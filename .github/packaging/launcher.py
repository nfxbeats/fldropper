"""Frozen-only entry point; source launches retain their existing behavior."""
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication
from fldropper import config


def packaged_config_path() -> Path:
    return Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation)) / "config.json"


# Do this before ui imports default_config_path. Never write into the bundle.
QApplication.setOrganizationName("FLDropper")
QApplication.setApplicationName("FLDropper")
config.default_config_path = packaged_config_path

if "--packaging-smoke-test" in sys.argv:
    import pyflp
    from tempfile import TemporaryDirectory
    from fldropper.branding import APP_IMAGE
    from fldropper.ui import MainWindow, create_application
    app = create_application()
    assert APP_IMAGE.is_file(), "Missing packaged artwork"
    assert (Path(config.__file__).parent / "defaults.json").is_file()
    with TemporaryDirectory() as temporary:
        window = MainWindow(config_path=Path(temporary) / "config.json")
        window.show()
        app.processEvents()
        window.close()
else:
    from fldropper.ui import main
    main()
