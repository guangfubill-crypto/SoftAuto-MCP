import json
import threading

from websockets.sync.client import connect

from softauto.web_bridge import WS_PORT, WebBridgeClient, ensure_web_bridge_server


def test_web_bridge_round_trip() -> None:
    client = ensure_web_bridge_server()
    extension = connect(f"ws://127.0.0.1:{WS_PORT}")
    extension.send(
        json.dumps(
            {
                "type": "hello",
                "extension": {"id": "test-extension", "version": "test"},
            }
        )
    )
    extension.recv()

    def respond() -> None:
        command = json.loads(extension.recv())
        extension.send(
            json.dumps(
                {
                    "type": "result",
                    "request_id": command["request_id"],
                    "ok": True,
                    "result": {"command": command["command"]},
                }
            )
        )

    worker = threading.Thread(target=respond)
    worker.start()
    result = WebBridgeClient().request("validate", {"locator": {}}, timeout=3)
    worker.join(timeout=3)
    extension.close()

    assert result == {"command": "validate"}
    assert client.status()["ok"] is True
