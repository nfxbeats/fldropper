"""Detect object packages by contents and preserve companion assets."""
import os
import threading
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from fldropper.config import Destination, default_config
from fldropper.routing import package_choices
from fldropper.transfers import Job, Package, run_jobs, scan


@pytest.mark.parametrize("zipped", [False, True])
def test_zge_package_suggestion_summary_and_copy(tmp_path, zipped):
    from PySide6.QtWidgets import QApplication
    from fldropper.ui import RoutingDialog

    app = QApplication.instance() or QApplication([])
    content = {"Atmosphere/Cloud.ZGEPROJ": b"object", "Assets/cloud.png": b"image",
               "README.txt": b"instructions"}
    source = tmp_path / ("Collection.zip" if zipped else "Collection")
    if zipped:
        with zipfile.ZipFile(source, "w") as archive:
            for name, data in content.items():
                archive.writestr(name, data)
    else:
        source.mkdir()
        for name, data in content.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    config = default_config()
    target = tmp_path / "destination"
    target.mkdir()
    config.roots["shared_data"] = str(target)
    # A manual accept-any route must not prevent the unique automatic suggestion.
    config.destinations.append(Destination("custom", "General", [], path=str(target), automatic=False))
    package = scan(source, config.zip_limits, threading.Event())
    assert [d.id for d in package_choices(config, package)] == ["zge"]
    dialog = RoutingDialog(config, [package], "auto")
    assert dialog.choices[0].currentData() == "zge"
    assert dialog.modes[0].currentData() is False
    dialog.close()
    output = package.displayed_target(target)
    result = run_jobs([Job(package, target, output)], config.zip_limits,
                      threading.Event(), lambda _: "skip", lambda _: None)
    assert result.copied == len(content)
    assert result.failed == 0
    for name, data in content.items():
        assert (output / name).read_bytes() == data
    assert source.exists()


def test_mixed_primary_content_does_not_suggest_zge_or_projects(tmp_path):
    config = default_config()
    package = Package(tmp_path / "mixed.zip", [Path("object.zgeproj"), Path("song.flp")], is_zip=True)
    assert package_choices(config, package) == []


def test_zge_routes_respect_ambiguity_disabled_and_manual_only(tmp_path):
    config = default_config()
    custom = Destination("custom-zge", "Other objects", [".zgeproj"], path=str(tmp_path))
    config.destinations.append(custom)
    package = Package(tmp_path / "objects.zip", [Path("object.zgeproj")], is_zip=True)
    assert [d.id for d in package_choices(config, package)] == ["zge", "custom-zge"]
    custom.automatic = False
    assert [d.id for d in package_choices(config, package)] == ["zge"]
    next(d for d in config.destinations if d.id == "zge").enabled = False
    assert package_choices(config, package) == []
