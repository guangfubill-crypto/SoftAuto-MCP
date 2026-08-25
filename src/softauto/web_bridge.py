from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from websockets.sync.server import ServerConnection, serve

WS_HOST = "127.0.0.1"
WS_PORT = 17856
HTTP_PORT = 17857


class WebAutomationError(RuntimeError):
    """The Chrome extension bridge could not complete a bounded DOM operation."""


@dataclass
class _PendingRequest:
    event: threading.Event = field(default_factory=threading.Event)
    response: dict[str, Any] | None = None


class WebBridgeServer:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connections: set[ServerConnection] = set()
        self._pending: dict[str, _PendingRequest] = {}
        self._extension_info: dict[str, Any] = {}
        self._last_seen = 0.0
        self._ws_server: Any = None
        self._http_server: ThreadingHTTPServer | None = None
        self._ready = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._serve_websocket, daemon=True).start()
        threading.Thread(target=self._serve_http, daemon=True).start()
        if not self._ready.wait(3):
            raise WebAutomationError("Web extension bridge failed to start")

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": True,
                "extension_connected": bool(self._connections),
                "connection_count": len(self._connections),
                "extension": dict(self._extension_info),
                "last_seen": self._last_seen or None,
            }

    def request(self, command: str, payload: dict[str, Any], timeout: float = 30) -> Any:
        request_id = str(uuid.uuid4())
        pending = _PendingRequest()
        message = {
            "type": "command",
            "request_id": request_id,
            "command": command,
            "payload": payload,
        }
        with self._lock:
            connections = list(self._connections)
            if not connections:
                raise WebAutomationError(
                    "SoftAuto Chrome extension is not connected. Open Chrome and check the extension."
                )
            self._pending[request_id] = pending
        delivered = False
        encoded = json.dumps(message, ensure_ascii=False)
        for connection in connections:
            try:
                connection.send(encoded)
                delivered = True
            except (OSError, RuntimeError):
                continue
        if not delivered:
            with self._lock:
                self._pending.pop(request_id, None)
            raise WebAutomationError("Could not send a command to the Chrome extension")
        if not pending.event.wait(max(1, min(timeout, 120))):
            with self._lock:
                self._pending.pop(request_id, None)
            raise WebAutomationError(f"Chrome extension command timed out: {command}")
        response = pending.response or {}
        if not response.get("ok"):
            raise WebAutomationError(str(response.get("error") or "Web element operation failed"))
        return response.get("result")

    def _serve_websocket(self) -> None:
        try:
            with serve(self._handle_extension, WS_HOST, WS_PORT) as server:
                self._ws_server = server
                self._ready.set()
                server.serve_forever()
        except OSError:
            self._ready.set()

    def _serve_http(self) -> None:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != "/v1/status":
                    self._reply(404, {"ok": False, "error": "Not found"})
                    return
                self._reply(200, bridge.status())

            def do_POST(self) -> None:
                if self.path != "/v1/request":
                    self._reply(404, {"ok": False, "error": "Not found"})
                    return
                try:
                    length = min(int(self.headers.get("Content-Length", "0")), 1_000_000)
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    result = bridge.request(
                        str(body.get("command") or ""),
                        body.get("payload") or {},
                        float(body.get("timeout") or 30),
                    )
                    self._reply(200, {"ok": True, "result": result})
                except (TypeError, ValueError, WebAutomationError) as exc:
                    self._reply(400, {"ok": False, "error": str(exc)})

            def _reply(self, status: int, body: dict[str, Any]) -> None:
                encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        try:
            self._http_server = ThreadingHTTPServer((WS_HOST, HTTP_PORT), Handler)
            self._ready.set()
            self._http_server.serve_forever()
        except OSError:
            self._ready.set()

    def _handle_extension(self, connection: ServerConnection) -> None:
        with self._lock:
            self._connections.add(connection)
            self._last_seen = time.time()
        try:
            for raw_message in connection:
                message = json.loads(raw_message)
                with self._lock:
                    self._last_seen = time.time()
                if message.get("type") == "hello":
                    with self._lock:
                        self._extension_info = message.get("extension") or {}
                    connection.send(json.dumps({"type": "hello_ack", "ok": True}))
                elif message.get("type") == "result":
                    request_id = str(message.get("request_id") or "")
                    with self._lock:
                        pending = self._pending.pop(request_id, None)
                    if pending:
                        pending.response = message
                        pending.event.set()
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            pass
        finally:
            with self._lock:
                self._connections.discard(connection)


class WebBridgeClient:
    def status(self) -> dict[str, Any]:
        return self._json_request("GET", "/v1/status")

    def request(self, command: str, payload: dict[str, Any], timeout: float = 30) -> Any:
        response = self._json_request(
            "POST",
            "/v1/request",
            {"command": command, "payload": payload, "timeout": timeout},
            timeout=timeout + 2,
        )
        if not response.get("ok"):
            raise WebAutomationError(str(response.get("error") or "Web bridge request failed"))
        return response.get("result")

    @staticmethod
    def _json_request(
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        timeout: float = 3,
    ) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"http://{WS_HOST}:{HTTP_PORT}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                return json.loads(exc.read().decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as decode_error:
                raise WebAutomationError(
                    f"SoftAuto web bridge returned HTTP {exc.code}"
                ) from decode_error
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise WebAutomationError("SoftAuto web bridge is not running") from exc


_server_lock = threading.Lock()
_server: WebBridgeServer | None = None


def ensure_web_bridge_server() -> WebBridgeClient:
    global _server
    client = WebBridgeClient()
    try:
        client.status()
        return client
    except WebAutomationError:
        pass
    with _server_lock:
        try:
            client.status()
            return client
        except WebAutomationError:
            if _server is None:
                _server = WebBridgeServer()
                _server.start()
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            client.status()
            return client
        except WebAutomationError:
            time.sleep(0.05)
    raise WebAutomationError("SoftAuto web bridge did not become ready")
