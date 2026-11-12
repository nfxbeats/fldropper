"""macOS discovery uses synthetic bundles, never a real FL Studio installation."""
import os
import plistlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from fldropper import discovery
from fldropper.config import Config, load


def bundle(base, name, version=None):
    app = base / f"{name}.app"
    root = app / "Contents/Resources/FL"
    (root / "Plugins").mkdir(parents=True)
    binary = app / "Contents/MacOS/FL Studio"
    binary.parent.mkdir(parents=True)
    binary.touch()
    info = {"CFBundleExecutable": "FL Studio"}
    if version is not None:
        info["CFBundleShortVersionString"] = version
    with (app / "Contents/Info.plist").open("wb") as stream:
        plistlib.dump(info, stream)
    return root


def test_latest_version_uses_metadata_not_name_or_timestamp(tmp_path):
    bundle(tmp_path, "FL Studio 2025", "25.9")
    bundle(tmp_path, "FL Studio", "26.2")
    bundle(tmp_path, "FL Studio 2099", "26.1")
    bundle(tmp_path, "FL Studio 2026.10", "26.10")
    expected = tmp_path / "FL Studio 2026.10.app/Contents/Resources/FL"
    assert [c.path for c in discovery.macos_installation_suggestions([tmp_path])] == [expected]


def test_version_fallback_and_equal_versions_need_choice(tmp_path):
    first = bundle(tmp_path, "FL Studio 2026")
    second = bundle(tmp_path, "FL Studio Stable", "26.0.0")
    bundle(tmp_path, "FL Studio 2025", "25.9")
    assert {c.path for c in discovery.macos_installation_suggestions([tmp_path])} == {first, second}


def test_missing_malformed_and_incomplete_bundles(tmp_path):
    assert discovery.macos_installation_suggestions([tmp_path / "missing"]) == []
    root = bundle(tmp_path, "FL Studio 2026", "26")
    plist = root.parents[1] / "Info.plist"
    plist.write_bytes(b"broken")
    assert discovery.macos_installation_suggestions([tmp_path]) == []
    plist.write_bytes(plistlib.dumps({"CFBundleExecutable": "../elsewhere"}))
    assert discovery.macos_installation_suggestions([tmp_path]) == []
    plist.write_bytes(plistlib.dumps({"CFBundleExecutable": "missing"}))
    assert discovery.macos_installation_suggestions([tmp_path]) == []


def test_unknown_version_is_manual_fallback(tmp_path):
    unknown = bundle(tmp_path, "FL Studio Stable")
    assert [c.path for c in discovery.macos_installation_suggestions([tmp_path])] == [unknown]
    newest = bundle(tmp_path, "FL Studio 2026", "26")
    assert [c.path for c in discovery.macos_installation_suggestions([tmp_path])] == [newest]


def test_macos_default_data_and_application_locations(monkeypatch, tmp_path):
    monkeypatch.setattr(discovery.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert discovery.user_suggestions() == []
    data = tmp_path / "Documents/Image-Line/FL Studio"
    data.mkdir(parents=True)
    assert discovery.user_suggestions() == [data]
    install = bundle(tmp_path / "Applications", "FL Studio 2026", "26")
    assert install in [c.path for c in discovery.installation_suggestions()]
    monkeypatch.setattr(discovery.os, "access", lambda *_: False)
    assert discovery.user_suggestions() == []


def test_startup_populates_and_saves_default_but_preserves_saved_roots(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from fldropper.ui import MainWindow, Settings

    monkeypatch.setattr(discovery.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    data = tmp_path / "Documents/Image-Line/FL Studio"
    data.mkdir(parents=True)
    install = bundle(tmp_path / "Applications", "FL Studio 2026", "26")
    monkeypatch.setattr(discovery, "registry_candidates", lambda **_: pytest.fail("No Windows registry on Mac"))
    candidates = Settings.find_candidates()
    state = SimpleNamespace(config=Config(), config_path=tmp_path / "config.json",
                            status=SimpleNamespace(setText=lambda _: None), refresh=lambda: None)
    MainWindow.missing_roots_detected(state, candidates)
    saved = load(state.config_path)
    assert saved.roots == {"user_data": str(data), "shared_data": str(data.parent), "fl_install": str(install)}
    saved.roots = {"user_data": str(tmp_path / "custom/FL Studio"),
                   "shared_data": str(tmp_path / "custom"), "fl_install": str(tmp_path / "older")}
    state.config = saved
    MainWindow.missing_roots_detected(state, candidates)
    assert state.config.roots == saved.roots
    saved.roots["shared_data"] = ""
    MainWindow.missing_roots_detected(state, candidates)
    assert state.config.roots == saved.roots


def test_bundle_access_errors_are_ignored(monkeypatch, tmp_path):
    bundle(tmp_path, "FL Studio 2026", "26")
    monkeypatch.setattr(discovery.os, "access", lambda *_: False)
    assert discovery.macos_installation_suggestions([tmp_path]) == []


def test_windows_conventional_install_requires_markers(tmp_path):
    valid = tmp_path / "FL Studio 2026"
    (valid / "Plugins").mkdir(parents=True)
    (valid / "FL64.exe").touch()
    (tmp_path / "FL Studio stale").mkdir()
    assert discovery.install_candidates([tmp_path]) == [valid]
