import json
from pathlib import Path

import pytest

from softauto.element_store import ElementStore


def captured_fixture() -> dict:
    return {
        "name": "保存",
        "control_type": "ButtonControl",
        "automation_id": "saveButton",
        "locator": {
            "backend": "windows-uia",
            "version": 1,
            "window": {"name": "业务系统"},
            "path": [],
            "target": {"automation_id": "saveButton"},
        },
        "ancestors": [{"name": "业务系统"}],
    }


def test_add_rename_and_delete_element(tmp_path: Path) -> None:
    store = ElementStore(tmp_path / "elements.json")
    item = store.add("保存按钮", captured_fixture())
    assert store.load()[0]["name"] == "保存按钮"
    assert store.get("保存按钮")["id"] == item["id"]
    assert store.get(item["id"])["name"] == "保存按钮"
    store.rename(item["id"], "提交按钮")
    assert store.load()[0]["name"] == "提交按钮"
    locator = store.get(item["id"])["locator"]
    locator["selector"] = {"target": ["automation_id"]}
    updated = store.update_locator(item["id"], locator)
    assert updated["locator"]["selector"]["target"] == ["automation_id"]
    store.delete(item["id"])
    assert store.load() == []


def test_legacy_flat_library_is_migrated_without_losing_elements(tmp_path: Path) -> None:
    path = tmp_path / "elements.json"
    legacy = {
        "id": "legacy-id",
        "name": "账号",
        "locator": captured_fixture()["locator"],
    }
    path.write_text(json.dumps([legacy], ensure_ascii=False), encoding="utf-8")
    store = ElementStore(path)

    assert store.get("账号")["id"] == "legacy-id"
    store.create_folder("登录")

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["version"] == 2
    assert document["elements"][0]["id"] == "legacy-id"
    assert document["elements"][0]["folder_id"] is None


def test_folder_tree_paths_and_moves(tmp_path: Path) -> None:
    store = ElementStore(tmp_path / "elements.json")
    application = store.create_folder("Training System")
    login = store.create_folder("登录", application["id"])
    account = store.add("账号", captured_fixture(), login["id"])

    assert store.get("Training System/登录/账号")["id"] == account["id"]
    assert store.list_elements(include_paths=True)[0]["path"] == "Training System/登录/账号"
    assert store.tree()[0]["children"][0]["children"][0]["kind"] == "element"

    store.move_element(account["id"], application["id"])
    assert store.get("Training System/账号")["id"] == account["id"]
    store.move_folder(login["id"], None)
    assert {node["name"] for node in store.tree()} == {"Training System", "登录"}


def test_folder_safety_rules(tmp_path: Path) -> None:
    store = ElementStore(tmp_path / "elements.json")
    parent = store.create_folder("页面")
    child = store.create_folder("登录", parent["id"])
    store.add("账号", captured_fixture(), child["id"])

    with pytest.raises(ValueError, match="descendants"):
        store.move_folder(parent["id"], child["id"])
    with pytest.raises(ValueError, match="not empty"):
        store.delete_folder(child["id"])
    with pytest.raises(ValueError, match="already exists"):
        store.add("账号", captured_fixture(), child["id"])
