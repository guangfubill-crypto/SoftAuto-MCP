# Changelog

All notable changes to SoftAuto are documented here.

## [0.5.6] - 2026-09-03

- 新增 FlaUI Bridge：桌面元素采集失败时自动尝试 FlaUI UIA3，再回退到 UIA2。
- 采集结果转换为现有稳定 Locator，不改变 MCP 动作接口。
- 安装包内置 FlaUI Bridge 及 FlaUI 依赖。

## [0.5.5] - 2026-09-03

- 参考影刀式元素采集闭环：右侧展示采集策略、稳定性和候选属性组合。
- 新增桌面元素定位诊断，验证时显示匹配数量、最佳匹配和失败阶段。
- 保持动态名称前缀、通配符和 MCP 变量定位能力。

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
