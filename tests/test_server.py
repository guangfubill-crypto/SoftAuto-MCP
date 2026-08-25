from softauto import server


def test_server_is_read_only_by_default() -> None:
    assert server.ALLOW_ACTIONS is False
    status = server.automation_status()
    assert status["backend"] == "windows-uia"
    assert status["actions_enabled"] is False


def test_list_windows_returns_locators() -> None:
    result = server.list_windows(limit=10)
    assert result["ok"] is True
    assert all("locator" in item for item in result["result"])
