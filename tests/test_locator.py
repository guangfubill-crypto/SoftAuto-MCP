from __future__ import annotations

from typing import Any

from softauto.locator import (
    build_locator,
    choose_best,
    configured_descriptor,
    descriptor_score,
    dynamic_name_prefix,
    ensure_selector,
    path_below_window,
    resolve_path,
    selector_variable_names,
)


class FakeControl:
    def __init__(self, name: str, control_type: str, automation_id: str = "", class_name: str = ""):
        self.Name = name
        self.ControlTypeName = control_type
        self.AutomationId = automation_id
        self.ClassName = class_name
        self.FrameworkId = "Test"
        self.ProcessId = 42
        self.NativeWindowHandle = 1 if control_type == "WindowControl" else 0
        self.parent: FakeControl | None = None
        self.children: list[FakeControl] = []

    def add(self, *children: FakeControl) -> FakeControl:
        for child in children:
            child.parent = self
            self.children.append(child)
        return self

    def GetChildren(self) -> list[FakeControl]:
        return self.children

    def GetParentControl(self) -> FakeControl | None:
        return self.parent

    def GetTopLevelControl(self) -> FakeControl:
        current = self
        while current.parent is not None:
            current = current.parent
        return current

    def __getattr__(self, _name: str) -> Any:
        raise AttributeError


def fixture_tree() -> tuple[FakeControl, FakeControl, FakeControl]:
    save = FakeControl("保存", "ButtonControl", "saveButton", "Button")
    cancel = FakeControl("取消", "ButtonControl", "cancelButton", "Button")
    panel = FakeControl("订单", "PaneControl", "orderPanel", "Panel").add(save, cancel)
    window = FakeControl("业务系统", "WindowControl", "mainWindow", "MainWindow").add(panel)
    return window, save, cancel


def test_build_and_resolve_stable_locator() -> None:
    window, save, _ = fixture_tree()
    locator = build_locator(save)
    assert locator["backend"] == "windows-uia"
    assert locator["target"]["automation_id"] == "saveButton"
    assert resolve_path(window, locator["path"]) is save


def test_automation_id_outweighs_mutable_name() -> None:
    _, save, cancel = fixture_tree()
    expected = {
        "automation_id": "saveButton",
        "name": "已保存",
        "control_type": "ButtonControl",
    }
    assert choose_best(expected, [cancel, save]) is save


def test_dynamic_label_uses_stable_text_prefix() -> None:
    expected = {
        "name": "Please take note of your order reference: 730",
        "class_name": "Static",
        "control_type": "TextControl",
        "framework_id": "Test",
    }
    unrelated = FakeControl("Total: 731", "TextControl", class_name="Static")
    current = FakeControl(
        "Please take note of your order reference: 842", "TextControl", class_name="Static"
    )

    assert dynamic_name_prefix(expected["name"]) == "Please take note of your order reference:"
    assert choose_best(expected, [unrelated, current]) is current


def test_dynamic_label_does_not_fall_back_to_unrelated_text() -> None:
    expected = {
        "name": "Order reference: 730",
        "class_name": "Static",
        "control_type": "TextControl",
    }
    unrelated = FakeControl("Customer number: 730", "TextControl", class_name="Static")

    assert choose_best(expected, [unrelated]) is None


def test_conflicting_automation_id_is_rejected() -> None:
    expected = {
        "automation_id": "Label1",
        "name": "Order reference: 730",
        "control_type": "TextControl",
    }
    actual = {
        "automation_id": "Label2",
        "name": "Order reference: 730",
        "control_type": "TextControl",
    }

    assert descriptor_score(expected, actual) == -1


def test_legacy_path_is_trimmed_below_resolved_window() -> None:
    window, save, _ = fixture_tree()
    locator = build_locator(save)
    legacy_path = [
        {
            "automation_id": "desktop",
            "name": "Desktop",
            "control_type": "PaneControl",
        },
        locator["window"],
        *locator["path"],
    ]

    trimmed = path_below_window(window, legacy_path)
    assert resolve_path(window, trimmed) is save


def test_system_recommendation_uses_prefix_instead_of_dynamic_full_name() -> None:
    locator = {
        "window": {"automation_id": "frmConfirm", "name": "Order Confirmation"},
        "path": [],
        "target": {
            "automation_id": "Label1",
            "name": "Order reference: 730",
            "class_name": "Static",
            "control_type": "TextControl",
        },
    }

    ensure_selector(locator)
    selected = locator["selector"]["target"]
    assert "automation_id" in selected
    assert "name_prefix" in selected
    assert "name" not in selected


def test_wildcard_property_matches_current_dynamic_value() -> None:
    expected = {
        "name": "Please take note of your order reference: *",
        "control_type": "TextControl",
    }
    current = FakeControl(
        "Please take note of your order reference: 842", "TextControl", class_name="Static"
    )

    assert choose_best(expected, [current]) is current


def test_selector_variable_is_resolved_from_mcp_arguments() -> None:
    source = {"name": "Order reference: 730", "control_type": "TextControl"}
    configured = configured_descriptor(
        source,
        ["name", "control_type"],
        {"name": "Order reference: ${reference}"},
        {"reference": 842},
    )

    assert configured["name"] == "Order reference: 842"


def test_selector_variable_names_are_discovered() -> None:
    locator = {
        "selector": {
            "values": {
                "window": {"name": "${window}"},
                "target": {"name": "Order ${reference} / ${reference}"},
            }
        }
    }

    assert selector_variable_names(locator) == ["reference", "window"]
