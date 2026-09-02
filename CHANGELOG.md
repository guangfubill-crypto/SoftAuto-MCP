# Changelog

All notable changes to SoftAuto are documented here.

## [0.5.4] - 2026-09-02

- 禁止将 `ProcessId` 和 `NativeWindowHandle` 用作定位条件；这两个字段保留为诊断信息。
- 过滤旧元素库中遗留的运行时身份选择器，避免重启后因进程或窗口句柄变化而失效。
- 新增运行时身份字段回归测试。

## [0.5.3] - 2026-08-25

### Added

- Project-scoped tree element libraries with import and export.
- Windows UIA and browser DOM element capture, highlighting, validation, and actions.
- Integrated MCP executable exposing 19 named query and action tools.
- Editable locator properties, wildcards, prefixes, and dynamic MCP variables.
- Simplified Chinese and English user interfaces with persisted language selection.
- Responsive window and button layouts for multiple resolutions and Windows DPI settings.
- Branded Windows installer, application icon, and browser extension assets.

### Security

- Named saved elements are required for MCP actions.
- Arbitrary shell execution and unrestricted coordinate clicks are not exposed.
- Automation actions can be disabled with `SOFTAUTO_ALLOW_ACTIONS=0`.
