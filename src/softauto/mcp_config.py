from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from softauto.runtime_paths import is_frozen, source_project_root


def mcp_executable_path() -> Path:
    if is_frozen():
        candidate = Path(sys.executable).resolve().parent / "mcp" / "SoftAutoMCP.exe"
    else:
        candidate = source_project_root() / "packaging" / "dist" / "SoftAutoMCP" / "SoftAutoMCP.exe"
    if not candidate.is_file():
        raise FileNotFoundError(f"SoftAuto MCP executable was not found: {candidate}")
    return candidate.resolve()


def agent_mcp_config(command: Path | None = None) -> dict[str, Any]:
    executable = (command or mcp_executable_path()).resolve()
    return {
        "mcpServers": {
            "software-automation": {
                "command": str(executable),
            }
        }
    }


def agent_mcp_config_json(command: Path | None = None) -> str:
    return json.dumps(agent_mcp_config(command), ensure_ascii=False, indent=2)
