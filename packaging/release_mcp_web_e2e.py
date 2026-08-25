from __future__ import annotations

import asyncio
import json
import sys

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    executable = sys.argv[1]
    target = StdioServerParameters(command=executable)
    locator = {
        "backend": "browser-dom",
        "version": 1,
        "page": {"origin": "http://127.0.0.1:18080"},
        "frame": {
            "url": "http://127.0.0.1:18080/web-bridge-test.html?run=1",
            "is_top": True,
        },
        "target": {"tag": "input", "attributes": {}},
        "selectors": [
            {"kind": "css", "value": "#${field_id}", "enabled": True},
        ],
    }
    async with Client(stdio_client(target), mode="legacy") as client:
        status = await client.call_tool("automation_status", {})
        status_payload = status.structured_content
        assert status_payload["actions_enabled"] is True
        assert status_payload["web_dom"]["extension_connected"] is True

        resolved = await client.call_tool(
            "get_element",
            {"locator": locator, "variables": {"field_id": "account"}},
        )
        assert resolved.structured_content["ok"] is True

        changed = await client.call_tool(
            "set_element_value",
            {
                "locator": locator,
                "variables": {"field_id": "account"},
                "value": "agent-admin",
                "confirm": True,
            },
        )
        assert changed.structured_content["ok"] is True
        assert changed.structured_content["result"]["element"]["value"] == "agent-admin"

        restored = await client.call_tool(
            "set_element_value",
            {
                "locator": locator,
                "variables": {"field_id": "account"},
                "value": "admin",
                "confirm": True,
            },
        )
        assert restored.structured_content["result"]["element"]["value"] == "admin"

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "transport": "stdio",
                    "dynamic_variable": "field_id",
                    "web_action": "set_element_value",
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
