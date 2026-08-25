from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from softauto import server


@pytest.mark.asyncio
async def test_mcp_exposes_read_and_action_tools() -> None:
    async with Client(server.mcp) as client:
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        assert {
            "automation_status",
            "integration_catalog",
            "list_element_projects",
            "get_active_element_project",
            "list_saved_elements",
            "list_element_tree",
            "get_saved_element",
            "validate_saved_element",
            "list_windows",
            "inspect_point",
            "get_element",
            "get_children",
            "find_elements",
            "highlight_element",
            "focus_element",
            "click_element",
            "invoke_element",
            "set_element_value",
            "send_element_keys",
        } == names

        integrations = await client.call_tool("integration_catalog", {})
        ids = {item["id"] for item in integrations.structured_content["integrations"]}
        assert {"windows-uia", "flauinspect", "playwright", "uivision", "openadapt"} == ids


@pytest.mark.asyncio
async def test_documented_stdio_server_command() -> None:
    project_root = Path(__file__).resolve().parents[1]
    target = StdioServerParameters(
        command="uv",
        args=["run", "mcp", "run", "src/softauto/server.py:mcp"],
        cwd=project_root,
    )
    async with Client(stdio_client(target), mode="legacy") as client:
        result = await client.call_tool("automation_status", {})
        assert result.structured_content["backend"] == "windows-uia"
        assert result.structured_content["actions_enabled"] is False
