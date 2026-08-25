# Contributing

Thanks for helping improve SoftAuto.

## Development setup

SoftAuto currently targets Windows 10/11 and Python 3.11–3.13.

```powershell
uv sync --extra dev
uv run pytest -q
uv run ruff check src tests
uv run softauto-inspector
```

Keep changes focused and include tests for locator, project-store, MCP, or localization behavior.
Do not commit real element libraries, screenshots containing business data, credentials, or local
absolute paths.

By contributing, you agree that your contribution is licensed under the repository's MIT license.
