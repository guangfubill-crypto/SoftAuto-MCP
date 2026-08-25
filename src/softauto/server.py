from __future__ import annotations

import os
import platform
import re
from typing import Any

import uiautomation as auto
from mcp.server import MCPServer

from softauto.element_store import ElementStore
from softauto.integrations import catalog
from softauto.project_store import ProjectStore
from softauto.web_bridge import WebAutomationError, ensure_web_bridge_server
from softauto.windows_uia import AutomationError, WindowsUIABackend

ALLOW_ACTIONS = os.environ.get("SOFTAUTO_ALLOW_ACTIONS", "0") == "1"
backend = WindowsUIABackend() if platform.system() == "Windows" else None
project_store = ProjectStore()
element_store = ElementStore(project_store=project_store)

mcp = MCPServer(
    "Software Automation",
    instructions=(
        "Inspect first, then operate only through a returned element locator. "
        "Never treat a successful click as proof of a business outcome. "
        "Re-inspect the resulting UI state after every consequential action."
    ),
)


def _require_backend() -> WindowsUIABackend:
    if backend is None:
        raise AutomationError("This build currently provides the Windows UI Automation backend")
    return backend


def _require_actions() -> None:
    if not ALLOW_ACTIONS:
        raise AutomationError(
            "UI-changing actions are disabled. Start the MCP server with SOFTAUTO_ALLOW_ACTIONS=1."
        )


def _result(call: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "result": call()}
    except (AutomationError, WebAutomationError, KeyError, OSError, TypeError, ValueError) as exc:
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}


def _uia_result(call: Any) -> dict[str, Any]:
    """Run one MCP UIA operation with COM initialized in its worker thread."""

    return _result(lambda: _run_initialized_uia(call))


def _run_initialized_uia(call: Any) -> Any:
    with auto.UIAutomationInitializerInThread():
        return call()


def _is_web_locator(locator: dict[str, Any]) -> bool:
    return locator.get("backend") == "browser-dom"


def _web_locator(locator: dict[str, Any], variables: dict[str, Any] | None) -> dict[str, Any]:
    values = variables or {}

    def substitute(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: substitute(item) for key, item in value.items()}
        if isinstance(value, list):
            return [substitute(item) for item in value]
        if not isinstance(value, str):
            return value

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in values:
                raise ValueError(f"Missing selector variable: {name}")
            return str(values[name])

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, value)

    return substitute(locator)


def _resolve(locator: dict[str, Any], variables: dict[str, Any] | None = None) -> Any:
    if _is_web_locator(locator):
        return ensure_web_bridge_server().request(
            "validate", {"locator": _web_locator(locator, variables)}, timeout=30
        )
    return _run_initialized_uia(lambda: _require_backend().get_element(locator, variables))


def _operate_web(
    command: str,
    locator: dict[str, Any],
    variables: dict[str, Any] | None = None,
    **payload: Any,
) -> Any:
    return ensure_web_bridge_server().request(
        command,
        {"locator": _web_locator(locator, variables), **payload},
        timeout=30,
    )


@mcp.tool()
def automation_status() -> dict[str, Any]:
    """Report the active automation backend and whether UI-changing actions are enabled."""
    try:
        web = ensure_web_bridge_server().status()
    except WebAutomationError as exc:
        web = {"ok": False, "extension_connected": False, "message": str(exc)}
    return {
        "ok": True,
        "platform": platform.system(),
        "backend": backend.backend_name if backend else None,
        "actions_enabled": ALLOW_ACTIONS,
        "active_project": project_store.active_project(),
        "element_library": str(element_store.path),
        "web_dom": web,
    }


@mcp.tool()
def integration_catalog() -> dict[str, Any]:
    """List the mature open-source components used by the automation stack and their roles."""
    return {"ok": True, "integrations": catalog()}


@mcp.tool()
def list_element_projects() -> dict[str, Any]:
    """List local element projects. Each project owns an independent element library."""
    return _result(project_store.list_projects)


@mcp.tool()
def get_active_element_project() -> dict[str, Any]:
    """Return the active element project and its library path."""
    return _result(project_store.active_project)


@mcp.tool()
def list_saved_elements() -> dict[str, Any]:
    """List saved elements with their stable tree paths and reusable locators."""
    return _result(lambda: element_store.list_elements(include_paths=True))


@mcp.tool()
def list_element_tree() -> dict[str, Any]:
    """List saved folders and elements as a Blue Prism-style hierarchy."""
    return _result(element_store.tree)


@mcp.tool()
def get_saved_element(element_id_or_name: str) -> dict[str, Any]:
    """Get an element by stable id, unique name, or full path such as Login/Username."""
    return _result(lambda: element_store.get(element_id_or_name))


