from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    executable = sys.argv[1]
    state_path = Path(sys.argv[2]).resolve()
    state_path.unlink(missing_ok=True)
    target = StdioServerParameters(command=executable)
    async with Client(stdio_client(target), mode="legacy") as client:
        windows = await client.call_tool("list_windows", {"limit": 200})
        window = next(
            item
            for item in windows.structured_content["result"]
            if item["name"] == "SoftAuto Desktop Release Gate"
        )

        edits = await client.call_tool(
            "find_elements",
            {
                "query": {"name": "Release Gate Input", "control_type": "EditControl"},
                "scope_locator": window["locator"],
                "max_depth": 8,
                "limit": 10,
            },
        )
        edit = edits.structured_content["result"][0]
        focused = await client.call_tool(
            "focus_element",
            {"locator": edit["locator"]},
        )
        assert focused.structured_content["ok"] is True
        written = await client.call_tool(
            "set_element_value",
            {"locator": edit["locator"], "value": "DESKTOP_VALUE_OK", "confirm": True},
        )
        assert written.structured_content["ok"] is True

        buttons = await client.call_tool(
            "find_elements",
            {
                "query": {"name": "Execute Gate", "control_type": "ButtonControl"},
                "scope_locator": window["locator"],
                "max_depth": 8,
                "limit": 10,
            },
        )
        button = buttons.structured_content["result"][0]
        highlighted = await client.call_tool(
            "highlight_element",
            {"locator": button["locator"], "seconds": 0.1},
        )
        if highlighted.structured_content is None:
            raise AssertionError(f"Highlight returned no structured content: {highlighted.content}")
        assert highlighted.structured_content["ok"] is True

        denied = await client.call_tool(
            "click_element",
            {"locator": button["locator"], "confirm": False},
        )
        assert denied.structured_content["ok"] is False
        clicked = await client.call_tool(
            "click_element",
            {"locator": button["locator"], "confirm": True},
        )
        assert clicked.structured_content["ok"] is True

        deadline = time.time() + 5
        while time.time() < deadline and not state_path.is_file():
            await asyncio.sleep(0.1)
        assert state_path.read_text(encoding="utf-8") == "DESKTOP_VALUE_OK"
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "transport": "stdio",
                    "backend": "windows-uia",
                    "actions": ["focus", "set_value", "highlight", "click"],
                    "confirmation_gate": "PASS",
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
