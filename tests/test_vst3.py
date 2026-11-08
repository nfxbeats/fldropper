"""Destination upgrades and VST3 copying use temporary content only."""
import os
import threading
import time
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from fldropper import vst3
from fldropper.catalog import CATALOG_REVISION
from fldropper.config import Config, Destination, load, save
from fldropper.routing import fst_package_groups, package_matches
from fldropper.transfers import Job, run_jobs, scan


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    from fldropper.ui import create_application
    import shiboken6
    existing = QApplication.instance()
    application = existing or create_application()
    yield application
    if existing is None:
        shiboken6.delete(application)


def test_windows_paths_use_known_folders(monkeypatch, tmp_path):
    monkeypatch.setattr(vst3.sys, "platform", "win32")
    bases = {guid: tmp_path / key for key, _, guid in vst3.WINDOWS_FOLDERS}
    monkeypatch.setattr(vst3, "known_folder", bases.get)
    assert [path for _, _, path in vst3.candidates()] == [base / "VST3" for base in bases.values()]
    monkeypatch.setattr(vst3, "known_folder", lambda _: None)
    assert vst3.candidates() == []


def test_macos_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(vst3.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert [p for _, _, p in vst3.candidates()] == [
        tmp_path / "Library/Audio/Plug-ins/VST3", Path("/Library/Audio/Plug-ins/VST3")]
    monkeypatch.setattr(vst3.sys, "platform", "linux")
    assert vst3.candidates() == []


def test_verification_existing_readable_unique_directories_only(monkeypatch, tmp_path):
    folder = tmp_path / "VST3"
    folder.mkdir()
    file = tmp_path / "file"
    file.touch()
    monkeypatch.setattr(vst3, "candidates", lambda: [
        ("good", "Good", folder), ("duplicate", "Duplicate", folder),
        ("absent", "Absent", tmp_path / "absent"), ("file", "File", file)])
    assert [d.id for d in vst3.verified_destinations()] == ["good"]
    assert not (tmp_path / "absent").exists()
    monkeypatch.setattr(vst3.os, "access", lambda *_: False)
    assert vst3.verified_destinations() == []


def test_verification_rejects_redirected_ancestors(monkeypatch, tmp_path):
    monkeypatch.setattr(vst3, "candidates", lambda: [("test", "Test", tmp_path)])
    def redirected(_):
        raise ValueError("link/reparse point")
    monkeypatch.setattr(vst3, "checked_ancestors", redirected)
    assert vst3.verified_destinations() == []


def test_upgrade_preserves_settings_retries_and_remembers_deletion(tmp_path):
    config = Config(extra={"catalog_revision": CATALOG_REVISION, "future_field": {"preserve": True}})
    path = tmp_path / "config.json"
    route = Destination("vst3-test", "VST3 test", [".vst3"], path=str(tmp_path))
    assert vst3.add_missing_destinations(config, []) == []
    save(config, path)
    config = load(path)
    assert vst3.add_missing_destinations(config, [route]) == ["VST3 test"]
    route.enabled = False
    route.path = str(tmp_path / "custom")
    config.last_selection = route.id
    save(config, path)
    config = load(path)
    assert vst3.add_missing_destinations(config, [Destination(route.id, "Original", [".vst3"], path=str(tmp_path))]) == []
    assert config.destinations[0].path.endswith("custom")
    assert not config.destinations[0].enabled
    assert config.last_selection == route.id
    assert config.extra["future_field"] == {"preserve": True}
    config.destinations.clear()
    save(config, path)
    config = load(path)
    assert vst3.add_missing_destinations(config, [route]) == []
    assert config.destinations == []


def test_upgrade_preserves_existing_custom_route_to_same_folder(tmp_path):
    existing = Destination("mine", "My plugins", [], path=str(tmp_path), enabled=False)
    config = Config(destinations=[existing])
    assert vst3.add_missing_destinations(config, [Destination("vst3-test", "VST3", [".vst3"], path=str(tmp_path))]) == []
    assert config.destinations == [existing]


@pytest.mark.parametrize("zipped", [False, True])
def test_bundle_routes_and_copies_intact_with_resources(tmp_path, zipped):
    bundle = tmp_path / "Plugin.vst3"
    contents = {
        "Contents/x86_64-win/Plugin.vst3": b"dummy binary, never loaded",
        "Contents/Resources/preset.fst": b"opaque bundled preset",
        "Contents/Resources/helper.py": b"import flpianoroll",
        "Contents/Info.plist": b"bundle metadata",
    }
    for name, data in contents.items():
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    source = bundle
    if zipped:
        source = tmp_path / "Plugin.zip"
        with zipfile.ZipFile(source, "w") as archive:
            for name, data in contents.items():
                archive.writestr("Plugin.vst3/" + name, data)
    config = Config()
    package = scan(source, config.zip_limits, threading.Event())
    assert not package.has_scripts
    assert package.file_plugins == {}
    assert fst_package_groups(package) == [package]
    target = tmp_path / "destination"
    target.mkdir()
    dest = Destination("vst3-test", "VST3", [".vst3"], path=str(target))
    assert package_matches(config, package.files, dest, source) == (True, [])
    assert not package_matches(config, package.files, Destination("presets", "Presets", [".fst"]), source)[0]
    result = run_jobs([Job(package, target, package.extraction_target(target))], config.zip_limits,
                      threading.Event(), lambda _: "skip", lambda _: None)
    assert result.copied == len(contents)
    assert result.failed == 0
    for name, data in contents.items():
        assert (target / "Plugin.vst3" / name).read_bytes() == data
        assert (bundle / name).read_bytes() == data
    assert source.exists()


def test_startup_updates_saved_config_and_routing_dialog(app, monkeypatch, tmp_path):
    from PySide6.QtTest import QTest
    from fldropper import ui
    folder = tmp_path / "VST3"
    folder.mkdir()
    monkeypatch.setattr(ui, "verified_destinations", lambda: [
        Destination("vst3-test", "VST3", [".vst3"], path=str(folder))])
    monkeypatch.setattr(ui.MainWindow, "detect_missing_roots", lambda _: None)
    path = tmp_path / "config.json"
    window = ui.MainWindow(path)
    window.check_destination_updates()
    deadline = time.monotonic() + 10
    while window.worker is not None and time.monotonic() < deadline:
        QTest.qWait(10)
        time.sleep(.001)
    assert window.worker is None
    assert any(d.id == "vst3-test" for d in load(path).destinations)
    assert window.destinations.findData("vst3-test") >= 0
    bundle = tmp_path / "Plugin.vst3"
    bundle.mkdir()
    (bundle / "binary").write_bytes(b"never loaded")
    package = scan(bundle, window.config.zip_limits, threading.Event())
    dialog = ui.RoutingDialog(window.config, [package], "auto")
    assert dialog.choices[0].currentData() == "vst3-test"
    window.config.destinations.append(Destination("second", "Other VST3", [".vst3"], path=str(tmp_path)))
    ambiguous = ui.RoutingDialog(window.config, [package], "auto")
    assert ambiguous.choices[0].currentData() is None
    dialog.close()
    ambiguous.close()
    window.close()
    app.processEvents()


def test_startup_preserves_malformed_config(app, monkeypatch, tmp_path):
    from fldropper import ui
    path = tmp_path / "config.json"
    path.write_text("{broken json", encoding="utf-8")
    monkeypatch.setattr(ui, "verified_destinations", lambda: pytest.fail("Must not check after invalid configuration"))
    window = ui.MainWindow(path)
    window.check_destination_updates()
    assert window.worker is None
    assert path.read_text(encoding="utf-8") == "{broken json"
    window.close()
    app.processEvents()
