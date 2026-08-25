import json
from pathlib import Path

from softauto.mcp_config import agent_mcp_config_json


def test_agent_mcp_config_uses_bundled_executable_path(tmp_path: Path) -> None:
    executable = tmp_path / "mcp" / "SoftAutoMCP.exe"
    config = json.loads(agent_mcp_config_json(executable))

    assert config == {
        "mcpServers": {
            "software-automation": {
                "command": str(executable.resolve()),
            }
        }
    }
