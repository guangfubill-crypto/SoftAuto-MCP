from __future__ import annotations

import hashlib
import json
import re
from fnmatch import fnmatchcase
from typing import Any, Protocol

from comtypes import COMError


class ControlLike(Protocol):
    Name: str
    AutomationId: str
    ClassName: str
    ControlTypeName: str
    FrameworkId: str
    ProcessId: int
    NativeWindowHandle: int

    def GetChildren(self) -> list[ControlLike]: ...

    def GetParentControl(self) -> ControlLike | None: ...

    def GetTopLevelControl(self) -> ControlLike | None: ...


_DYNAMIC_NAME_TOKEN = re.compile(
    r"(?<![\w])(?:[A-Za-z_-]*\d[A-Za-z0-9_.:/-]*)(?![\w])",
    re.UNICODE,
)
_VARIABLE_TOKEN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
SELECTOR_FIELDS = (
    "automation_id",
    "name",
    "name_prefix",
    "class_name",
    "control_type",
    "framework_id",
    "process_id",
    "native_window_handle",
)


def safe_property(control: Any, name: str, default: Any = "") -> Any:
    try:
        return getattr(control, name)
    except (AttributeError, COMError, OSError, RuntimeError):
        return default


def descriptor(control: ControlLike) -> dict[str, Any]:
    result = {
        "automation_id": str(safe_property(control, "AutomationId")),
        "name": str(safe_property(control, "Name")),
        "class_name": str(safe_property(control, "ClassName")),
        "control_type": str(safe_property(control, "ControlTypeName")),
        "framework_id": str(safe_property(control, "FrameworkId")),
        "process_id": int(safe_property(control, "ProcessId", 0) or 0),
        "native_window_handle": int(safe_property(control, "NativeWindowHandle", 0) or 0),
    }
    name_prefix = dynamic_name_prefix(result["name"])
    if name_prefix:
        result["name_prefix"] = name_prefix
    return result


def dynamic_name_prefix(name: str) -> str:
    """Return the stable text before a likely generated id, number, or date token."""

    match = _DYNAMIC_NAME_TOKEN.search(name)
    if not match:
        return ""
    prefix = name[: match.start()].rstrip()
    return prefix if len(prefix) >= 3 else ""


def selector_properties(item: dict[str, Any]) -> dict[str, Any]:
    properties = {field: item.get(field) for field in SELECTOR_FIELDS}
    if not properties.get("name_prefix"):
        properties["name_prefix"] = dynamic_name_prefix(str(properties.get("name") or ""))
    return properties


def recommended_selector_fields(item: dict[str, Any]) -> list[str]:
    properties = selector_properties(item)
    selected = []
    if properties.get("automation_id"):
        selected.append("automation_id")
    if properties.get("name_prefix"):
        selected.append("name_prefix")
    elif properties.get("name"):
        selected.append("name")
    selected.extend(
        field for field in ("class_name", "control_type", "framework_id") if properties.get(field)
    )
    return selected


