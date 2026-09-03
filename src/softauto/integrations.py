from __future__ import annotations

from typing import Any


def catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "windows-uia",
            "role": "Windows element inspection and actions with FlaUI UIA3/UIA2 fallback",
            "project": "Python-UIAutomation-for-Windows",
            "repository": "https://github.com/yinkaisheng/Python-UIAutomation-for-Windows",
            "license": "Apache-2.0",
            "connection": "Python UIA primary; bundled FlaUI Bridge tries UIA3 then UIA2 when capture fails",
        },
        {
            "id": "flauinspect",
            "role": "Windows visual element inspector",
            "project": "FlaUInspect",
            "repository": "https://github.com/FlaUI/FlaUInspect",
            "license": "MIT",
            "connection": "Bundled desktop executable; run softauto-inspector",
        },
        {
            "id": "playwright",
            "role": "Browser DOM and accessibility-tree automation",
            "project": "Playwright MCP",
            "repository": "https://github.com/microsoft/playwright-mcp",
            "license": "Apache-2.0",
            "connection": "Direct MCP server in mcp-stack.json",
        },
        {
            "id": "uivision",
            "role": "OCR, computer vision, browser and desktop fallback",
            "project": "Ui.Vision MCP Bridge",
            "repository": "https://github.com/A9T9/RPA/tree/master/mcp",
            "license": "MIT bridge; AGPL-3.0/commercial core",
            "connection": "Direct MCP server in mcp-stack.json; extension pairing required",
        },
        {
            "id": "openadapt",
            "role": "Recorded, compiled and governed repeatable workflows",
            "project": "OpenAdapt Agent",
            "repository": "https://github.com/OpenAdaptAI/openadapt-agent",
            "license": "MIT",
            "connection": "Optional direct MCP server; see mcp-openadapt.example.json",
        },
    ]
