from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def source_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    configured = os.environ.get("SOFTAUTO_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if not is_frozen():
        return source_project_root() / "data"
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return (base / "SoftAuto" / "data").resolve()


def bundled_resource(*parts: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", source_project_root()))
    return bundle_root.joinpath(*parts).resolve()
