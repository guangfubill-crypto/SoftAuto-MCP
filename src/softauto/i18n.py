from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from softauto.runtime_paths import user_data_dir

DEFAULT_LANGUAGE = "zh-CN"
LANGUAGE_NAMES = {"zh-CN": "简体中文", "en": "English"}

TEXTS: dict[str, dict[str, str]] = {
    "app_title": {
        "zh-CN": "零禾一智能 · SoftAuto 软件自动化",
        "en": "Lingheyi Intelligence · SoftAuto",
    },
    "tagline": {
        "zh-CN": "让每一个软件，都能成为智能体的可靠工具",
        "en": "Turn every application into a reliable agent tool",
    },
    "web_checking": {"zh-CN": "网页扩展  检查中", "en": "Web extension  Checking"},
    "web_connected": {"zh-CN": "网页扩展  ● 已连接", "en": "Web extension  ● Connected"},
    "web_connected_short": {"zh-CN": "● 已连接", "en": "● Connected"},
    "web_disconnected": {"zh-CN": "网页扩展  ○ 未连接", "en": "Web extension  ○ Disconnected"},
    "web_disconnected_short": {"zh-CN": "○ 未连接", "en": "○ Disconnected"},
    "current_project": {"zh-CN": "当前项目", "en": "Project"},
    "new_project": {"zh-CN": "＋ 新建", "en": "+ New"},
    "import": {"zh-CN": "导入", "en": "Import"},
    "export": {"zh-CN": "导出", "en": "Export"},
    "mcp_config": {"zh-CN": "MCP 配置", "en": "MCP Config"},
    "web_extension": {"zh-CN": "网页扩展", "en": "Web Extension"},
    "pick_desktop": {"zh-CN": "拾取桌面元素", "en": "Pick Desktop Element"},
    "pick_web": {"zh-CN": "拾取网页元素", "en": "Pick Web Element"},
    "new_folder": {"zh-CN": "＋ 文件夹", "en": "+ Folder"},
    "validate": {"zh-CN": "✓ 验证", "en": "✓ Validate"},
    "rename": {"zh-CN": "重命名", "en": "Rename"},
    "delete": {"zh-CN": "删除", "en": "Delete"},
    "copy_locator": {"zh-CN": "复制定位器", "en": "Copy Locator"},
    "inspect": {"zh-CN": "深度检查", "en": "Inspect"},
    "element_library": {"zh-CN": "元素库", "en": "Element Library"},
    "locator_properties": {"zh-CN": "定位属性", "en": "Locator Properties"},
    "name": {"zh-CN": "名称", "en": "Name"},
    "type": {"zh-CN": "类型", "en": "Type"},
    "window": {"zh-CN": "窗口", "en": "Window"},
    "ready": {
        "zh-CN": "就绪 · 选择项目后即可拾取元素",
        "en": "Ready · Select a project to capture elements",
    },
    "selector_help": {
        "zh-CN": "勾选参与定位的属性；★表示系统推荐。动态文本优先使用 NamePrefix。ProcessId 和窗口句柄仅用于诊断，不参与定位。",
        "en": "Select locator attributes. ★ indicates recommended. Use NamePrefix for dynamic text. ProcessId and window handles are diagnostic-only.",
    },
    "recommended": {"zh-CN": "系统推荐", "en": "Recommended"},
    "save_properties": {"zh-CN": "保存属性", "en": "Save Properties"},
    "validate_plain": {"zh-CN": "验证", "en": "Validate"},
    "language": {"zh-CN": "语言", "en": "Language"},
    "capture_title": {
        "zh-CN": "零禾一智能 · 元素拾取",
        "en": "Lingheyi Intelligence · Element Capture",
    },
    "capture_help": {
        "zh-CN": "移动鼠标定位元素；Ctrl + 左键保存；Esc 取消",
        "en": "Move to highlight; Ctrl + left-click to save; Esc to cancel",
    },
    "cancel": {"zh-CN": "取消", "en": "Cancel"},
    "no_name": {"zh-CN": "(无名称)", "en": "(unnamed)"},
    "folder": {"zh-CN": "文件夹", "en": "Folder"},
    "web_type": {"zh-CN": "网页 · {tag}", "en": "Web · {tag}"},
    "choose_element": {
        "zh-CN": "请在左侧元素库选择一个元素",
        "en": "Select an element from the library",
    },
    "folder_help": {
        "zh-CN": "选中此文件夹后拾取的新元素会自动保存在这里。\n也可以把文件夹或元素拖放到其他文件夹中。",
        "en": "Newly captured elements are saved in the selected folder.\nYou can also drag folders or elements into another folder.",
    },
    "target_element": {"zh-CN": "目标元素", "en": "Target Element"},
    "parent_window": {"zh-CN": "所属窗口", "en": "Parent Window"},
    "web_dom": {"zh-CN": "网页 DOM", "en": "Web DOM"},
    "page": {"zh-CN": "页面：{title}\n{url}", "en": "Page: {title}\n{url}"},
    "dom_selectors": {"zh-CN": "DOM 选择器（可编辑）", "en": "DOM Selectors (editable)"},
    "dom_help": {
        "zh-CN": "系统优先使用上方稳定属性选择器；可以取消勾选或直接编辑 CSS。",
        "en": "Stable selectors are tried first. Disable a selector or edit its CSS directly.",
    },
    "field_name": {"zh-CN": "Name（完整当前值）", "en": "Name (complete current value)"},
    "field_name_prefix": {
        "zh-CN": "NamePrefix（动态文本前缀）",
        "en": "NamePrefix (dynamic text prefix)",
    },
}


def normalize_language(value: str | None) -> str:
    return value if value in LANGUAGE_NAMES else DEFAULT_LANGUAGE


def translate(key: str, language: str, **values: Any) -> str:
    entry = TEXTS[key]
    return entry.get(normalize_language(language), entry[DEFAULT_LANGUAGE]).format(**values)


def settings_path() -> Path:
    return user_data_dir() / "settings.json"


def load_language(path: Path | None = None) -> str:
    target = path or settings_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return DEFAULT_LANGUAGE
    return (
        normalize_language(payload.get("language"))
        if isinstance(payload, dict)
        else DEFAULT_LANGUAGE
    )


def save_language(language: str, path: Path | None = None) -> None:
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"language": normalize_language(language)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def responsive_window_metrics(screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
    safe_width = max(640, int(screen_width))
    safe_height = max(480, int(screen_height))
    minimum_width = max(640, min(860, safe_width - 40))
    minimum_height = max(440, min(560, safe_height - 80))
    initial_width = max(minimum_width, min(1280, safe_width - 80))
    initial_height = max(minimum_height, min(800, safe_height - 100))
    return initial_width, initial_height, minimum_width, minimum_height


def responsive_layout_mode(window_width: int) -> str:
    if window_width < 900:
        return "narrow"
    if window_width < 1180:
        return "compact"
    return "wide"
