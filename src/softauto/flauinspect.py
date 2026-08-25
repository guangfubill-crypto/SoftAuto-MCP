from __future__ import annotations

import os
import subprocess
from pathlib import Path

from softauto.runtime_paths import bundled_resource


def executable_path() -> Path:
    configured = os.environ.get("FLAUINSPECT_PATH")
    return (
        Path(configured).resolve()
        if configured
        else bundled_resource("tools", "FlaUInspect", "FlaUInspect.exe")
    )


def main() -> None:
    executable = executable_path()
    if not executable.is_file():
        raise SystemExit(
            "FlaUInspect was not found. Download a release from "
            "https://github.com/FlaUI/FlaUInspect/releases or set FLAUINSPECT_PATH."
        )
    subprocess.Popen([str(executable)], cwd=str(executable.parent))


if __name__ == "__main__":
    main()
