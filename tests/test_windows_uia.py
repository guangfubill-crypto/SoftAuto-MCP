from unittest.mock import Mock, call, patch

import uiautomation as auto

from softauto.windows_uia import WindowsUIABackend



class _FakeControl:
    def __init__(self, name: str, control_type: str, automation_id: str, class_name: str):
        self.Name = name
        self.ControlTypeName = control_type
        self.AutomationId = automation_id
        self.ClassName = class_name
        self.FrameworkId = "Test"
        self.ProcessId = 42
        self.NativeWindowHandle = 1 if control_type == "WindowControl" else 0
        self.parent = None
        self.children = []

    def add(self, *children):
        for child in children:
            child.parent = self
            self.children.append(child)
        return self

    def GetChildren(self):
        return self.children

    def GetParentControl(self):
        return self.parent

    def GetTopLevelControl(self):
        current = self
        while current.parent is not None:
            current = current.parent
        return current


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


def test_diagnose_reports_match_count_for_capture_style_locator() -> None:
    save = _FakeControl("保存", "ButtonControl", "saveButton", "Button")
    panel = _FakeControl("订单", "PaneControl", "orderPanel", "Panel").add(save)
    window = _FakeControl("业务系统", "WindowControl", "mainWindow", "MainWindow").add(panel)
    locator = {
        "backend": "windows-uia",
        "version": 1,
        "window": {"automation_id": "mainWindow", "control_type": "WindowControl"},
        "path": [{"automation_id": "orderPanel", "control_type": "PaneControl"}],
        "target": {"automation_id": "saveButton", "control_type": "ButtonControl"},
        "selector": {
            "window": ["automation_id", "control_type"],
            "path": [["automation_id", "control_type"]],
            "target": ["automation_id", "control_type"],
            "values": {"window": {}, "path": [{}], "target": {}},
        },
    }
    backend = WindowsUIABackend()
    with patch.object(auto, "GetRootControl", return_value=Mock(GetChildren=lambda: [window])):
        with patch.object(backend, "_snapshot", side_effect=lambda control, include_locator=True: {"name": control.Name, "bounds": {"left": 0, "top": 0, "right": 1, "bottom": 1}}):
            result = backend.diagnose(locator)

    assert result["ok"] is True
    assert result["match_count"] == 1
    assert result["element"]["name"] == "保存"


def test_element_from_point_falls_back_to_flaui_when_python_uia_fails() -> None:
    backend = WindowsUIABackend()
    fallback = {
        "ok": True,
        "engine": "uia2",
        "capture_engine": "uia2",
        "point": {"x": 12, "y": 34},
        "locator": {"backend": "windows-uia", "version": 1, "window": {}, "path": [], "target": {}},
    }
    with patch.object(auto, "ControlFromPoint", side_effect=RuntimeError("UIA provider failed")):
        with patch("softauto.flaui_bridge.inspect_point", return_value=fallback) as inspect:
            result = backend.element_from_point(12, 34)

    inspect.assert_called_once_with(12, 34, engine="auto")
    assert result["capture_engine"] == "uia2"