def selected_descriptor(item: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
    return configured_descriptor(item, fields)


def configured_descriptor(
    item: dict[str, Any],
    fields: list[str] | None,
    values: dict[str, Any] | None = None,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    properties = selector_properties(item)
    active_fields = fields if fields is not None else recommended_selector_fields(item)
    configured_values = values or {}
    selected = {}
    for field in active_fields:
        if field not in SELECTOR_FIELDS:
            continue
        value = configured_values.get(field, properties.get(field))
        value = resolve_variables(value, variables)
        if value not in (None, "", 0):
            selected[field] = value
    if "sibling_index" in item:
        selected["sibling_index"] = item["sibling_index"]
    return selected


def resolve_variables(value: Any, variables: dict[str, Any] | None) -> Any:
    if not isinstance(value, str) or "${" not in value:
        return value

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if variables is None or name not in variables:
            raise ValueError(f"Missing selector variable: {name}")
        return str(variables[name])

    return _VARIABLE_TOKEN.sub(replace, value)


def selector_variable_names(locator: dict[str, Any]) -> list[str]:
    names = set()

    def visit(value: Any) -> None:
        if isinstance(value, str):
            names.update(_VARIABLE_TOKEN.findall(value))
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(locator.get("selector", {}).get("values", {}))
    return sorted(names)


def ensure_selector(locator: dict[str, Any]) -> dict[str, Any]:
    selector = locator.setdefault("selector", {})
    selector.setdefault("window", recommended_selector_fields(locator.get("window", {})))
    selector.setdefault(
        "path", [recommended_selector_fields(item) for item in locator.get("path", [])]
    )
    selector.setdefault("target", recommended_selector_fields(locator.get("target", {})))
    values = selector.setdefault("values", {})
    values.setdefault("window", {})
    values.setdefault("path", [{} for _item in locator.get("path", [])])
    values.setdefault("target", {})
    return locator


def descriptor_score(expected: dict[str, Any], actual: dict[str, Any]) -> int:
    expected_id = str(expected.get("automation_id") or "")
    actual_id = str(actual.get("automation_id") or "")
    if expected_id and actual_id and not _property_matches(expected_id, actual_id):
        return -1

    expected_name = str(expected.get("name") or "")
    actual_name = str(actual.get("name") or "")
    expected_prefix = str(expected.get("name_prefix") or dynamic_name_prefix(expected_name))
    name_matches = bool(expected_name and _property_matches(expected_name, actual_name))
    prefix_matches = bool(expected_prefix and actual_name.startswith(expected_prefix))
    if not expected_id and expected_name and not (name_matches or prefix_matches):
        return -1

    score = 0
    weights = {
        "automation_id": 100,
        "class_name": 30,
        "control_type": 25,
        "framework_id": 10,
        "process_id": 2,
        "native_window_handle": 1,
    }
    for field, weight in weights.items():
        wanted = expected.get(field)
        if wanted not in (None, "", 0) and _property_matches(wanted, actual.get(field)):
            score += weight
    if name_matches:
        score += 35
    elif prefix_matches:
        score += 30
    return score


def _property_matches(expected: Any, actual: Any) -> bool:
    if (
        isinstance(expected, str)
        and isinstance(actual, str)
        and any(token in expected for token in ("*", "?"))
    ):
        return fnmatchcase(actual, expected)
    return expected == actual


def _same_control(left: ControlLike, right: ControlLike) -> bool:
    if left is right:
        return True
    left_item = descriptor(left)
    right_item = descriptor(right)
    left_handle = left_item.get("native_window_handle")
    right_handle = right_item.get("native_window_handle")
    if left_handle and right_handle:
        return bool(
            left_handle == right_handle
            and left_item.get("process_id") == right_item.get("process_id")
        )
    return left_item == right_item


def _same_sibling_family(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    automation_id = expected.get("automation_id")
    if automation_id:
        return automation_id == actual.get("automation_id")
    compared = ("class_name", "control_type", "framework_id")
    populated = [field for field in compared if expected.get(field)]
    return bool(populated) and all(expected[field] == actual.get(field) for field in populated)


def _stable_segment(control: ControlLike) -> dict[str, Any]:
    segment = descriptor(control)
    parent = control.GetParentControl()
    segment["sibling_index"] = 0
    if parent is not None:
        peers = []
        try:
            peers = [
                item
                for item in parent.GetChildren()
                if _same_sibling_family(segment, descriptor(item))
            ]
        except (AttributeError, OSError, RuntimeError):
            peers = []
        for index, peer in enumerate(peers):
            if _same_control(peer, control):
                segment["sibling_index"] = index
                break
    return segment


def _minimum_score(expected: dict[str, Any]) -> int:
    if expected.get("automation_id"):
        return 100
    populated = sum(bool(expected.get(field)) for field in ("name", "class_name", "control_type"))
    return 25 if populated == 1 else 50


def build_locator(control: ControlLike) -> dict[str, Any]:
    top = control.GetTopLevelControl() or control
    path: list[dict[str, Any]] = []
    current: ControlLike | None = control
    visited = 0
    while current is not None and not _same_control(current, top) and visited < 64:
        path.append(_stable_segment(current))
        current = current.GetParentControl()
        visited += 1
    path.reverse()
    locator: dict[str, Any] = {
        "backend": "windows-uia",
        "version": 1,
        "window": descriptor(top),
        "path": path,
        "target": descriptor(control),
    }
    ensure_selector(locator)
    canonical = json.dumps(locator, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    locator["locator_id"] = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return locator


def choose_best(
    expected: dict[str, Any],
    candidates: list[ControlLike],
    sibling_index: int | None = None,
) -> ControlLike | None:
    ranked = sorted(
        (
            (descriptor_score(expected, descriptor(item)), index, item)
            for index, item in enumerate(candidates)
        ),
        key=lambda row: (row[0], -row[1]),
        reverse=True,
    )
    ranked = [row for row in ranked if row[0] >= _minimum_score(expected)]
    if not ranked:
        return None
    best_score = ranked[0][0]
    tied = [row[2] for row in ranked if row[0] == best_score]
    if sibling_index is not None and 0 <= sibling_index < len(tied):
        return tied[sibling_index]
    return tied[0]


def resolve_path(window: ControlLike, path: list[dict[str, Any]]) -> ControlLike | None:
    current = window
    for segment in path:
        try:
            children = current.GetChildren()
        except (AttributeError, OSError, RuntimeError):
            return None
        current = choose_best(segment, children, segment.get("sibling_index"))
        if current is None:
            return None
    return current


def path_below_window(window: ControlLike, path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Trim legacy paths that accidentally include desktop, owner, and window segments."""

    for index, segment in enumerate(path):
        if choose_best(segment, [window]) is not None:
            return path[index + 1 :]
    return path
