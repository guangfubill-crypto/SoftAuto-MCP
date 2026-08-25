from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from softauto.project_store import ProjectStore

LIBRARY_VERSION = 2


class ElementStore:
    """Persist captured elements and Blue Prism-style folders.

    Version 1 libraries were plain JSON arrays. They are read as root-level
    elements and are upgraded to the version 2 document format on the first
    write, so existing captured elements remain usable.
    """

    def __init__(
        self,
        path: Path | None = None,
        project_store: ProjectStore | None = None,
    ) -> None:
        configured = os.environ.get("SOFTAUTO_ELEMENT_LIBRARY")
        self._explicit_path = path or (Path(configured) if configured else None)
        if self._explicit_path is not None:
            self._explicit_path = self._explicit_path.resolve()
        self.project_store = project_store or ProjectStore()

    @property
    def path(self) -> Path:
        if self._explicit_path is not None:
            return self._explicit_path
        active = self.project_store.active_project()
        return Path(active["library_path"])

    def _load_document(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": LIBRARY_VERSION, "folders": [], "elements": []}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            elements = copy.deepcopy(raw)
            for item in elements:
                item.setdefault("folder_id", None)
            return {"version": LIBRARY_VERSION, "folders": [], "elements": elements}
        if not isinstance(raw, dict):
            raise TypeError("Element library must contain a JSON array or object")
        folders = raw.get("folders", [])
        elements = raw.get("elements", [])
        if not isinstance(folders, list) or not isinstance(elements, list):
            raise TypeError("Element library folders and elements must be JSON arrays")
        return {
            "version": LIBRARY_VERSION,
            "folders": copy.deepcopy(folders),
            "elements": copy.deepcopy(elements),
        }

    def load(self) -> list[dict[str, Any]]:
        """Return elements only, preserving the original flat-list API."""

        return self._load_document()["elements"]

    def list_folders(self) -> list[dict[str, Any]]:
        return self._load_document()["folders"]

    def list_elements(self, include_paths: bool = False) -> list[dict[str, Any]]:
        document = self._load_document()
        elements = document["elements"]
        if not include_paths:
            return elements
        folders = document["folders"]
        for item in elements:
            item["path"] = self._element_path(item, folders)
        return elements

    def tree(self) -> list[dict[str, Any]]:
        document = self._load_document()
        folders = document["folders"]
        elements = document["elements"]

        def children(parent_id: str | None) -> list[dict[str, Any]]:
            folder_nodes = [
                {
                    "kind": "folder",
                    "id": folder["id"],
                    "name": folder["name"],
                    "path": self._folder_path(folder["id"], folders),
                    "children": children(folder["id"]),
                }
                for folder in folders
                if folder.get("parent_id") == parent_id
            ]
            element_nodes = [
                {
                    "kind": "element",
                    "id": item["id"],
                    "name": item["name"],
                    "path": self._element_path(item, folders),
                    "snapshot": item.get("snapshot", {}),
                }
                for item in elements
                if item.get("folder_id") == parent_id
            ]
            folder_nodes.sort(key=lambda node: node["name"].casefold())
            element_nodes.sort(key=lambda node: node["name"].casefold())
            return folder_nodes + element_nodes

        return children(None)

    def export_to(self, destination: Path) -> Path:
        target = destination.resolve()
        document = self._load_document()
        if self._explicit_path is None:
            project = self.project_store.active_project()
            document["project"] = {
                "id": project["id"],
                "name": project["name"],
                "exported_at": datetime.now(UTC).isoformat(),
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{target.name}.tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
        return target

    def add(
        self,
        name: str,
        captured: dict[str, Any],
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        clean_name = self._clean_name(name, "Element")
        document = self._load_document()
        self._require_folder(document["folders"], folder_id)
        self._require_unique_element_name(document["elements"], clean_name, folder_id)
        item = {
            "id": str(uuid.uuid4()),
            "name": clean_name,
            "folder_id": folder_id,
            "created_at": datetime.now(UTC).isoformat(),
            "snapshot": {
                key: value for key, value in captured.items() if key not in {"ancestors", "locator"}
            },
            "ancestors": captured.get("ancestors", []),
            "locator": captured["locator"],
        }
        document["elements"].append(item)
        self._write_document(document)
        return item

    def create_folder(self, name: str, parent_id: str | None = None) -> dict[str, Any]:
        clean_name = self._clean_name(name, "Folder")
        document = self._load_document()
        folders = document["folders"]
        self._require_folder(folders, parent_id)
        self._require_unique_folder_name(folders, clean_name, parent_id)
        folder = {
            "id": str(uuid.uuid4()),
            "name": clean_name,
            "parent_id": parent_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        folders.append(folder)
        self._write_document(document)
        return folder

    def get(self, element_id_or_name_or_path: str) -> dict[str, Any]:
        document = self._load_document()
        elements = document["elements"]
        exact_id = next(
            (item for item in elements if item.get("id") == element_id_or_name_or_path),
            None,
        )
        if exact_id:
            return exact_id

        normalized = self._normalize_path(element_id_or_name_or_path)
        path_matches = [
            item
            for item in elements
            if self._element_path(item, document["folders"]).casefold() == normalized.casefold()
        ]
        if len(path_matches) == 1:
            return path_matches[0]
        if len(path_matches) > 1:
            raise ValueError("Multiple saved elements have this path; use the element id")

        matches = [
            item
            for item in elements
            if str(item.get("name", "")).casefold() == element_id_or_name_or_path.casefold()
        ]
        if not matches:
            raise KeyError(element_id_or_name_or_path)
        if len(matches) > 1:
            raise ValueError(
                "Multiple saved elements have this name; use its full path or element id"
            )
        return matches[0]

    def rename(self, element_id: str, name: str) -> dict[str, Any]:
        clean_name = self._clean_name(name, "Element")
        document = self._load_document()
        items = document["elements"]
        for item in items:
            if item.get("id") == element_id:
                self._require_unique_element_name(
                    items, clean_name, item.get("folder_id"), exclude_id=element_id
                )
                item["name"] = clean_name
                self._write_document(document)
                return item
        raise KeyError(element_id)

    def rename_folder(self, folder_id: str, name: str) -> dict[str, Any]:
        clean_name = self._clean_name(name, "Folder")
        document = self._load_document()
        folders = document["folders"]
        folder = self._folder_by_id(folders, folder_id)
        self._require_unique_folder_name(
            folders, clean_name, folder.get("parent_id"), exclude_id=folder_id
        )
        folder["name"] = clean_name
        self._write_document(document)
        return folder

    def move_element(self, element_id: str, folder_id: str | None) -> dict[str, Any]:
        document = self._load_document()
        self._require_folder(document["folders"], folder_id)
        for item in document["elements"]:
            if item.get("id") == element_id:
                self._require_unique_element_name(
                    document["elements"], item["name"], folder_id, exclude_id=element_id
                )
                item["folder_id"] = folder_id
                self._write_document(document)
                return item
        raise KeyError(element_id)

    def move_folder(self, folder_id: str, parent_id: str | None) -> dict[str, Any]:
        document = self._load_document()
        folders = document["folders"]
        folder = self._folder_by_id(folders, folder_id)
        self._require_folder(folders, parent_id)
        if parent_id == folder_id or parent_id in self._descendant_folder_ids(folder_id, folders):
            raise ValueError("A folder cannot be moved into itself or one of its descendants")
        self._require_unique_folder_name(folders, folder["name"], parent_id, exclude_id=folder_id)
        folder["parent_id"] = parent_id
        self._write_document(document)
        return folder

    def update_locator(self, element_id: str, locator: dict[str, Any]) -> dict[str, Any]:
        document = self._load_document()
        for item in document["elements"]:
            if item.get("id") == element_id:
                item["locator"] = locator
                self._write_document(document)
                return item
        raise KeyError(element_id)

    def delete(self, element_id: str) -> None:
        document = self._load_document()
        retained = [item for item in document["elements"] if item.get("id") != element_id]
        if len(retained) == len(document["elements"]):
            raise KeyError(element_id)
        document["elements"] = retained
        self._write_document(document)

    def delete_folder(self, folder_id: str) -> None:
        document = self._load_document()
        folders = document["folders"]
        self._folder_by_id(folders, folder_id)
        if any(folder.get("parent_id") == folder_id for folder in folders) or any(
            item.get("folder_id") == folder_id for item in document["elements"]
        ):
            raise ValueError("Folder is not empty")
        document["folders"] = [folder for folder in folders if folder.get("id") != folder_id]
        self._write_document(document)

    @staticmethod
    def _clean_name(name: str, kind: str) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError(f"{kind} name cannot be empty")
        if "/" in clean_name or "\\" in clean_name:
            raise ValueError(f"{kind} name cannot contain / or \\")
        return clean_name

    @staticmethod
    def _normalize_path(value: str) -> str:
        return "/".join(part for part in value.replace("\\", "/").split("/") if part)

    @staticmethod
    def _folder_by_id(folders: list[dict[str, Any]], folder_id: str) -> dict[str, Any]:
        folder = next((item for item in folders if item.get("id") == folder_id), None)
        if folder is None:
            raise KeyError(folder_id)
        return folder

    def _require_folder(self, folders: list[dict[str, Any]], folder_id: str | None) -> None:
        if folder_id is not None:
            self._folder_by_id(folders, folder_id)

    @staticmethod
    def _require_unique_element_name(
        elements: list[dict[str, Any]],
        name: str,
        folder_id: str | None,
        exclude_id: str | None = None,
    ) -> None:
        if any(
            item.get("id") != exclude_id
            and item.get("folder_id") == folder_id
            and str(item.get("name", "")).casefold() == name.casefold()
            for item in elements
        ):
            raise ValueError("An element with this name already exists in the target folder")

    @staticmethod
    def _require_unique_folder_name(
        folders: list[dict[str, Any]],
        name: str,
        parent_id: str | None,
        exclude_id: str | None = None,
    ) -> None:
        if any(
            folder.get("id") != exclude_id
            and folder.get("parent_id") == parent_id
            and str(folder.get("name", "")).casefold() == name.casefold()
            for folder in folders
        ):
            raise ValueError("A folder with this name already exists here")

    def _folder_path(self, folder_id: str, folders: list[dict[str, Any]]) -> str:
        names: list[str] = []
        seen: set[str] = set()
        current_id: str | None = folder_id
        while current_id is not None:
            if current_id in seen:
                raise ValueError("Folder hierarchy contains a cycle")
            seen.add(current_id)
            folder = self._folder_by_id(folders, current_id)
            names.append(folder["name"])
            current_id = folder.get("parent_id")
        return "/".join(reversed(names))

    def _element_path(self, item: dict[str, Any], folders: list[dict[str, Any]]) -> str:
        folder_id = item.get("folder_id")
        if folder_id is None:
            return str(item["name"])
        return f"{self._folder_path(folder_id, folders)}/{item['name']}"

    @staticmethod
    def _descendant_folder_ids(folder_id: str, folders: list[dict[str, Any]]) -> set[str]:
        descendants: set[str] = set()
        frontier = [folder_id]
        while frontier:
            current = frontier.pop()
            children = [folder["id"] for folder in folders if folder.get("parent_id") == current]
            for child_id in children:
                if child_id not in descendants:
                    descendants.add(child_id)
                    frontier.append(child_id)
        return descendants

    def _write_document(self, document: dict[str, Any]) -> None:
        document["version"] = LIBRARY_VERSION
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
