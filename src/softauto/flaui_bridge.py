from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .locator import ensure_selector
from .runtime_paths import bundled_resource


class FlaUIBridgeError(RuntimeError):
    """FlaUI could not inspect the requested point."""


def executable_path() -> Path:
    configured = os.environ.get("FLAUI_BRIDGE_PATH")
    if configured:
        return Path(configured).resolve()
    return bundled_resource("tools", "FlaUIBridge", "FlaUIBridge.exe")


def inspect_point(
    x: int,
    y: int,
    engine: str = "auto",
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Inspect a desktop point through FlaUI UIA3/UIA2.

    The bridge is intentionally a short-lived process. This prevents a stale
    COM/UIA object from surviving an ERP restart and keeps the main Python UIA
    backend independent from the .NET runtime.
    """

    executable = executable_path()
    if not executable.is_file():
        raise FlaUIBridgeError(f"FlaUI bridge was not found: {executable}")
    request = json.dumps(
        {"op": "inspect_point", "x": int(x), "y": int(y), "engine": engine},
        ensure_ascii=False,
    )
    try:
        completed = subprocess.run(
            [str(executable)],
            input=request + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=max(0.5, float(timeout)),
            cwd=str(executable.parent),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FlaUIBridgeError(str(exc)) from exc
    line = completed.stdout.strip().splitlines()
    if not line:
        detail = completed.stderr.strip() or "FlaUI bridge returned no result"
        raise FlaUIBridgeError(detail)
    try:
        result = json.loads(line[-1])
    except json.JSONDecodeError as exc:
        raise FlaUIBridgeError(f"Invalid FlaUI bridge response: {line[-1]}") from exc
    if not result.get("ok"):
        raise FlaUIBridgeError(str(result.get("error") or "FlaUI inspection failed"))
    locator = result.get("locator")
    if isinstance(locator, dict):
        result["locator"] = ensure_selector(locator)
    result["capture_engine"] = result.get("engine", engine)
    return result