@mcp.tool()
def validate_saved_element(
    element_id_or_name: str, variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Resolve a saved element against the live UI and return its fresh properties."""
    return _result(lambda: _resolve(element_store.get(element_id_or_name)["locator"], variables))


@mcp.tool()
def list_windows(limit: int = 100) -> dict[str, Any]:
    """List visible top-level UI Automation elements and return reusable locators."""
    return _uia_result(lambda: _require_backend().list_windows(limit))


@mcp.tool()
def inspect_point(x: int | None = None, y: int | None = None) -> dict[str, Any]:
    """Inspect the element at a screen point, or at the current cursor when coordinates are omitted."""
    return _uia_result(lambda: _require_backend().element_from_point(x, y))


@mcp.tool()
def get_element(locator: dict[str, Any], variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve a previously returned locator against the current UI and return fresh state."""
    return _result(lambda: _resolve(locator, variables))


@mcp.tool()
def get_children(locator: dict[str, Any], limit: int = 100) -> dict[str, Any]:
    """Return direct child elements beneath a resolved element."""
    return _uia_result(lambda: _require_backend().children(locator, limit))


@mcp.tool()
def find_elements(
    query: dict[str, Any],
    scope_locator: dict[str, Any] | None = None,
    max_depth: int = 12,
    limit: int = 20,
) -> dict[str, Any]:
    """Find UIA elements by stable properties, optionally within a previously resolved scope."""
    return _uia_result(
        lambda: _require_backend().find_elements(query, scope_locator, max_depth, limit)
    )


@mcp.tool()
def highlight_element(
    locator: dict[str, Any],
    seconds: float = 0.8,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Draw a temporary outline around a resolved element without changing application state."""
    if _is_web_locator(locator):
        return _result(lambda: _operate_web("highlight", locator, variables))
    return _uia_result(lambda: _require_backend().highlight(locator, seconds, variables))


@mcp.tool()
def focus_element(
    locator: dict[str, Any], variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Move keyboard focus to a resolved element. Requires actions to be enabled."""
    if _is_web_locator(locator):
        return _result(lambda: (_require_actions(), _operate_web("focus", locator, variables))[1])
    return _uia_result(
        lambda: (_require_actions(), _require_backend().focus(locator, variables))[1]
    )


@mcp.tool()
def click_element(
    locator: dict[str, Any],
    confirm: bool = False,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Click the center of a resolved, enabled, visible element. Requires explicit confirmation."""
    if _is_web_locator(locator):
        return _result(
            lambda: (
                _require_actions(),
                confirm or (_ for _ in ()).throw(AutomationError("Click requires confirm=true")),
                _operate_web("click", locator, variables),
            )[2]
        )
    return _uia_result(
        lambda: (
            _require_actions(),
            confirm or (_ for _ in ()).throw(AutomationError("Click requires confirm=true")),
            _require_backend().click(locator, variables),
        )[2]
    )


@mcp.tool()
def invoke_element(
    locator: dict[str, Any],
    confirm: bool = False,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke an element through UI Automation InvokePattern. Requires explicit confirmation."""
    if _is_web_locator(locator):
        return _result(
            lambda: (
                _require_actions(),
                confirm or (_ for _ in ()).throw(AutomationError("Invoke requires confirm=true")),
                _operate_web("invoke", locator, variables),
            )[2]
        )
    return _uia_result(
        lambda: (
            _require_actions(),
            confirm or (_ for _ in ()).throw(AutomationError("Invoke requires confirm=true")),
            _require_backend().invoke(locator, variables),
        )[2]
    )


@mcp.tool()
def set_element_value(
    locator: dict[str, Any],
    value: str,
    confirm: bool = False,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set an editable element through ValuePattern. Requires explicit confirmation."""
    if _is_web_locator(locator):
        return _result(
            lambda: (
                _require_actions(),
                confirm
                or (_ for _ in ()).throw(AutomationError("Set value requires confirm=true")),
                _operate_web("set_value", locator, variables, value=value),
            )[2]
        )
    return _uia_result(
        lambda: (
            _require_actions(),
            confirm or (_ for _ in ()).throw(AutomationError("Set value requires confirm=true")),
            _require_backend().set_value(locator, value, variables),
        )[2]
    )


@mcp.tool()
def send_element_keys(
    locator: dict[str, Any],
    text: str,
    confirm: bool = False,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Focus a resolved element and send bounded text input. Requires explicit confirmation."""
    if _is_web_locator(locator):
        return _result(
            lambda: (
                _require_actions(),
                confirm
                or (_ for _ in ()).throw(AutomationError("Send keys requires confirm=true")),
                _operate_web("send_keys", locator, variables, text=text),
            )[2]
        )
    return _uia_result(
        lambda: (
            _require_actions(),
            confirm or (_ for _ in ()).throw(AutomationError("Send keys requires confirm=true")),
            _require_backend().send_keys(locator, text, variables),
        )[2]
    )
