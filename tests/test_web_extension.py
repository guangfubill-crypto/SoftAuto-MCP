import json
from pathlib import Path

from softauto.web_extension import prepare_local_extension


def test_prepare_local_extension_copies_valid_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text(
        json.dumps({"manifest_version": 3, "name": "SoftAuto Web Connector"}),
        encoding="utf-8",
    )
    (source / "popup.html").write_text("<html></html>", encoding="utf-8")
    destination = tmp_path / "installed"

    prepared = prepare_local_extension(source, destination)

    manifest = json.loads((prepared / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert (prepared / "popup.html").is_file()


def test_prepare_local_extension_requires_manifest(tmp_path: Path) -> None:
    source = tmp_path / "empty"
    source.mkdir()

    try:
        prepare_local_extension(source, tmp_path / "destination")
    except FileNotFoundError as exc:
        assert "manifest" in str(exc)
    else:
        raise AssertionError("Missing manifest should fail")


def test_bundled_extension_has_dom_automation_components() -> None:
    root = Path(__file__).resolve().parents[1] / "web-extension"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == 3
    assert "http://*/*" in manifest["host_permissions"]
    assert manifest["content_scripts"][0]["all_frames"] is True
    assert (root / "content-script.js").is_file()
    assert (root / "service-worker.js").is_file()
    content_script = (root / "content-script.js").read_text(encoding="utf-8")
    service_worker = (root / "service-worker.js").read_text(encoding="utf-8")
    assert "browser-dom" in content_script
    assert "softauto-content-ready" in content_script
    assert "setInterval(wakeBackground" in content_script
    assert "softauto-content-ready" in service_worker
