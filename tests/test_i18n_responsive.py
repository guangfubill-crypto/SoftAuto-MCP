from __future__ import annotations

import json
from pathlib import Path

from softauto.i18n import (
    load_language,
    responsive_layout_mode,
    responsive_window_metrics,
    save_language,
    translate,
)


def test_language_translation_and_persistence(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    assert load_language(settings) == "zh-CN"
    assert translate("validate", "en") == "✓ Validate"
    save_language("en", settings)
    assert json.loads(settings.read_text(encoding="utf-8")) == {"language": "en"}
    assert load_language(settings) == "en"


def test_invalid_language_falls_back_to_simplified_chinese(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text('{"language": "invalid"}', encoding="utf-8")
    assert load_language(settings) == "zh-CN"
    assert translate("validate", "invalid") == "✓ 验证"


def test_window_metrics_fit_common_displays() -> None:
    for screen_width, screen_height in ((3840, 2160), (1366, 768), (1024, 768), (800, 600)):
        width, height, minimum_width, minimum_height = responsive_window_metrics(
            screen_width, screen_height
        )
        assert minimum_width <= width <= screen_width
        assert minimum_height <= height <= screen_height
        assert minimum_width >= 640
        assert minimum_height >= 440


def test_responsive_layout_breakpoints() -> None:
    assert responsive_layout_mode(1280) == "wide"
    assert responsive_layout_mode(1024) == "compact"
    assert responsive_layout_mode(800) == "narrow"
