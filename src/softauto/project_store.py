from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from softauto.runtime_paths import user_data_dir


class ProjectStore:
    """Manage independent element libraries and the currently active project."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = (registry_path or (user_data_dir() / "projects.json")).resolve()
        self.projects_dir = self.registry_path.parent / "projects"
        self.legacy_library = self.registry_path.parent / "elements.json"

    def list_projects(self) -> list[dict[str, Any]]:
        return self._load_registry()["projects"]

    def active_project(self) -> dict[str, Any]:
        registry = self._load_registry()
        active_id = registry["active_project_id"]
        project = next(
            (item for item in registry["projects"] if item.get("id") == active_id),
            None,
        )
        if project is None:
            raise ValueError("Active project does not exist")
        result = dict(project)
        result["library_path"] = str(self.library_path(project["id"]))
        return result

    def create_project(self, name: str, activate: bool = True) -> dict[str, Any]:
        clean_name = self._clean_name(name)
        registry = self._load_registry()
        if any(
            str(project.get("name", "")).casefold() == clean_name.casefold()
            for project in registry["projects"]
        ):
            raise ValueError("A project with this name already exists")
        project = {
            "id": str(uuid.uuid4()),
            "name": clean_name,
            "created_at": datetime.now(UTC).isoformat(),
        }
        registry["projects"].append(project)
        if activate:
            registry["active_project_id"] = project["id"]
        self._write_registry(registry)
        self._write_empty_library(self.library_path(project["id"]))
        return {**project, "library_path": str(self.library_path(project["id"]))}

    def import_project(
        self,
        source: Path,
        name: str | None = None,
        activate: bool = True,
    ) -> dict[str, Any]:
        source_path = source.resolve()
        raw = json.loads(source_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            document = {"version": 2, "folders": [], "elements": raw}
            suggested_name = source_path.stem
        elif isinstance(raw, dict):
            folders = raw.get("folders", [])
            elements = raw.get("elements", [])
            if not isinstance(folders, list) or not isinstance(elements, list):
                raise TypeError("Imported project folders and elements must be JSON arrays")
            document = {"version": 2, "folders": folders, "elements": elements}
            project_info = raw.get("project") or {}
            suggested_name = str(project_info.get("name") or source_path.stem)
        else:
            raise TypeError("Imported project must contain a JSON object or array")

        project = self.create_project(name or suggested_name, activate=activate)
        destination = Path(project["library_path"])
        temporary = destination.with_suffix(".import.tmp")
        try:
            temporary.write_text(
                json.dumps(document, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(destination)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise
        return project

    def activate(self, project_id: str) -> dict[str, Any]:
        registry = self._load_registry()
        project = next(
            (item for item in registry["projects"] if item.get("id") == project_id),
            None,
        )
        if project is None:
            raise KeyError(project_id)
        registry["active_project_id"] = project_id
        self._write_registry(registry)
        result = dict(project)
        result["library_path"] = str(self.library_path(project_id))
        return result

    def library_path(self, project_id: str) -> Path:
        try:
            uuid.UUID(project_id)
        except ValueError as exc:
            raise ValueError("Invalid project id") from exc
        return (self.projects_dir / project_id / "elements.json").resolve()

    def _load_registry(self) -> dict[str, Any]:
        if not self.registry_path.is_file():
            return self._initialize_registry()
        raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("projects"), list):
            raise TypeError("Project registry is invalid")
        if not raw.get("active_project_id"):
            raise ValueError("Project registry has no active project")
        return raw

    def _initialize_registry(self) -> dict[str, Any]:
        project_id = str(uuid.uuid4())
        project = {
            "id": project_id,
            "name": "默认项目",
            "created_at": datetime.now(UTC).isoformat(),
        }
        registry = {
            "version": 1,
            "active_project_id": project_id,
            "projects": [project],
        }
        library_path = self.library_path(project_id)
        library_path.parent.mkdir(parents=True, exist_ok=True)
        if self.legacy_library.is_file():
            shutil.copy2(self.legacy_library, library_path)
        else:
            self._write_empty_library(library_path)
        self._write_registry(registry)
        return registry

    @staticmethod
    def _clean_name(name: str) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Project name cannot be empty")
        if any(character in clean_name for character in '<>:"/\\|?*'):
            raise ValueError("Project name contains invalid filename characters")
        return clean_name

    @staticmethod
    def _write_empty_library(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"version": 2, "folders": [], "elements": []},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_registry(self, registry: dict[str, Any]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.registry_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.registry_path)
