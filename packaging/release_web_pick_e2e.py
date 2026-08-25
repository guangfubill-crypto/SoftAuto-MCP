from __future__ import annotations

import json
import sys
import threading
import time

import uiautomation as auto
from pynput import keyboard, mouse

from softauto.web_bridge import WebAutomationError, WebBridgeClient

sys.path.insert(0, str(__file__).rsplit("\\", 1)[0])
from reload_chrome_extension import walk

window = next(
    item
    for item in auto.GetRootControl().GetChildren()
    if item.Name == "SoftAuto DOM Test - Google Chrome"
)
window.SetFocus()
target = next(
    control
    for control in walk(window)
    if control.Name == "账号"
    and control.ControlTypeName == "EditControl"
    and control.BoundingRectangle.width() > 0
)

client = WebBridgeClient()
result: dict = {}
failure: list[Exception] = []


def pick() -> None:
    try:
        result.update(client.request("start_pick", {}, timeout=15))
    except (WebAutomationError, TimeoutError) as exc:
        failure.append(exc)


worker = threading.Thread(target=pick)
worker.start()
time.sleep(1)
rect = target.BoundingRectangle
pointer = mouse.Controller()
keys = keyboard.Controller()
with keys.pressed(keyboard.Key.ctrl):
    pointer.position = ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    pointer.click(mouse.Button.left)
worker.join(timeout=15)

assert not worker.is_alive(), "Ctrl+click picker did not return"
assert not failure, failure
assert result["locator"]["backend"] == "browser-dom"
assert result["captured"]["tag"] == "input"
assert any(item["value"] == "#account" for item in result["locator"]["selectors"])
validated = client.request("validate", {"locator": result["locator"]})
assert validated["element"]["tag"] == "input"

print(
    json.dumps(
        {
            "status": "PASS",
            "captured_tag": result["captured"]["tag"],
            "selectors": result["locator"]["selectors"],
        },
        ensure_ascii=False,
    )
)
