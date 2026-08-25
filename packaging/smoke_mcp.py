from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    executable, data_dir = sys.argv[1:3]
    environment = dict(os.environ)
    environment["SOFTAUTO_DATA_DIR"] = data_dir
    target = StdioServerParameters(command=executable, env=environment)
    async with Client(stdio_client(target), mode="legacy") as client:
        tools = await client.list_tools()
        status = await client.call_tool("automation_status", {})
        payload = {
            "tool_count": len(tools.tools),
            "has_element_tree": any(tool.name == "list_element_tree" for tool in tools.tools),
            "has_click": any(tool.name == "click_element" for tool in tools.tools),
            "actions_enabled": status.structured_content["actions_enabled"],
            "backend": status.structured_content["backend"],
        }
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
