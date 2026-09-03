from __future__ import annotations

import copy
import ctypes
import json
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

import uiautomation as auto
from comtypes import COMError
from pynput import keyboard, mouse

from softauto import __version__
from softauto.element_store import ElementStore
from softauto.flauinspect import main as launch_flauinspect
from softauto.i18n import (
    LANGUAGE_NAMES,
    load_language,
    responsive_layout_mode,
    responsive_window_metrics,
    save_language,
    translate,
)
from softauto.live_highlight import OverlayHighlighter
from softauto.locator import (
    STABLE_SELECTOR_FIELDS,
    ensure_selector,
    recommended_selector_fields,
    selector_profile,
    selector_properties,
    selector_variable_names,
)
from softauto.mcp_config import agent_mcp_config_json, mcp_executable_path
from softauto.project_store import ProjectStore
from softauto.runtime_paths import bundled_resource
from softauto.web_bridge import WebAutomationError, ensure_web_bridge_server
from softauto.web_extension import open_extension_installation, prepare_local_extension
from softauto.windows_uia import AutomationError, WindowsUIABackend

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
VK_CONTROL = 0x11
BRAND_NAME = "零禾一智能"
PRODUCT_NAME = "SoftAuto"
APP_TITLE = f"{BRAND_NAME} · {PRODUCT_NAME} 软件自动化"
COLORS = {
    "teal": "#0F5B50",
    "teal_hover": "#0A463E",
    "green": "#2FA36B",
    "green_soft": "#E7F5EE",
    "canvas": "#F3F6F4",
    "surface": "#FFFFFF",
    "border": "#D8E2DD",
    "text": "#17312B",
    "muted": "#64756F",
    "warning": "#9A6700",
    "warning_soft": "#FFF4D6",
}
FIELD_LABELS = {
    "automation_id": "AutomationId",
    "name": "field_name",
    "name_prefix": "field_name_prefix",
    "class_name": "ClassName",
    "control_type": "ControlType",
    "framework_id": "FrameworkId",
    "process_id": "ProcessId",
    "native_window_handle": "NativeWindowHandle",
}


def enable_per_monitor_dpi_awareness() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


