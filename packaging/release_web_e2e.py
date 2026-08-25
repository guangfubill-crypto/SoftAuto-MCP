from __future__ import annotations

import json

from softauto.web_bridge import WebAutomationError, WebBridgeClient


def locator(selector: str, tag: str, text: str = "") -> dict:
    return {
        "backend": "browser-dom",
        "version": 1,
        "page": {"origin": "http://127.0.0.1:18080"},
        "frame": {
            "url": "http://127.0.0.1:18080/web-bridge-test.html?run=1",
            "is_top": True,
        },
        "target": {"tag": tag, "text": text, "attributes": {}},
        "selectors": [{"kind": "css", "value": selector, "enabled": True}],
    }


client = WebBridgeClient()
status = client.status()
assert status["extension_connected"] is True
assert status["extension"]["version"] == "0.3.1"

account = locator("#account", "input")
password = locator("#password", "input")
login = locator("#login", "button", "登录")
logged_in = locator("#logged-in", "div")
order_code = locator("#order-code", "input")
new_order = locator("#new-order", "button", "新建订单")
reference = locator("#order-reference", "output")
continue_button = locator("#continue", "button", "继续")

assert client.request("validate", {"locator": account})["element"]["tag"] == "input"
assert client.request("focus", {"locator": account})["element"]["focused"] is True
client.request("set_value", {"locator": account, "value": "admin"})
client.request("set_value", {"locator": password, "value": "admin"})
assert client.request("validate", {"locator": account})["element"]["value"] == "admin"
assert client.request("validate", {"locator": password})["element"]["value"] == "admin"
client.request("click", {"locator": login})
assert client.request("validate", {"locator": logged_in})["element"]["text"] == "LOGIN_OK"

client.request("set_value", {"locator": order_code, "value": ""})
client.request("send_keys", {"locator": order_code, "text": "ORDER-42"})
assert client.request("validate", {"locator": order_code})["element"]["value"] == "ORDER-42"
client.request("click", {"locator": new_order})
assert client.request("validate", {"locator": reference})["element"]["text"] == "REF-ORDER-42"
client.request("highlight", {"locator": reference})
client.request("click", {"locator": continue_button})
assert client.request("validate", {"locator": order_code})["element"]["value"] == ""
assert client.request("validate", {"locator": reference})["element"]["text"] == ""

try:
    client.request("validate", {"locator": locator("#does-not-exist", "div")}, timeout=3)
except WebAutomationError as exc:
    assert "未找到网页元素" in str(exc)
else:
    raise AssertionError("Missing DOM selector should fail")

print(
    json.dumps(
        {
            "status": "PASS",
            "extension_version": status["extension"]["version"],
            "validated_actions": [
                "validate",
                "focus",
                "set_value",
                "send_keys",
                "click",
                "highlight",
                "negative_selector",
            ],
        },
        ensure_ascii=False,
    )
)
