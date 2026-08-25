from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from pathlib import Path

from softauto.runtime_paths import bundled_resource, is_frozen, user_data_dir

CHROME_EXTENSIONS_URL = "chrome://extensions/"


def extension_source_path() -> Path:
    return bundled_resource("web-extension")


def extension_install_path() -> Path:
    if not is_frozen():
        return extension_source_path()
    return user_data_dir().parent / "web-extension"


def prepare_local_extension(
    source: Path | None = None,
    destination: Path | None = None,
) -> Path:
    source_path = (source or extension_source_path()).resolve()
    destination_path = (destination or extension_install_path()).resolve()
    manifest = source_path / "manifest.json"
    if not manifest.is_file():
        raise FileNotFoundError(f"Chrome extension manifest was not found: {manifest}")
    if source_path != destination_path:
        destination_path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
    return destination_path


def chrome_executable() -> Path | None:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
    ]
    return next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)


def open_extension_installation(extension_path: Path) -> str:
    store_url = os.environ.get("SOFTAUTO_EXTENSION_STORE_URL", "").strip()
    if store_url:
        webbrowser.open(store_url)
        return "store"
    chrome = chrome_executable()
    if chrome:
        subprocess.Popen([str(chrome), CHROME_EXTENSIONS_URL])
    os.startfile(str(extension_path))
    return "local"
