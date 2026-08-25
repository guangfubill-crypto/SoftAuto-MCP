from __future__ import annotations

import uiautomation as auto
from reload_chrome_extension import property_value, walk

controls = [
    control
    for window in auto.GetRootControl().GetChildren()
    if property_value(window, "ClassName") == "Chrome_WidgetWin_1"
    for control in walk(window)
]
name = next(
    control
    for control in controls
    if property_value(control, "Name") == "零禾一智能 Web Connector"
    and property_value(control, "AutomationId") == "name"
    and property_value(control, "ControlTypeName") == "TextControl"
)
name_rect = name.BoundingRectangle
links = [
    control
    for control in controls
    if str(property_value(control, "Name") or "").startswith("Service Worker")
    and property_value(control, "ControlTypeName") == "HyperlinkControl"
    and property_value(control, "BoundingRectangle").width() > 0
]
target = min(
    links,
    key=lambda control: abs(
        (control.BoundingRectangle.left + control.BoundingRectangle.right)
        - (name_rect.left + name_rect.right)
    ),
)
pattern = target.GetInvokePattern()
if pattern:
    pattern.Invoke()
else:
    target.Click()
print("PASS: opened 零禾一智能 extension Service Worker inspector")
