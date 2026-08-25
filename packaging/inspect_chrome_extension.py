from __future__ import annotations

import uiautomation as auto
from reload_chrome_extension import property_value, walk

for window in auto.GetRootControl().GetChildren():
    if property_value(window, "ClassName") != "Chrome_WidgetWin_1":
        continue
    controls = walk(window)
    if not any(
        property_value(item, "Name")
        in {"零禾一智能 Web Connector", "SoftAuto Web Connector"}
        for item in controls
    ):
        continue
    print(f"WINDOW: {property_value(window, 'Name')}")
    for control in controls:
        name = str(property_value(control, "Name") or "").strip()
        automation_id = str(property_value(control, "AutomationId") or "")
        if name and (
            "SoftAuto" in name
            or "错误" in name
            or "Error" in name
            or "Service Worker" in name
            or automation_id in {"version", "errors-button", "inspect-views"}
        ):
            print(
                repr(name),
                property_value(control, "ControlTypeName"),
                repr(automation_id),
                property_value(control, "BoundingRectangle"),
            )
        elif automation_id in {"name", "dev-reload-button", "version"}:
            print(
                "CARD",
                repr(name),
                property_value(control, "ControlTypeName"),
                repr(automation_id),
                property_value(control, "BoundingRectangle"),
            )
