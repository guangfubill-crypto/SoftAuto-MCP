from __future__ import annotations

import ctypes
import tkinter as tk
from typing import Any

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
LWA_COLORKEY = 0x00000001


class OverlayHighlighter:
    """Topmost, transparent, click-through element outline for Windows."""

    transparent_color = "#010101"
    outline_color = "#ff8a00"

    def __init__(self, root: tk.Misc) -> None:
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=self.transparent_color)
        self.window.attributes("-transparentcolor", self.transparent_color)
        self.canvas = tk.Canvas(
            self.window,
            bg=self.transparent_color,
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.window.update_idletasks()
        self._make_click_through()
        self._bounds: tuple[int, int, int, int] | None = None

    def _make_click_through(self) -> None:
        hwnd = int(self.window.winfo_id())
        user32 = ctypes.windll.user32
        get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_style.restype = ctypes.c_ssize_t
        set_style.restype = ctypes.c_ssize_t
        style = int(get_style(hwnd, GWL_EXSTYLE))
        style |= WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOACTIVATE
        set_style(hwnd, GWL_EXSTYLE, style)
        user32.SetLayeredWindowAttributes(hwnd, 0x00010101, 0, LWA_COLORKEY)

    def update(self, bounds: dict[str, Any] | None) -> None:
        if not bounds:
            self.clear()
            return
        normalized = (
            int(bounds["left"]),
            int(bounds["top"]),
            int(bounds["right"]),
            int(bounds["bottom"]),
        )
        if normalized[2] <= normalized[0] or normalized[3] <= normalized[1]:
            self.clear()
            return
        if normalized == self._bounds and self.window.state() != "withdrawn":
            return
        self._bounds = normalized
        left, top, right, bottom = normalized
        width = max(8, right - left)
        height = max(8, bottom - top)
        self.window.geometry(f"{width}x{height}+{left}+{top}")
        self.canvas.configure(width=width, height=height)
        self.canvas.delete("all")
        inset = 3
        self.canvas.create_rectangle(
            inset,
            inset,
            max(inset + 1, width - inset - 1),
            max(inset + 1, height - inset - 1),
            outline=self.outline_color,
            width=5,
        )
        self.window.deiconify()
        self.window.lift()

    def clear(self) -> None:
        self._bounds = None
        self.window.withdraw()

    def close(self) -> None:
        self.clear()
        self.window.destroy()
