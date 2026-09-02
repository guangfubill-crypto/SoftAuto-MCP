from __future__ import annotations

import json
from pathlib import Path

from softauto import __version__
from softauto.picker import APP_TITLE, BRAND_NAME


def test_brand_identity_and_release_version() -> None:
    assert BRAND_NAME == "零禾一智能"
    assert BRAND_NAME in APP_TITLE
    assert __version__ == "0.5.4"


def test_brand_assets_include_real_alpha_and_windows_icon() -> None:
    root = Path(__file__).resolve().parents[1]
    png = (root / "assets" / "brand-mark.png").read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert png[24] == 8
    assert png[25] == 6  # PNG color type 6 is RGBA.
    assert (root / "assets" / "brand-header.png").is_file()
    assert (root / "assets" / "softauto.ico").is_file()


def test_extension_uses_branded_multisize_icons() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "web-extension" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "零禾一智能 Web Connector"
    assert manifest["version"] == "0.3.1"
    for size, icon_path in manifest["icons"].items():
        assert int(size) in {16, 32, 48, 128}
        assert (root / "web-extension" / icon_path).is_file()
