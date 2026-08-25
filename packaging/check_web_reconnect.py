from __future__ import annotations

import json
import time

from softauto.web_bridge import WebAutomationError, WebBridgeClient

client = WebBridgeClient()
deadline = time.time() + 15
status = None
while time.time() < deadline:
    try:
        status = client.status()
        if status.get("extension_connected"):
            print(json.dumps({"status": "PASS", "bridge": status}, ensure_ascii=False))
            raise SystemExit(0)
    except WebAutomationError:
        pass
    time.sleep(0.5)

raise RuntimeError(f"Chrome extension did not reconnect within 15 seconds: {status}")
