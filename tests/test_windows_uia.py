from unittest.mock import Mock, call, patch

import uiautomation as auto

from softauto.windows_uia import WindowsUIABackend


def test_click_prefers_invoke_pattern_for_covered_controls() -> None:
    backend = WindowsUIABackend()
    control = Mock()
    pattern = Mock()
    control.GetPattern.return_value = pattern
    with (
        patch.object(backend, "_action_target", return_value=control),
        patch.object(backend, "_snapshot", return_value={"name": "Execute Gate"}),
    ):
        result = backend.click({"backend": "windows-uia"})

    pattern.Invoke.assert_called_once_with()
    assert result["action"] == "invoked"


def test_click_activates_and_focuses_before_physical_fallback() -> None:
    backend = WindowsUIABackend()
    control = Mock()
    top_level = Mock()
    control.GetPattern.return_value = None
    control.GetTopLevelControl.return_value = top_level
    with (
        patch.object(backend, "_action_target", return_value=control),
        patch.object(backend, "_snapshot", return_value={"name": "Canvas"}),
    ):
        result = backend.click({"backend": "windows-uia"})

    assert control.method_calls == [
        call.GetPattern(auto.PatternId.InvokePattern),
        call.GetTopLevelControl(),
        call.SetFocus(),
        call.Click(),
    ]
    top_level.SetActive.assert_called_once_with()
    assert result["action"] == "clicked"
