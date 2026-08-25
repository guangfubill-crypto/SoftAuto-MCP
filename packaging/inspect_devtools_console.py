from __future__ import annotations

import uiautomation as auto
from reload_chrome_extension import property_value, walk

window = next(
    item
    for item in auto.GetRootControl().GetChildren()
    if property_value(item, "Name") == "DevTools"
)
for control in walk(window):
    name = str(property_value(control, "Name") or "").strip()
    if name:
        print(property_value(control, "ControlTypeName"), repr(name))
