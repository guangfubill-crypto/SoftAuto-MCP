# SoftAuto 0.5.3 — Agent 决策，RPA 速度执行

Computer Use 擅长理解未知界面，但每一步都依赖截图、视觉推理和坐标操作时，自动化会慢且容易漂移。

SoftAuto 0.5.3 提供另一条执行路径：首次拾取并验证 Windows UIA 或网页 DOM 元素，之后 Agent 通过 MCP 直接调用已保存元素。智能体负责理解与决策，SoftAuto 负责稳定、快速地执行重复操作。

## 本次发布

- Windows UIA 与浏览器 DOM 双通道元素拾取和验证。
- 以项目为单位的树状元素库，支持文件夹、拖放、导入和导出。
- 集成 19 个 MCP 查询与动作工具。
- 支持稳定属性推荐、动态文本前缀、通配符和 MCP 变量。
- 集成网页扩展安装入口和浏览器连接状态检查。
- 简体中文 / English 即时切换并自动记忆。
- 窗口、按钮和文字根据分辨率及 Windows DPI 自适应。
- Windows 安装包内置 GUI、MCP 服务和 FlaUInspect 深度检查工具。

## 安全设计

- MCP 动作必须通过已保存的命名元素执行。
- 不暴露任意 Shell 执行。
- 不暴露绕过元素库的任意坐标点击。
- 可以通过 `SOFTAUTO_ALLOW_ACTIONS=0` 禁用动作工具。

## 验证

- 36 项自动化测试通过。
- 安装版 MCP 冒烟测试通过，共发现 19 个工具。
- Windows UIA、浏览器 DOM、项目迁移和中英文响应式界面均已验证。

Windows 用户请下载 `Lingheyi-SoftAuto-Setup-0.5.3.exe`。
