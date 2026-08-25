import json
from pathlib import Path

from softauto.element_store import ElementStore
from softauto.project_store import ProjectStore


def captured_fixture(name: str) -> dict:
    return {
        "name": name,
        "control_type": "ButtonControl",
        "locator": {
            "backend": "windows-uia",
            "version": 1,
            "window": {"name": "业务系统"},
            "path": [],
            "target": {"name": name},
        },
    }


def test_legacy_library_becomes_default_project(tmp_path: Path) -> None:
    legacy = [{"id": "old", "name": "旧元素", "locator": {"target": {}}}]
    (tmp_path / "elements.json").write_text(
        json.dumps(legacy, ensure_ascii=False), encoding="utf-8"
    )
    projects = ProjectStore(tmp_path / "projects.json")

    active = projects.active_project()

    assert active["name"] == "默认项目"
    assert json.loads(Path(active["library_path"]).read_text(encoding="utf-8")) == legacy
    assert json.loads((tmp_path / "elements.json").read_text(encoding="utf-8")) == legacy


def test_new_project_is_empty_and_switching_restores_library(tmp_path: Path) -> None:
    projects = ProjectStore(tmp_path / "projects.json")
    store = ElementStore(project_store=projects)
    original = projects.active_project()
    store.add("原项目元素", captured_fixture("原项目元素"))

    created = projects.create_project("采购流程")
    assert projects.active_project()["id"] == created["id"]
    assert store.load() == []

    store.add("新项目元素", captured_fixture("新项目元素"))
    projects.activate(original["id"])
    assert [item["name"] for item in store.load()] == ["原项目元素"]


def test_export_is_directly_loadable_as_an_element_library(tmp_path: Path) -> None:
    projects = ProjectStore(tmp_path / "projects.json")
    store = ElementStore(project_store=projects)
    store.add("提交", captured_fixture("提交"))
    export_path = store.export_to(tmp_path / "exports" / "elements.json")

    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["project"]["name"] == "默认项目"
    assert ElementStore(export_path).get("提交")["name"] == "提交"


def test_exported_project_can_be_imported_on_another_computer(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_projects = ProjectStore(source_root / "projects.json")
    source_store = ElementStore(project_store=source_projects)
    source_store.add("账号输入框", captured_fixture("账号输入框"))
    exported = source_store.export_to(tmp_path / "portable-project.json")

    target_projects = ProjectStore(target_root / "projects.json")
    imported = target_projects.import_project(exported, name="登录流程")
    target_store = ElementStore(project_store=target_projects)

    assert target_projects.active_project()["id"] == imported["id"]
    assert target_store.get("账号输入框")["name"] == "账号输入框"