class ElementPickerApp:
    def __init__(self) -> None:
        enable_per_monitor_dpi_awareness()
        self.backend = WindowsUIABackend()
        self.projects = ProjectStore()
        self.store = ElementStore(project_store=self.projects)
        self.events: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self.active = threading.Event()
        self.closed = threading.Event()
        self._suppress_left_until_up = False
        self._hover_signature: tuple[Any, ...] | None = None
        self._hover_text = ""
        self.capture_folder_id: str | None = None
        self._drag_source: str | None = None
        self.web_bridge = None
        self.language = load_language()
        self._web_connected = False
        self._layout_mode: str | None = None
        self._responsive_after_id: str | None = None

        self.root = tk.Tk()
        self.root.title(self._t("app_title"))
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width, height, minimum_width, minimum_height = responsive_window_metrics(
            screen_width, screen_height
        )
        left = max(0, (screen_width - width) // 2)
        top = max(0, (screen_height - height) // 2)
        self.root.geometry(f"{width}x{height}+{left}+{top}")
        self.root.minsize(minimum_width, minimum_height)
        self.root.configure(background=COLORS["canvas"])
        self._apply_branding()
        self.highlighter = OverlayHighlighter(self.root)
        self._build_ui()
        try:
            self.web_bridge = ensure_web_bridge_server()
        except WebAutomationError:
            pass

        self.mouse_listener = mouse.Listener(
            on_click=lambda *_args: None,
            win32_event_filter=self._mouse_filter,
        )
        self.keyboard_listener = keyboard.Listener(on_press=self._key_press)
        self.mouse_listener.start()
        self.keyboard_listener.start()
        self.hover_thread = threading.Thread(target=self._hover_loop, daemon=True)
        self.hover_thread.start()

        self.root.after(50, self._poll_events)
        self.root.after(500, self._refresh_web_status)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh_projects()
        self.refresh_library()

    def _t(self, key: str, **values: Any) -> str:
        return translate(key, self.language, **values)

    def _l(self, chinese: str, english: str) -> str:
        return english if self.language == "en" else chinese

    def _brand_display_name(self) -> str:
        return self._l(BRAND_NAME, "Lingheyi Intelligence")

    def _apply_branding(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background=COLORS["surface"])
        style.configure("TLabel", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure("App.TFrame", background=COLORS["canvas"])
        style.configure("Surface.TFrame", background=COLORS["surface"])
        style.configure("Header.TFrame", background=COLORS["teal"])
        style.configure(
            "HeaderTitle.TLabel",
            background=COLORS["teal"],
            foreground="#FFFFFF",
            font=("Microsoft YaHei UI", 16, "bold"),
        )
        style.configure(
            "HeaderSubtitle.TLabel",
            background=COLORS["teal"],
            foreground="#CFE7DF",
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Section.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["muted"],
        )
        style.configure(
            "Status.TLabel",
            background=COLORS["canvas"],
            foreground=COLORS["muted"],
            padding=(12, 5),
        )
        style.configure(
            "Connected.TLabel",
            background=COLORS["green_soft"],
            foreground=COLORS["teal"],
            padding=(12, 6),
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        style.configure(
            "Disconnected.TLabel",
            background=COLORS["warning_soft"],
            foreground=COLORS["warning"],
            padding=(12, 6),
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        style.configure(
            "TButton",
            background="#FFFFFF",
            foreground=COLORS["text"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            padding=(12, 7),
        )
        style.map(
            "TButton",
            background=[("active", "#EDF3F0"), ("pressed", "#E2ECE7")],
            bordercolor=[("focus", COLORS["green"])],
        )
        style.configure(
            "Primary.TButton",
            background=COLORS["teal"],
            foreground="#FFFFFF",
            bordercolor=COLORS["teal"],
            lightcolor=COLORS["teal"],
            darkcolor=COLORS["teal"],
            padding=(14, 8),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", COLORS["teal_hover"]), ("pressed", "#073A34")],
            foreground=[("disabled", "#D4DFDB")],
        )
        style.configure(
            "Card.TLabelframe",
            background=COLORS["surface"],
            bordercolor=COLORS["border"],
            relief="solid",
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        style.configure(
            "Treeview",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=30,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#EAF1EE",
            foreground=COLORS["text"],
            padding=(8, 8),
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        style.map("Treeview", background=[("selected", COLORS["teal"])])
        icon_path = bundled_resource("assets", "brand-mark.png")
        if icon_path.is_file():
            self.brand_icon = tk.PhotoImage(file=icon_path).subsample(16, 16)
            self.root.iconphoto(True, self.brand_icon)
        header_icon_path = bundled_resource("assets", "brand-header.png")
        if header_icon_path.is_file():
            self.header_brand_icon = tk.PhotoImage(file=header_icon_path)

    def _build_ui(self) -> None:
        self.header = ttk.Frame(self.root, style="Header.TFrame", padding=(20, 14))
        self.header.pack(fill=tk.X)
        if hasattr(self, "header_brand_icon"):
            ttk.Label(
                self.header,
                image=self.header_brand_icon,
                background=COLORS["teal"],
            ).pack(side=tk.LEFT, padx=(0, 12))
        self.brand_copy = ttk.Frame(self.header, style="Header.TFrame")
        self.brand_copy.pack(side=tk.LEFT)
        self.brand_title = ttk.Label(
            self.brand_copy, text=self._brand_display_name(), style="HeaderTitle.TLabel"
        )
        self.brand_title.pack(anchor="w")
        self.header_subtitle = ttk.Label(
            self.brand_copy,
            text=self._t("tagline"),
            style="HeaderSubtitle.TLabel",
        )
        self.header_subtitle.pack(anchor="w", pady=(2, 0))
        self.header_controls = ttk.Frame(self.header, style="Header.TFrame")
        self.header_controls.pack(side=tk.RIGHT)
        self.language_name = tk.StringVar(value=LANGUAGE_NAMES[self.language])
        self.language_picker = ttk.Combobox(
            self.header_controls,
            textvariable=self.language_name,
            values=list(LANGUAGE_NAMES.values()),
            state="readonly",
            width=10,
        )
        self.language_picker.pack(side=tk.RIGHT, padx=(10, 0))
        self.language_picker.bind("<<ComboboxSelected>>", self.change_language)
        self.web_status = ttk.Label(
            self.header_controls,
            text=self._t("web_checking"),
            style="Disconnected.TLabel",
        )
        self.web_status.pack(side=tk.RIGHT)

        self.project_bar = ttk.Frame(self.root, style="Surface.TFrame", padding=(13, 9))
        self.project_bar.pack(fill=tk.X, padx=16, pady=(14, 8))
        self.project_selector_frame = ttk.Frame(self.project_bar, style="Surface.TFrame")
        self.project_selector_frame.columnconfigure(1, weight=1)
        self.project_label = ttk.Label(
            self.project_selector_frame,
            text=self._t("current_project"),
            style="Section.TLabel",
        )
        self.project_label.grid(row=0, column=0, sticky="w")
        self.project_name = tk.StringVar()
        self.project_picker = ttk.Combobox(
            self.project_selector_frame,
            textvariable=self.project_name,
            state="readonly",
            width=18,
        )
        self.project_picker.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.project_picker.bind("<<ComboboxSelected>>", self.switch_project)
        self.project_actions_frame = ttk.Frame(self.project_bar, style="Surface.TFrame")
        self.project_action_buttons = [
            ttk.Button(
                self.project_actions_frame,
                text=self._t("new_project"),
                command=self.create_project,
            ),
            ttk.Button(
                self.project_actions_frame,
                text=self._t("import"),
                command=self.import_project,
            ),
            ttk.Button(
                self.project_actions_frame,
                text=self._t("export"),
                command=self.export_for_mcp,
            ),
            ttk.Button(
                self.project_actions_frame,
                text=self._t("mcp_config"),
                command=self.copy_mcp_config,
            ),
            ttk.Button(
                self.project_actions_frame,
                text=self._t("web_extension"),
                command=self.install_web_extension,
            ),
        ]

        self.toolbar = ttk.Frame(self.root, style="Surface.TFrame", padding=(13, 7))
        self.toolbar.pack(fill=tk.X, padx=16, pady=(0, 10))
        self.capture_actions_frame = ttk.Frame(self.toolbar, style="Surface.TFrame")
        self.capture_action_buttons = [
            ttk.Button(
                self.capture_actions_frame,
                text=self._t("pick_desktop"),
                command=self.start_picking,
                style="Primary.TButton",
            ),
            ttk.Button(
                self.capture_actions_frame,
                text=self._t("pick_web"),
                command=self.start_web_picking,
                style="Primary.TButton",
            ),
        ]
        self.manage_actions_frame = ttk.Frame(self.toolbar, style="Surface.TFrame")
        self.manage_action_buttons = [
            ttk.Button(
                self.manage_actions_frame,
                text=self._t("new_folder"),
                command=self.create_folder,
            ),
            ttk.Button(
                self.manage_actions_frame,
                text=self._t("validate"),
                command=self.validate_selected,
            ),
            ttk.Button(
                self.manage_actions_frame,
                text=self._t("rename"),
                command=self.rename_selected,
            ),
            ttk.Button(
                self.manage_actions_frame,
                text=self._t("delete"),
                command=self.delete_selected,
            ),
            ttk.Button(
                self.manage_actions_frame,
                text=self._t("copy_locator"),
                command=self.copy_locator,
            ),
            ttk.Button(
                self.manage_actions_frame,
                text=self._t("inspect"),
                command=launch_flauinspect,
            ),
        ]

        panes = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))
        self.library_frame = ttk.Labelframe(
            panes, text=self._t("element_library"), padding=10, style="Card.TLabelframe"
        )
        self.details_frame = ttk.Labelframe(
            panes, text=self._t("locator_properties"), padding=10, style="Card.TLabelframe"
        )
        panes.add(self.library_frame, weight=2)
        panes.add(self.details_frame, weight=3)

        columns = ("type", "automation_id", "window")
        self.library = ttk.Treeview(self.library_frame, columns=columns, show="tree headings")
        self.library.heading("#0", text=self._t("name"))
        self.library.column("#0", width=235, stretch=True)
        for column, title, width in (
            ("type", self._t("type"), 115),
            ("automation_id", "AutomationId", 140),
            ("window", self._t("window"), 170),
        ):
            self.library.heading(column, text=title)
            self.library.column(column, width=width, stretch=True)
        self.library.pack(fill=tk.BOTH, expand=True)
        self.library.bind("<<TreeviewSelect>>", self._show_selected)
        self.library.bind("<Double-1>", lambda _event: self.rename_selected())
        self.library.bind("<ButtonPress-1>", self._begin_tree_drag, add="+")
        self.library.bind("<ButtonRelease-1>", self._finish_tree_drag, add="+")

        self._build_details_panel(self.details_frame)

        status_bar = ttk.Frame(self.root, style="App.TFrame")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(0, 8), before=panes)
        self.status = ttk.Label(
            status_bar,
            text=self._t("ready"),
            style="Status.TLabel",
        )
        self.status.pack(side=tk.LEFT)
        self.footer_brand = ttk.Label(
            status_bar,
            text=f"{self._brand_display_name()} · {PRODUCT_NAME} {__version__}",
            style="Status.TLabel",
        )
        self.footer_brand.pack(side=tk.RIGHT)
        self.root.bind("<Configure>", self._on_root_configure, add="+")
        self.root.after_idle(self._apply_responsive_layout)

    @staticmethod
    def _arrange_buttons(frame: ttk.Frame, buttons: list[ttk.Button], columns: int) -> None:
        for button in buttons:
            button.grid_forget()
        for column in range(8):
            frame.columnconfigure(column, weight=0, uniform="")
        for index, button in enumerate(buttons):
            row, column = divmod(index, columns)
            frame.columnconfigure(column, weight=1, uniform="responsive-buttons")
            button.grid(
                row=row,
                column=column,
                sticky="ew",
                padx=3,
                pady=3,
            )

    def _on_root_configure(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self.root:
            return
        if self._responsive_after_id is not None:
            self.root.after_cancel(self._responsive_after_id)
        self._responsive_after_id = self.root.after(70, self._apply_responsive_layout)

    def _apply_responsive_layout(self) -> None:
        self._responsive_after_id = None
        window_width = self.root.winfo_width()
        mode = responsive_layout_mode(window_width)
        english_toolbar_stacked = self.language == "en" and window_width < 1500
        layout_key = f"{mode}:{'stacked' if english_toolbar_stacked else 'inline'}"
        if layout_key == self._layout_mode:
            return
        self._layout_mode = layout_key
        for parent in (self.project_bar, self.toolbar):
            for column in range(2):
                parent.columnconfigure(column, weight=0)
        for frame in (
            self.project_selector_frame,
            self.project_actions_frame,
            self.capture_actions_frame,
            self.manage_actions_frame,
        ):
            frame.grid_forget()

        if mode == "wide":
            self.project_bar.columnconfigure(1, weight=1)
            self.project_selector_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            self.project_actions_frame.grid(row=0, column=1, sticky="ew")
            self._arrange_buttons(self.project_actions_frame, self.project_action_buttons, 5)
        else:
            self.project_bar.columnconfigure(0, weight=1)
            self.project_selector_frame.grid(row=0, column=0, sticky="ew")
            self.project_actions_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
            action_columns = 3 if mode == "narrow" else 5
            self._arrange_buttons(
                self.project_actions_frame, self.project_action_buttons, action_columns
            )

        if mode == "wide" and not english_toolbar_stacked:
            self.toolbar.columnconfigure(0, weight=2)
            self.toolbar.columnconfigure(1, weight=3)
            self.capture_actions_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            self.manage_actions_frame.grid(row=0, column=1, sticky="ew")
            self._arrange_buttons(self.capture_actions_frame, self.capture_action_buttons, 2)
            self._arrange_buttons(self.manage_actions_frame, self.manage_action_buttons, 6)
        else:
            self.toolbar.columnconfigure(0, weight=1)
            self.capture_actions_frame.grid(row=0, column=0, sticky="ew")
            self.manage_actions_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
            manage_columns = 3 if mode == "narrow" else 6
            self._arrange_buttons(self.capture_actions_frame, self.capture_action_buttons, 2)
            self._arrange_buttons(
                self.manage_actions_frame, self.manage_action_buttons, manage_columns
            )

        if mode == "narrow":
            self.header_subtitle.pack_forget()
            self.details_help.config(wraplength=320)
        else:
            if not self.header_subtitle.winfo_manager():
                self.header_subtitle.pack(anchor="w", pady=(2, 0))
            self.details_help.config(wraplength=480 if mode == "compact" else 600)
        self._render_web_status()

    def change_language(self, _event: object | None = None) -> None:
        selected = self.language_name.get()
        language = next(
            (code for code, name in LANGUAGE_NAMES.items() if name == selected),
            self.language,
        )
        if language == self.language:
            return
        self.language = language
        save_language(language)
        self._update_language()

    def _update_language(self) -> None:
        self.root.title(self._t("app_title"))
        self.brand_title.config(text=self._brand_display_name())
        self.header_subtitle.config(text=self._t("tagline"))
        self.project_label.config(text=self._t("current_project"))
        for button, key in zip(
            self.project_action_buttons,
            ("new_project", "import", "export", "mcp_config", "web_extension"),
            strict=True,
        ):
            button.config(text=self._t(key))
        for button, key in zip(
            self.capture_action_buttons,
            ("pick_desktop", "pick_web"),
            strict=True,
        ):
            button.config(text=self._t(key))
        for button, key in zip(
            self.manage_action_buttons,
            ("new_folder", "validate", "rename", "delete", "copy_locator", "inspect"),
            strict=True,
        ):
            button.config(text=self._t(key))
        self.library_frame.config(text=self._t("element_library"))
        self.details_frame.config(text=self._t("locator_properties"))
        self.footer_brand.config(
            text=f"{self._brand_display_name()} · {PRODUCT_NAME} {__version__}"
        )
        self.library.heading("#0", text=self._t("name"))
        self.library.heading("type", text=self._t("type"))
        self.library.heading("window", text=self._t("window"))
        self.details_help.config(text=self._t("selector_help"))
        self.detail_action_buttons[0].config(text=self._t("recommended"))
        self.detail_action_buttons[1].config(text=self._t("save_properties"))
        self.detail_action_buttons[2].config(text=self._t("validate_plain"))
        self._render_web_status()
        self.status.config(text=self._t("ready"))
        selected = self.library.selection()
        self.refresh_library(select_iid=selected[0] if selected else None)
        if not selected:
            self._clear_details()
        self._layout_mode = None
        self._apply_responsive_layout()

    def _build_details_panel(self, parent: ttk.Frame) -> None:
        self.details_help = ttk.Label(
            parent,
            text=self._t("selector_help"),
            wraplength=600,
        )
        self.details_help.pack(fill=tk.X, pady=(0, 6))
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)
        self.details_canvas = tk.Canvas(
            container, highlightthickness=0, background=COLORS["surface"]
        )
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.details_canvas.yview)
        self.details_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.details_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.details_body = ttk.Frame(self.details_canvas)
        self.details_window = self.details_canvas.create_window(
            (0, 0), window=self.details_body, anchor="nw"
        )
        self.details_body.bind(
            "<Configure>",
            lambda _event: self.details_canvas.configure(
                scrollregion=self.details_canvas.bbox("all")
            ),
        )
        self.details_canvas.bind(
            "<Configure>",
            lambda event: self.details_canvas.itemconfigure(self.details_window, width=event.width),
        )

        actions = ttk.Frame(parent, padding=(0, 8, 0, 0))
        actions.pack(fill=tk.X)
        self.detail_action_buttons = [
            ttk.Button(
                actions,
                text=self._t("recommended"),
                command=self.reset_detail_recommended,
            ),
            ttk.Button(
                actions,
                text=self._t("save_properties"),
                command=self.save_detail_selector,
            ),
            ttk.Button(
                actions,
                text=self._t("validate_plain"),
                command=self.validate_selected,
            ),
        ]
        for index, button in enumerate(self.detail_action_buttons):
            button.pack(side=tk.LEFT, padx=(0 if index == 0 else 6, 0))
        self.detail_vars: dict[str, dict[str, tk.BooleanVar]] = {}
        self.detail_value_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.detail_sources: dict[str, dict[str, Any]] = {}
        self.detail_locator: dict[str, Any] | None = None
        self.detail_item_id: str | None = None
        self.web_selector_vars: list[tuple[tk.BooleanVar, tk.StringVar]] = []
        self._clear_details()

    def _refresh_web_status(self) -> None:
        connected = False
        try:
            if self.web_bridge is None:
                self.web_bridge = ensure_web_bridge_server()
            connected = bool(self.web_bridge.status().get("extension_connected"))
        except WebAutomationError:
            self.web_bridge = None
        self._web_connected = connected
        self._render_web_status()
        if not self.closed.is_set():
            self.root.after(1500, self._refresh_web_status)

    def _render_web_status(self) -> None:
        narrow = responsive_layout_mode(self.root.winfo_width()) == "narrow"
        if self._web_connected:
            key = "web_connected_short" if narrow else "web_connected"
        else:
            key = "web_disconnected_short" if narrow else "web_disconnected"
        self.web_status.config(
            text=self._t(key),
            style="Connected.TLabel" if self._web_connected else "Disconnected.TLabel",
        )

    def start_web_picking(self) -> None:
        self.capture_folder_id = self._selected_destination_folder()
        try:
            if self.web_bridge is None:
                self.web_bridge = ensure_web_bridge_server()
            if not self.web_bridge.status().get("extension_connected"):
                raise WebAutomationError(
                    self._l(
                        "网页扩展尚未连接，请先安装/更新扩展并在 Chrome 中重新加载",
                        "The web extension is not connected. Install or update it, reload it in Chrome, then try again.",
                    )
                )
        except WebAutomationError as exc:
            messagebox.showwarning(
                self._l("网页扩展未连接", "Web Extension Disconnected"), str(exc)
            )
            return
        self.status.config(
            text=self._l(
                "网页拾取中：请到 Chrome 按 Ctrl + 左键",
                "Web capture active: press Ctrl + left-click in Chrome",
            )
        )

        def worker() -> None:
            try:
                result = self.web_bridge.request("start_pick", {}, timeout=120)
                self.events.put(("web_capture", True, result))
            except WebAutomationError as exc:
                self.events.put(("web_capture", False, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def start_picking(self) -> None:
        if self.active.is_set():
            return
        self.capture_folder_id = self._selected_destination_folder()
        self.active.set()
        self.root.iconify()
        self._show_capture_bar()
        self.status.config(text=self._l("拾取中", "Capturing"))

    def stop_picking(self, message: str | None = None) -> None:
        self.active.clear()
        self.highlighter.clear()
        self._hover_signature = None
        if hasattr(self, "capture_bar") and self.capture_bar.winfo_exists():
            self.capture_bar.destroy()
        self.root.deiconify()
        self.root.lift()
        self.status.config(text=message or self._l("已取消拾取", "Capture cancelled"))

    def _show_capture_bar(self) -> None:
        self.capture_bar = tk.Toplevel(self.root)
        self.capture_bar.title(self._t("capture_title"))
        self.capture_bar.attributes("-topmost", True)
        self.capture_bar.resizable(False, False)
        frame = ttk.Frame(self.capture_bar, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=self._t("capture_help")).pack(side=tk.LEFT)
        ttk.Button(frame, text=self._t("cancel"), command=self.stop_picking).pack(
            side=tk.LEFT, padx=(12, 0)
        )
        self.hover_label = ttk.Label(self.capture_bar, text="", padding=(10, 0, 10, 8))
        self.hover_label.pack(fill=tk.X)
        self.capture_bar.update_idletasks()
        width = self.capture_bar.winfo_width()
        screen_width = self.capture_bar.winfo_screenwidth()
        self.capture_bar.geometry(f"+{max(0, (screen_width - width) // 2)}+30")

    def _mouse_filter(self, msg: int, data: Any) -> bool:
        if not self.active.is_set():
            return True
        ctrl_down = bool(ctypes.windll.user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
        if msg == WM_LBUTTONDOWN and ctrl_down:
            self._suppress_left_until_up = True
            self.events.put(("capture", int(data.pt.x), int(data.pt.y)))
            self.mouse_listener.suppress_event()
        elif msg == WM_LBUTTONUP and self._suppress_left_until_up:
            self._suppress_left_until_up = False
            self.mouse_listener.suppress_event()
        return True

    def _key_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if self.active.is_set() and key == keyboard.Key.esc:
            self.events.put(("cancel",))

    def _hover_loop(self) -> None:
        with auto.UIAutomationInitializerInThread():
            self._hover_loop_initialized()

    def _hover_loop_initialized(self) -> None:
        own_pid = os.getpid()
        while not self.closed.is_set():
            if not self.active.is_set():
                time.sleep(0.05)
                continue
            try:
                x, y = auto.GetCursorPos()
                control = auto.ControlFromPoint(x, y)
                if control is None or int(control.ProcessId or 0) == own_pid:
                    self.events.put(("highlight", None))
                    time.sleep(0.05)
                    continue
                item = self.backend.snapshot(control, include_locator=False)
                bounds = item.get("bounds")
                signature = (
                    item.get("process_id"),
                    item.get("native_window_handle"),
                    item.get("automation_id"),
                    item.get("name"),
                    tuple(bounds.values()) if bounds else None,
                )
                self.events.put(("highlight", bounds))
                if signature != self._hover_signature:
                    self._hover_signature = signature
                    text = f"{item.get('control_type')}  {item.get('name') or self._t('no_name')}"
                    self.events.put(("hover", text))
            except (AttributeError, AutomationError, COMError, OSError, RuntimeError):
                self.events.put(("highlight", None))
            time.sleep(0.06)

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "capture":
                    self._capture_at(int(event[1]), int(event[2]))
                elif event[0] == "cancel":
                    self.stop_picking()
                elif event[0] == "hover" and self.active.is_set():
                    self.hover_label.config(text=str(event[1]))
                elif event[0] == "highlight" and self.active.is_set():
                    self.highlighter.update(event[1])
                elif event[0] == "validation":
                    if event[1]:
                        diagnostics = event[4] if len(event) > 4 and isinstance(event[4], dict) else {}
                        count = int(diagnostics.get("match_count", 1) or 1)
                        self.highlighter.update(event[3].get("bounds"))
                        self.root.after(1400, self.highlighter.clear)
                        self.status.config(
                            text=self._l(
                                f"验证成功：{event[2]}（{count} 个匹配）",
                                f"Validation succeeded: {event[2]} ({count} match(es))",
                            )
                        )
                        messagebox.showinfo(
                            self._l("验证成功", "Validation Succeeded"),
                            self._t("validation_matches", count=count, name=event[2]),
                        )
                    else:
                        diagnostics = event[4] if len(event) > 4 and isinstance(event[4], dict) else {}
                        stage = diagnostics.get("stage", "target")
                        detail = self._t(
                            "validation_failure_detail", stage=stage, message=event[3]
                        )
                        self.status.config(
                            text=detail
                        )
                        messagebox.showerror(
                            self._l("验证失败", "Validation Failed"), detail
                        )
                elif event[0] == "web_capture":
                    if event[1]:
                        self._save_web_capture(event[2])
                    else:
                        self.status.config(
                            text=self._l("网页元素拾取失败", "Web element capture failed")
                        )
                        messagebox.showerror(
                            self._l("网页元素拾取失败", "Web Element Capture Failed"),
                            str(event[2]),
                        )
                elif event[0] == "web_validation":
                    if event[1]:
                        self.status.config(
                            text=self._l(
                                f"验证成功：{event[2]}", f"Validation succeeded: {event[2]}"
                            )
                        )
                        messagebox.showinfo(
                            self._l("验证成功", "Validation Succeeded"),
                            self._l(
                                f"网页 DOM 元素已找到并高亮：{event[2]}",
                                f"Web DOM element found and highlighted: {event[2]}",
                            ),
                        )
                    else:
                        self.status.config(
                            text=self._l(f"验证失败：{event[2]}", f"Validation failed: {event[2]}")
                        )
                        messagebox.showerror(
                            self._l("验证失败", "Validation Failed"), str(event[3])
                        )
        except queue.Empty:
            pass
        if not self.closed.is_set():
            self.root.after(50, self._poll_events)

    def _save_web_capture(self, result: dict[str, Any]) -> None:
        captured = result.get("captured") or {}
        captured["locator"] = result.get("locator") or {}
        suggested = (
            captured.get("attributes", {}).get("aria-label")
            or captured.get("attributes", {}).get("name")
            or captured.get("text")
            or captured.get("tag")
            or self._l("网页元素", "Web element")
        )
        name = simpledialog.askstring(
            self._l("保存网页元素", "Save Web Element"),
            self._l("请输入元素的自定义名称：", "Enter a custom element name:"),
            initialvalue=str(suggested)[:80],
            parent=self.root,
        )
        if not name:
            self.status.config(text=self._l("已放弃保存", "Save cancelled"))
            return
        try:
            item = self.store.add(name, captured, folder_id=self.capture_folder_id)
        except (OSError, ValueError) as exc:
            messagebox.showerror(self._l("保存失败", "Save Failed"), str(exc))
            return
        self.refresh_library(select_iid=f"element:{item['id']}")
        self.status.config(
            text=self._l(f"已保存网页元素：{item['name']}", f"Web element saved: {item['name']}")
        )

    def _capture_at(self, x: int, y: int) -> None:
        self.active.clear()
        self.highlighter.clear()
        try:
            captured = self.backend.element_from_point(x, y)
        except AutomationError as exc:
            self.stop_picking(self._l("捕获失败", "Capture failed"))
            messagebox.showerror(self._l("捕获失败", "Capture Failed"), str(exc))
            return
        self.stop_picking(self._l("已捕获，等待保存", "Captured; waiting to save"))
        suggested = (
            captured.get("name")
            or captured.get("automation_id")
            or captured.get("control_type")
            or self._l("未命名元素", "Unnamed element")
        )
        name = simpledialog.askstring(
            self._l("保存元素", "Save Element"),
            self._l("请输入元素的自定义名称：", "Enter a custom element name:"),
            initialvalue=str(suggested),
            parent=self.root,
        )
        if not name:
            self.status.config(text=self._l("已放弃保存", "Save cancelled"))
            return
        try:
            item = self.store.add(name, captured, folder_id=self.capture_folder_id)
        except (OSError, ValueError) as exc:
            messagebox.showerror(self._l("保存失败", "Save Failed"), str(exc))
            return
        self.refresh_library(select_iid=f"element:{item['id']}")
        self.status.config(text=self._l(f"已保存：{item['name']}", f"Saved: {item['name']}"))

    def refresh_library(self, select_iid: str | None = None) -> None:
        expanded = {
            iid
            for iid in self.library.get_children("")
            for iid in self._walk_tree(iid)
            if self.library.item(iid, "open")
        }
        for row in self.library.get_children():
            self.library.delete(row)

        root_iid = "library-root"
        self.library.insert(
            "",
            tk.END,
            iid=root_iid,
            text=self._t("element_library"),
            open=True,
            tags=("root",),
        )
        folders = self.store.list_folders()
        pending = list(folders)
        while pending:
            inserted = False
            for folder in pending[:]:
                parent_id = folder.get("parent_id")
                parent_iid = root_iid if parent_id is None else f"folder:{parent_id}"
                if not self.library.exists(parent_iid):
                    continue
                iid = f"folder:{folder['id']}"
                self.library.insert(
                    parent_iid,
                    tk.END,
                    iid=iid,
                    text=f"📁 {folder['name']}",
                    values=(self._t("folder"), "", ""),
                    open=iid in expanded,
                    tags=("folder",),
                )
                pending.remove(folder)
                inserted = True
            if not inserted:
                raise ValueError("元素库文件夹层级无效")

        for item in self.store.load():
            snapshot = item.get("snapshot", {})
            locator = item.get("locator", {})
            is_web = locator.get("backend") == "browser-dom"
            window = locator.get("window", {})
            page = locator.get("page", {})
            folder_id = item.get("folder_id")
            parent_iid = root_iid if folder_id is None else f"folder:{folder_id}"
            if not self.library.exists(parent_iid):
                parent_iid = root_iid
            self.library.insert(
                parent_iid,
                tk.END,
                iid=f"element:{item['id']}",
                text=f"⚙ {item.get('name')}",
                values=(
                    self._t("web_type", tag=snapshot.get("tag", ""))
                    if is_web
                    else snapshot.get("control_type"),
                    "DOM" if is_web else snapshot.get("automation_id"),
                    page.get("title") if is_web else window.get("name"),
                ),
                tags=("element",),
            )
        if select_iid and self.library.exists(select_iid):
            self._open_ancestors(select_iid)
            self.library.selection_set(select_iid)
            self.library.focus(select_iid)
            self.library.see(select_iid)
            self._show_selected(None)

    def _walk_tree(self, iid: str) -> list[str]:
        result = [iid]
        for child in self.library.get_children(iid):
            result.extend(self._walk_tree(child))
        return result

    def _open_ancestors(self, iid: str) -> None:
        parent = self.library.parent(iid)
        while parent:
            self.library.item(parent, open=True)
            parent = self.library.parent(parent)

    def _selected_node(self) -> tuple[str, str | None]:
        selection = self.library.selection()
        if not selection or selection[0] == "library-root":
            return "root", None
        iid = selection[0]
        kind, node_id = iid.split(":", 1)
        return kind, node_id

    def _selected_destination_folder(self) -> str | None:
        kind, node_id = self._selected_node()
        if kind == "folder":
            return node_id
        if kind == "element" and node_id:
            item = next((item for item in self.store.load() if item.get("id") == node_id), None)
            return item.get("folder_id") if item else None
        return None

    def selected_item(self) -> dict[str, Any] | None:
        kind, selected_id = self._selected_node()
        if kind != "element" or selected_id is None:
            return None
        return next((item for item in self.store.load() if item.get("id") == selected_id), None)

    def _show_selected(self, _event: object | None) -> None:
        item = self.selected_item()
        if item:
            self._render_selector_details(item)
            return
        kind, node_id = self._selected_node()
        if kind == "folder" and node_id:
            folder = next(
                (folder for folder in self.store.list_folders() if folder.get("id") == node_id),
                None,
            )
            self._render_folder_details(folder)
            return
        self._clear_details()

    def _clear_details(self) -> None:
        for child in self.details_body.winfo_children():
            child.destroy()
        self.detail_vars = {}
        self.detail_value_vars = {}
        self.detail_sources = {}
        self.detail_locator = None
        self.detail_item_id = None
        self.web_selector_vars = []
        ttk.Label(self.details_body, text=self._t("choose_element"), padding=12).pack(anchor="w")

    def _render_folder_details(self, folder: dict[str, Any] | None) -> None:
        self._clear_details()
        if not folder:
            return
        for child in self.details_body.winfo_children():
            child.destroy()
        ttk.Label(
            self.details_body,
            text=f"📁 {folder['name']}",
            font=("Microsoft YaHei UI", 11, "bold"),
            padding=12,
        ).pack(anchor="w")
        ttk.Label(
            self.details_body,
            text=self._t("folder_help"),
            padding=(12, 0),
            justify=tk.LEFT,
            wraplength=max(260, self.details_frame.winfo_width() - 40),
        ).pack(anchor="w")

    def _render_selector_details(self, item: dict[str, Any] | None) -> None:
        for child in self.details_body.winfo_children():
            child.destroy()
        self.detail_vars = {}
        self.detail_value_vars = {}
        self.detail_sources = {}
        if not item:
            self._clear_details()
            return

        self.detail_item_id = item["id"]
        raw_locator = copy.deepcopy(item["locator"])
        if raw_locator.get("backend") == "browser-dom":
            self.detail_locator = raw_locator
            self._render_web_selector_details(item)
            return
        self.detail_locator = ensure_selector(raw_locator)
        ttk.Label(
            self.details_body,
            text=f"{item['name']}  ·  {item.get('snapshot', {}).get('control_type', '')}",
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(fill=tk.X, padx=6, pady=(4, 8))

        profile = selector_profile(
            self.detail_locator.get("target", {}),
            self.detail_locator.get("selector", {}).get("target"),
        )
        strategy = self._t(f"strategy_{profile['strategy']}")
        stability = self._t(f"stability_{profile['stability']}")
        candidates = "；".join(profile.get("candidate_labels", [])) or self._l(
            "暂无完整候选组合", "No complete candidate combination"
        )
        ttk.Label(
            self.details_body,
            text=self._t(
                "capture_profile",
                strategy=strategy,
                stability=stability,
                candidates=candidates,
            ),
            foreground=COLORS["muted"],
            justify=tk.LEFT,
            wraplength=max(260, self.details_frame.winfo_width() - 40),
        ).pack(fill=tk.X, padx=6, pady=(0, 8))

        sections = (
            ("target", self._t("target_element"), self.detail_locator.get("target", {})),
            ("window", self._t("parent_window"), self.detail_locator.get("window", {})),
        )
        selector = self.detail_locator["selector"]
        for section, title, source in sections:
            group = ttk.Labelframe(self.details_body, text=title, padding=8)
            group.pack(fill=tk.X, padx=4, pady=4)
            group.columnconfigure(1, weight=1)
            properties = selector_properties(source)
            self.detail_sources[section] = properties
            recommended = set(recommended_selector_fields(source))
            selected = set(selector.get(section, recommended))
            variables = {}
            value_variables = {}
            configured_values = selector.get("values", {}).get(section, {})
            row = 0
            for field in STABLE_SELECTOR_FIELDS:
                value = properties.get(field)
                if value in (None, "", 0):
                    continue
                variable = tk.BooleanVar(value=field in selected)
                value_variable = tk.StringVar(value=str(configured_values.get(field, value)))
                variables[field] = variable
                value_variables[field] = value_variable
                label_key = FIELD_LABELS[field]
                label = self._t(label_key) if label_key.startswith("field_") else label_key
                if field in recommended:
                    label += "  ★"
                ttk.Checkbutton(group, text=label, variable=variable).grid(
                    row=row, column=0, sticky="w", pady=3
                )
                ttk.Entry(group, textvariable=value_variable).grid(
                    row=row, column=1, sticky="ew", padx=(12, 0), pady=3
                )
                row += 1
            self.detail_vars[section] = variables
            self.detail_value_vars[section] = value_variables

    def _render_web_selector_details(self, item: dict[str, Any]) -> None:
        locator = self.detail_locator or {}
        target = locator.get("target", {})
        page = locator.get("page", {})
        self.web_selector_vars = []
        ttk.Label(
            self.details_body,
            text=f"{item['name']}  ·  {self._t('web_dom')} · {target.get('tag', '')}",
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(fill=tk.X, padx=6, pady=(4, 8))
        ttk.Label(
            self.details_body,
            text=self._t("page", title=page.get("title", ""), url=page.get("url", "")),
            justify=tk.LEFT,
            wraplength=max(260, self.details_frame.winfo_width() - 40),
        ).pack(fill=tk.X, padx=6, pady=(0, 8))
        group = ttk.Labelframe(self.details_body, text=self._t("dom_selectors"), padding=8)
        group.pack(fill=tk.X, padx=4, pady=4)
        group.columnconfigure(1, weight=1)
        for row, selector in enumerate(locator.get("selectors", [])):
            enabled = tk.BooleanVar(value=selector.get("enabled", True))
            value = tk.StringVar(value=str(selector.get("value", "")))
            self.web_selector_vars.append((enabled, value))
            ttk.Checkbutton(
                group,
                text=f"CSS {selector.get('score', '')}★" if row == 0 else "CSS",
                variable=enabled,
            ).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(group, textvariable=value).grid(
                row=row, column=1, sticky="ew", padx=(12, 0), pady=3
            )
        ttk.Label(
            self.details_body,
            text=self._t("dom_help"),
            foreground="#52606d",
        ).pack(fill=tk.X, padx=8, pady=6)

    def _locator_from_details(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if self.detail_item_id != item["id"] or self.detail_locator is None:
            return copy.deepcopy(item["locator"])
        locator = copy.deepcopy(self.detail_locator)
        if locator.get("backend") == "browser-dom":
            selectors = locator.get("selectors", [])
            for index, (enabled, value) in enumerate(self.web_selector_vars):
                selectors[index]["enabled"] = enabled.get()
                selectors[index]["value"] = value.get().strip()
            if not any(entry.get("enabled") and entry.get("value") for entry in selectors):
                messagebox.showwarning(
                    self._l("元素属性", "Element Properties"),
                    self._l(
                        "至少启用一个非空 DOM 选择器",
                        "Enable at least one non-empty DOM selector.",
                    ),
                )
                return None
            return locator
        for section, variables in self.detail_vars.items():
            selected = [
                field
                for field in STABLE_SELECTOR_FIELDS
                if variables.get(field, None) and variables[field].get()
            ]
            if not selected:
                messagebox.showwarning(
                    self._l("元素属性", "Element Properties"),
                    self._l(
                        f"{section} 至少选择一个属性",
                        f"Select at least one property for {section}.",
                    ),
                )
                return None
            locator["selector"][section] = selected
            configured = {}
            for field in selected:
                raw_value = self.detail_value_vars[section][field].get()
                original = self.detail_sources[section].get(field)
                configured[field] = original if raw_value == str(original) else raw_value
            locator["selector"]["values"][section] = configured
        return locator

    def reset_detail_recommended(self) -> None:
        item = self.selected_item()
        if not item or self.detail_locator is None:
            return
        if self.detail_locator.get("backend") == "browser-dom":
            original = item.get("locator", {}).get("selectors", [])
            for index, (enabled, value) in enumerate(self.web_selector_vars):
                enabled.set(True)
                if index < len(original):
                    value.set(str(original[index].get("value", "")))
            self.status.config(
                text=self._l(
                    "已恢复网页 DOM 选择器，点击“保存属性”生效",
                    "Web DOM selectors restored. Click Save Properties to apply.",
                )
            )
            return
        for section, source in (
            ("target", self.detail_locator.get("target", {})),
            ("window", self.detail_locator.get("window", {})),
        ):
            recommended = set(recommended_selector_fields(source))
            properties = selector_properties(source)
            for field, variable in self.detail_vars.get(section, {}).items():
                variable.set(field in recommended)
                self.detail_value_vars[section][field].set(str(properties.get(field, "")))
        self.status.config(
            text=self._l(
                "已恢复系统推荐属性，点击“保存属性”生效",
                "Recommended properties restored. Click Save Properties to apply.",
            )
        )

    def save_detail_selector(self) -> None:
        item = self.selected_item()
        if not item:
            return
        locator = self._locator_from_details(item)
        if locator is None:
            return
        try:
            updated = self.store.update_locator(item["id"], locator)
        except (KeyError, OSError, ValueError) as exc:
            messagebox.showerror(self._l("保存失败", "Save Failed"), str(exc))
            return
        self._render_selector_details(updated)
        self.status.config(
            text=self._l(f"属性已保存：{updated['name']}", f"Properties saved: {updated['name']}")
        )

    def validate_selected(self) -> None:
        item = self.selected_item()
        if not item:
            messagebox.showinfo(
                self._l("验证", "Validate"),
                self._l("请先选择一个已保存元素", "Select a saved element first."),
            )
            return
        locator = self._locator_from_details(item)
        if locator is None:
            return
        if locator.get("backend") == "browser-dom":
            self.status.config(
                text=self._l(
                    f"正在验证网页元素：{item['name']}",
                    f"Validating web element: {item['name']}",
                )
            )

            def web_worker() -> None:
                try:
                    if self.web_bridge is None:
                        self.web_bridge = ensure_web_bridge_server()
                    result = self.web_bridge.request("validate", {"locator": locator}, timeout=30)
                    self.events.put(("web_validation", True, item["name"], result))
                except WebAutomationError as exc:
                    self.events.put(("web_validation", False, item["name"], str(exc)))

            threading.Thread(target=web_worker, daemon=True).start()
            return
        selector_variables = {}
        for variable_name in selector_variable_names(locator):
            value = simpledialog.askstring(
                self._l("验证动态变量", "Validate Dynamic Variable"),
                self._l(
                    f"请输入 ${{{variable_name}}} 的本次值：",
                    f"Enter the current value of ${{{variable_name}}}:",
                ),
                parent=self.root,
            )
            if value is None:
                self.status.config(text=self._l("已取消验证", "Validation cancelled"))
                return
            selector_variables[variable_name] = value
        self.status.config(text=self._l(f"正在验证：{item['name']}", f"Validating: {item['name']}"))

        def worker() -> None:
            try:
                with auto.UIAutomationInitializerInThread():
                    diagnostics = self.backend.diagnose(locator, selector_variables)
                if diagnostics.get("ok"):
                    self.events.put(
                        (
                            "validation",
                            True,
                            item["name"],
                            diagnostics["element"],
                            diagnostics,
                        )
                    )
                else:
                    self.events.put(
                        (
                            "validation",
                            False,
                            item["name"],
                            diagnostics.get("message", "Target element could not be resolved"),
                            diagnostics,
                        )
                    )
            except (AutomationError, OSError, RuntimeError, ValueError) as exc:
                self.events.put(("validation", False, item["name"], str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_projects(self) -> None:
        projects = self.projects.list_projects()
        self.project_ids_by_name = {project["name"]: project["id"] for project in projects}
        self.project_picker.configure(values=[project["name"] for project in projects])
        self.project_name.set(self.projects.active_project()["name"])

    def switch_project(self, _event: object | None = None) -> None:
        project_id = self.project_ids_by_name.get(self.project_name.get())
        if not project_id:
            return
        try:
            active = self.projects.activate(project_id)
        except (KeyError, OSError, ValueError) as exc:
            messagebox.showerror(self._l("切换失败", "Switch Failed"), str(exc))
            self.refresh_projects()
            return
        self.refresh_library()
        self._clear_details()
        self.status.config(
            text=self._l(f"当前项目：{active['name']}", f"Current project: {active['name']}")
        )

    def create_project(self) -> None:
        name = simpledialog.askstring(
            self._l("新建项目", "New Project"),
            self._l(
                "请输入项目名称。新项目将使用一个全新的空元素库：",
                "Enter a project name. The new project starts with an empty element library:",
            ),
            parent=self.root,
        )
        if not name:
            return
        try:
            project = self.projects.create_project(name, activate=True)
        except (OSError, TypeError, ValueError) as exc:
            messagebox.showerror(self._l("新建失败", "Create Failed"), str(exc))
            return
        self.refresh_projects()
        self.refresh_library()
        self._clear_details()
        self.status.config(
            text=self._l(f"已新建空项目：{project['name']}", f"Created project: {project['name']}")
        )

    def import_project(self) -> None:
        source = filedialog.askopenfilename(
            title=self._l(
                f"导入 {BRAND_NAME} SoftAuto 项目元素",
                "Import a Lingheyi SoftAuto project",
            ),
            filetypes=(
                (self._l(f"{BRAND_NAME} 项目 JSON", "SoftAuto Project JSON"), "*.json"),
                (self._l("所有文件", "All files"), "*.*"),
            ),
            parent=self.root,
        )
        if not source:
            return
        suggested = Path(source).stem.removesuffix("-elements")
        name = simpledialog.askstring(
            self._l("导入项目", "Import Project"),
            self._l("请输入导入后的项目名称：", "Enter a name for the imported project:"),
            initialvalue=suggested,
            parent=self.root,
        )
        if not name:
            return
        try:
            project = self.projects.import_project(Path(source), name=name, activate=True)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror(self._l("导入失败", "Import Failed"), str(exc))
            return
        self.refresh_projects()
        self.refresh_library()
        self._clear_details()
        self.status.config(
            text=self._l(
                f"已导入并切换到项目：{project['name']}",
                f"Imported and switched to project: {project['name']}",
            )
        )

    def copy_mcp_config(self) -> None:
        try:
            executable = mcp_executable_path()
            config = agent_mcp_config_json(executable)
        except FileNotFoundError as exc:
            messagebox.showerror(self._l("MCP 未找到", "MCP Not Found"), str(exc))
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(config)
        self.status.config(text=self._l("Agent MCP 配置已复制", "Agent MCP configuration copied"))
        messagebox.showinfo(
            self._l("MCP 已集成", "MCP Integrated"),
            self._l(
                f"MCP 服务程序：\n{executable}\n\n"
                "Agent 配置已经复制到剪贴板。粘贴到支持 MCP 的 Agent 配置中即可。\n\n"
                "MCP 默认读取本软件当前选中的项目；软件和扩展保持运行即可执行网页元素。",
                f"MCP executable:\n{executable}\n\n"
                "The Agent configuration was copied to the clipboard. Paste it into any MCP-compatible Agent.\n\n"
                "MCP reads the project currently selected here. Keep SoftAuto and the extension running for web automation.",
            ),
        )

    def export_for_mcp(self) -> None:
        project = self.projects.active_project()
        destination = filedialog.asksaveasfilename(
            title=self._l(
                f"导出 {BRAND_NAME} SoftAuto 项目（可在其他电脑导入）",
                "Export Lingheyi SoftAuto project",
            ),
            defaultextension=".json",
            filetypes=(
                (self._l("JSON 元素库", "JSON Element Library"), "*.json"),
                (self._l("所有文件", "All files"), "*.*"),
            ),
            initialfile=f"{project['name']}-elements.json",
            parent=self.root,
        )
        if not destination:
            return
        try:
            exported = self.store.export_to(Path(destination))
        except (OSError, TypeError, ValueError) as exc:
            messagebox.showerror(self._l("导出失败", "Export Failed"), str(exc))
            return
        self.status.config(text=self._l(f"已导出：{exported.name}", f"Exported: {exported.name}"))
        messagebox.showinfo(
            self._l("导出成功", "Export Succeeded"),
            self._l(
                f"元素信息已导出到：\n{exported}\n\n"
                f"把此 JSON 复制到另一台电脑，在 {BRAND_NAME} SoftAuto 点击“导入”即可继续使用。",
                f"Element information exported to:\n{exported}\n\n"
                "Copy this JSON to another computer and click Import in Lingheyi SoftAuto.",
            ),
        )

    def install_web_extension(self) -> None:
        try:
            extension_path = prepare_local_extension()
            mode = open_extension_installation(extension_path)
        except (FileNotFoundError, OSError, ValueError) as exc:
            messagebox.showerror(self._l("扩展安装失败", "Extension Installation Failed"), str(exc))
            return
        if mode == "store":
            self.status.config(
                text=self._l("已打开 Chrome Web Store 安装页", "Chrome Web Store page opened")
            )
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(str(extension_path))
        self.status.config(
            text=self._l("已打开网页扩展安装页面", "Web extension installation page opened")
        )
        messagebox.showinfo(
            self._l("安装/更新网页扩展", "Install or Update Web Extension"),
            self._l(
                "Chrome 出于安全限制，不允许普通软件静默安装本地扩展。\n\n"
                "已经为你打开扩展管理页和扩展目录，并复制了目录路径。\n\n"
                "首次安装：打开“开发者模式”，点击“加载已解压的扩展程序”，选择 web-extension 文件夹。\n\n"
                f"已经安装：在 {BRAND_NAME} Web Connector 卡片上点击圆形“重新加载”按钮，然后刷新目标网页。",
                "Chrome security rules prevent applications from silently installing local extensions.\n\n"
                "The extension page and folder are open, and the folder path was copied.\n\n"
                "First install: enable Developer mode, click Load unpacked, and select the web-extension folder.\n\n"
                "Already installed: click Reload on the Lingheyi Web Connector card, then refresh the target page.",
            ),
        )

    def create_folder(self) -> None:
        parent_id = self._selected_destination_folder()
        name = simpledialog.askstring(
            self._l("新建文件夹", "New Folder"),
            self._l("请输入文件夹名称：", "Enter a folder name:"),
            parent=self.root,
        )
        if not name:
            return
        try:
            folder = self.store.create_folder(name, parent_id=parent_id)
        except (KeyError, OSError, ValueError) as exc:
            messagebox.showerror(self._l("新建失败", "Create Failed"), str(exc))
            return
        self.refresh_library(select_iid=f"folder:{folder['id']}")
        self.status.config(
            text=self._l(f"已新建文件夹：{folder['name']}", f"Folder created: {folder['name']}")
        )

    def rename_selected(self) -> None:
        kind, node_id = self._selected_node()
        if kind == "folder" and node_id:
            folder = next(
                (folder for folder in self.store.list_folders() if folder.get("id") == node_id),
                None,
            )
            if not folder:
                return
            name = simpledialog.askstring(
                self._l("重命名文件夹", "Rename Folder"),
                self._l("请输入新的文件夹名称：", "Enter a new folder name:"),
                initialvalue=folder["name"],
                parent=self.root,
            )
            if name:
                try:
                    self.store.rename_folder(node_id, name)
                except (KeyError, OSError, ValueError) as exc:
                    messagebox.showerror(self._l("重命名失败", "Rename Failed"), str(exc))
                    return
                self.refresh_library(select_iid=f"folder:{node_id}")
            return
        item = self.selected_item()
        if not item:
            return
        name = simpledialog.askstring(
            self._l("重命名元素", "Rename Element"),
            self._l("请输入新的元素名称：", "Enter a new element name:"),
            initialvalue=item["name"],
            parent=self.root,
        )
        if name:
            try:
                self.store.rename(item["id"], name)
            except (KeyError, OSError, ValueError) as exc:
                messagebox.showerror(self._l("重命名失败", "Rename Failed"), str(exc))
                return
            self.refresh_library(select_iid=f"element:{item['id']}")

    def delete_selected(self) -> None:
        kind, node_id = self._selected_node()
        if kind == "folder" and node_id:
            folder = next(
                (folder for folder in self.store.list_folders() if folder.get("id") == node_id),
                None,
            )
            if not folder:
                return
            if not messagebox.askyesno(
                self._l("删除文件夹", "Delete Folder"),
                self._l(
                    f"确定删除空文件夹“{folder['name']}”吗？",
                    f"Delete the empty folder '{folder['name']}'?",
                ),
            ):
                return
            try:
                self.store.delete_folder(node_id)
            except ValueError:
                messagebox.showwarning(
                    self._l("无法删除", "Cannot Delete"),
                    self._l(
                        "文件夹不是空的，请先移动或删除其中的内容。",
                        "The folder is not empty. Move or delete its contents first.",
                    ),
                )
                return
            except (KeyError, OSError) as exc:
                messagebox.showerror(self._l("删除失败", "Delete Failed"), str(exc))
                return
            self.refresh_library()
            self._clear_details()
            return
        item = self.selected_item()
        if not item:
            return
        if messagebox.askyesno(
            self._l("删除元素", "Delete Element"),
            self._l(f"确定删除“{item['name']}”吗？", f"Delete '{item['name']}'?"),
        ):
            self.store.delete(item["id"])
            self.refresh_library()
            self._clear_details()

    def _begin_tree_drag(self, event: tk.Event[tk.Misc]) -> None:
        iid = self.library.identify_row(event.y)
        self._drag_source = iid if iid and iid != "library-root" else None

    def _finish_tree_drag(self, event: tk.Event[tk.Misc]) -> None:
        source_iid = self._drag_source
        self._drag_source = None
        if not source_iid or not self.library.exists(source_iid):
            return
        target_iid = self.library.identify_row(event.y)
        if target_iid == source_iid:
            return
        if not target_iid or target_iid == "library-root":
            target_folder_id = None
        elif target_iid.startswith("folder:"):
            target_folder_id = target_iid.split(":", 1)[1]
        elif target_iid.startswith("element:"):
            target_element_id = target_iid.split(":", 1)[1]
            target_item = next(
                (item for item in self.store.load() if item.get("id") == target_element_id),
                None,
            )
            target_folder_id = target_item.get("folder_id") if target_item else None
        else:
            return

        try:
            if source_iid.startswith("folder:"):
                node_id = source_iid.split(":", 1)[1]
                moved = self.store.move_folder(node_id, target_folder_id)
                selected_iid = f"folder:{moved['id']}"
            elif source_iid.startswith("element:"):
                node_id = source_iid.split(":", 1)[1]
                moved = self.store.move_element(node_id, target_folder_id)
                selected_iid = f"element:{moved['id']}"
            else:
                return
        except (KeyError, OSError, ValueError) as exc:
            messagebox.showerror(self._l("移动失败", "Move Failed"), str(exc))
            return
        self.refresh_library(select_iid=selected_iid)
        self.status.config(text=self._l("已移动节点", "Node moved"))

    def copy_locator(self) -> None:
        item = self.selected_item()
        if not item:
            return
        text = json.dumps(item["locator"], ensure_ascii=False, indent=2)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.config(text=self._l("Locator 已复制", "Locator copied"))

    def close(self) -> None:
        self.closed.set()
        self.active.clear()
        self.highlighter.clear()
        self.mouse_listener.stop()
        self.keyboard_listener.stop()
        self.highlighter.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    ElementPickerApp().run()


if __name__ == "__main__":
    main()
