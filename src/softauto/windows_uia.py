from __future__ import annotations

import ctypes
import time
from collections import deque
from typing import Any

import uiautomation as auto
from comtypes import COMError

from .locator import (
    build_locator,
    choose_best,
    configured_descriptor,
    descriptor,
    path_below_window,
    resolve_path,
)


class AutomationError(RuntimeError):
    """UI Automation could not safely complete an operation."""


ALLOWED_QUERY_FIELDS = {
    "automation_id",
    "name",
    "name_contains",
    "class_name",
    "control_type",
    "framework_id",
    "process_id",
}


class WindowsUIABackend:
    backend_name = "windows-uia"

    def _snapshot(self, control: Any, include_locator: bool = True) -> dict[str, Any]:
        if control is None:
            raise AutomationError("Element not found")
        result = descriptor(control)
        try:
            rect = control.BoundingRectangle
            result["bounds"] = {
                "left": int(rect.left),
                "top": int(rect.top),
                "right": int(rect.right),
                "bottom": int(rect.bottom),
                "width": int(rect.width()),
                "height": int(rect.height()),
            }
        except (AttributeError, COMError, OSError, RuntimeError, TypeError):
            result["bounds"] = None
        for source, target in (("IsEnabled", "enabled"), ("IsOffscreen", "offscreen")):
            try:
                result[target] = bool(getattr(control, source))
            except (AttributeError, COMError, OSError, RuntimeError):
                result[target] = None
        if include_locator:
            result["locator"] = build_locator(control)
        return result

    def snapshot(self, control: Any, include_locator: bool = True) -> dict[str, Any]:
        return self._snapshot(control, include_locator)

    def list_windows(self, limit: int = 100) -> list[dict[str, Any]]:
        windows = []
        for control in auto.GetRootControl().GetChildren():
            item = self._snapshot(control)
            bounds = item.get("bounds")
            if not bounds or bounds["width"] <= 0 or bounds["height"] <= 0:
                continue
            if item.get("offscreen") is True:
                continue
            windows.append(item)
            if len(windows) >= max(1, min(limit, 200)):
                break
        return windows

    def element_from_point(self, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        if x is None or y is None:
            x, y = auto.GetCursorPos()
        control = auto.ControlFromPoint(int(x), int(y))
        result = self._snapshot(control)
        result["point"] = {"x": int(x), "y": int(y)}
        result["ancestors"] = self.ancestors(control)
        return result

    def ancestors(self, control: Any, limit: int = 32) -> list[dict[str, Any]]:
        items = []
        current = control.GetParentControl() if control else None
        while current is not None and len(items) < limit:
            items.append(self._snapshot(current, include_locator=False))
            current = current.GetParentControl()
        return items

    def resolve(self, locator: dict[str, Any], variables: dict[str, Any] | None = None) -> Any:
        if locator.get("backend") != self.backend_name or locator.get("version") != 1:
            raise AutomationError("Unsupported locator backend or version")
        windows = auto.GetRootControl().GetChildren()
        selector = locator.get("selector", {})
        values = selector.get("values", {})
        window_expected = configured_descriptor(
            locator.get("window", {}),
            selector.get("window"),
            values.get("window"),
            variables,
        )
        window = choose_best(window_expected, windows)
        if window is None:
            window = self._find_nested_window(window_expected, windows)
        if window is None:
            raise AutomationError("Target window could not be resolved")
        raw_path = locator.get("path", [])
        path_fields = selector.get("path", [])
        selected_path = [
            configured_descriptor(
                segment,
                path_fields[index] if index < len(path_fields) else None,
                values.get("path", [])[index] if index < len(values.get("path", [])) else None,
                variables,
            )
            for index, segment in enumerate(raw_path)
        ]
        path = path_below_window(window, selected_path)
        control = resolve_path(window, path) if path else window
        target = configured_descriptor(
            locator.get("target", {}),
            selector.get("target"),
            values.get("target"),
            variables,
        )
        if control is not None:
            matched = choose_best(target, [control])
            if matched is not None:
                return matched

        candidates = self._walk(window, max_depth=12, max_results=5000)
        control = choose_best(target, candidates)
        if control is None:
            raise AutomationError("Target element could not be resolved")
        return control

    def _find_nested_window(self, expected: dict[str, Any], windows: list[Any]) -> Any | None:
        expected_process = int(expected.get("process_id") or 0)
        roots = [
            window
            for window in windows
            if expected_process
            and int(descriptor(window).get("process_id") or 0) == expected_process
        ]
        if not roots:
            expected_framework = expected.get("framework_id")
            roots = [
                window
                for window in windows
                if not expected_framework
                or descriptor(window).get("framework_id") == expected_framework
            ][:20]
        for root in roots:
            nested = choose_best(expected, self._walk(root, max_depth=4, max_results=1000))
            if nested is not None:
                return nested
        return None

    def get_element(
        self, locator: dict[str, Any], variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._snapshot(self.resolve(locator, variables))

    def children(self, locator: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        control = self.resolve(locator)
        return [self._snapshot(item) for item in control.GetChildren()[: max(1, min(limit, 500))]]

    def find_elements(
        self,
        query: dict[str, Any],
        scope_locator: dict[str, Any] | None = None,
        max_depth: int = 12,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        unknown = set(query) - ALLOWED_QUERY_FIELDS
        if unknown:
            raise AutomationError(f"Unsupported query fields: {sorted(unknown)}")
        if not query:
            raise AutomationError("At least one query field is required")
        root = self.resolve(scope_locator) if scope_locator else auto.GetRootControl()
        matches = []
        for control in self._walk(root, max_depth=max_depth, max_results=5000):
            item = descriptor(control)
            if self._matches_query(item, query):
                matches.append(self._snapshot(control))
                if len(matches) >= max(1, min(limit, 100)):
                    break
        return matches

    def _walk(self, root: Any, max_depth: int, max_results: int) -> list[Any]:
        found = []
        queue = deque((child, 1) for child in root.GetChildren())
        while queue and len(found) < max_results:
            control, depth = queue.popleft()
            found.append(control)
            if depth >= max_depth:
                continue
            try:
                children = control.GetChildren()
            except (AttributeError, COMError, OSError, RuntimeError):
                children = []
            queue.extend((child, depth + 1) for child in children)
        return found

    @staticmethod
    def _matches_query(item: dict[str, Any], query: dict[str, Any]) -> bool:
        for field, wanted in query.items():
            if field == "name_contains":
                if str(wanted).casefold() not in str(item.get("name", "")).casefold():
                    return False
            elif item.get(field) != wanted:
                return False
        return True

    def focus(
        self, locator: dict[str, Any], variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        control = self._action_target(locator, variables)
        control.SetFocus()
        return self._snapshot(control)

    def click(
        self, locator: dict[str, Any], variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        control = self._action_target(locator, variables)
        snapshot = self._snapshot(control)
        pattern = control.GetPattern(auto.PatternId.InvokePattern)
        if pattern is not None:
            pattern.Invoke()
            snapshot["action"] = "invoked"
            return snapshot
        top_level = control.GetTopLevelControl()
        if top_level is not None:
            top_level.SetActive()
        control.SetFocus()
        control.Click()
        snapshot["action"] = "clicked"
        return snapshot

    def invoke(
        self, locator: dict[str, Any], variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        control = self._action_target(locator, variables)
        snapshot = self._snapshot(control)
        pattern = control.GetPattern(auto.PatternId.InvokePattern)
        if pattern is None:
            raise AutomationError("Element does not support InvokePattern")
        pattern.Invoke()
        snapshot["action"] = "invoked"
        return snapshot

    def set_value(
        self,
        locator: dict[str, Any],
        value: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        control = self._action_target(locator, variables)
        pattern = control.GetPattern(auto.PatternId.ValuePattern)
        if pattern is None:
            raise AutomationError("Element does not support ValuePattern")
        if pattern.IsReadOnly:
            raise AutomationError("Element value is read-only")
        pattern.SetValue(value)
        return self._snapshot(control)

    def send_keys(
        self,
        locator: dict[str, Any],
        text: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if len(text) > 4000:
            raise AutomationError("Text exceeds the 4000 character limit")
        control = self._action_target(locator, variables)
        control.SetFocus()
        control.SendKeys(text, interval=0.01, waitTime=0.2)
        return self._snapshot(control)

    def _action_target(
        self, locator: dict[str, Any], variables: dict[str, Any] | None = None
    ) -> Any:
        control = self.resolve(locator, variables)
        snapshot = self._snapshot(control, include_locator=False)
        if snapshot.get("enabled") is False:
            raise AutomationError("Element is disabled")
        if snapshot.get("offscreen") is True:
            raise AutomationError("Element is offscreen")
        bounds = snapshot.get("bounds")
        if not bounds or bounds["width"] <= 0 or bounds["height"] <= 0:
            raise AutomationError("Element has no actionable bounds")
        return control

    def highlight(
        self,
        locator: dict[str, Any],
        seconds: float = 0.8,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        control = self.resolve(locator, variables)
        snapshot = self._snapshot(control)
        bounds = snapshot.get("bounds")
        if not bounds:
            raise AutomationError("Element has no visible bounds")
        self._draw_xor_rectangle(bounds, max(0.1, min(seconds, 3.0)))
        return snapshot

    @staticmethod
    def _draw_xor_rectangle(bounds: dict[str, int], seconds: float) -> None:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        pen = gdi32.CreatePen(0, 5, 0x0000FF)
        old_pen = gdi32.SelectObject(hdc, pen)
        old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(5))
        old_mode = gdi32.SetROP2(hdc, 10)

        def draw() -> None:
            gdi32.Rectangle(
                hdc,
                bounds["left"],
                bounds["top"],
                bounds["right"],
                bounds["bottom"],
            )

        try:
            draw()
            time.sleep(seconds)
            draw()
        finally:
            gdi32.SetROP2(hdc, old_mode)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.SelectObject(hdc, old_pen)
            gdi32.DeleteObject(pen)
            user32.ReleaseDC(0, hdc)
