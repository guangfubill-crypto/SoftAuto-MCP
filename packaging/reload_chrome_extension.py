from __future__ import annotations

import time
from typing import Any

import uiautomation as auto
from comtypes import COMError


def walk(root: Any, max_depth: int = 20) -> list[Any]:
    found: list[Any] = []
    pending = [(root, 0)]
    while pending:
        control, depth = pending.pop(0)
        found.append(control)
        if depth >= max_depth:
            continue
        try:
            pending.extend((child, depth + 1) for child in control.GetChildren())
        except (AttributeError, COMError, OSError, RuntimeError) as exc:
            _ = exc
    return found


def property_value(control: Any, name: str) -> Any:
    try:
        return getattr(control, name)
    except (AttributeError, COMError, OSError, RuntimeError):
        return None


def main() -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        windows = [
            window
            for window in auto.GetRootControl().GetChildren()
            if property_value(window, "ClassName") == "Chrome_WidgetWin_1"
        ]
        controls = [control for window in windows for control in walk(window)]
        names = [
            control
            for control in controls
            if property_value(control, "Name")
            in {"零禾一智能 Web Connector", "SoftAuto Web Connector"}
            and property_value(control, "AutomationId") == "name"
            and property_value(control, "ControlTypeName") == "TextControl"
            and property_value(control, "BoundingRectangle")
            and property_value(control, "BoundingRectangle").width() > 0
        ]
        reloads = [
            control
            for control in controls
            if property_value(control, "Name") in {"重新加载", "Reload"}
            and property_value(control, "AutomationId") == "dev-reload-button"
            and property_value(control, "BoundingRectangle")
            and property_value(control, "BoundingRectangle").width() > 0
        ]
        if names and reloads:
            name_rect = names[0].BoundingRectangle
            target = min(
                reloads,
                key=lambda control: abs(
                    (control.BoundingRectangle.left + control.BoundingRectangle.right)
                    - (name_rect.left + name_rect.right)
                ),
            )
            top_level = target.GetTopLevelControl()
            if top_level:
                top_level.SetFocus()
                time.sleep(0.3)
            pattern = target.GetInvokePattern()
            if pattern:
                pattern.Invoke()
            else:
                target.Click()
            print("PASS: 零禾一智能 Web Connector reloaded")
            return
        time.sleep(0.5)
    raise RuntimeError("零禾一智能 Web Connector card or reload button was not found")


if __name__ == "__main__":
    main()
