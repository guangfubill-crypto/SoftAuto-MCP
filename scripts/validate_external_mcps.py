from __future__ import annotations

import asyncio

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


async def inspect_server(name: str, args: list[str]) -> dict[str, object]:
    target = StdioServerParameters(command="npx", args=args)
    async with Client(stdio_client(target), mode="legacy") as client:
        listed = await client.list_tools()
        return {"name": name, "tool_count": len(listed.tools), "connected": True}


async def main() -> None:
    results = []
    results.append(
        await inspect_server(
            "playwright",
            ["-y", "@playwright/mcp@0.0.79", "--isolated", "--headless"],
        )
    )
    results.append(
        await inspect_server(
            "uivision",
            [
                "-y",
                "uivision-mcp-bridge@1.1.1",
                "--token",
                "softauto-validation-token",
                "--port",
                "50991",
            ],
        )
    )
    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
