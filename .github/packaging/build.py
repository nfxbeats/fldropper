"""Build, smoke-check, and archive the app on the current Windows/Mac runner."""
from pathlib import Path
import os
import platform
import runpy
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = HERE / "dist"


def archive_label():
    # Read the checkout, independent of any previously installed package.
    version = runpy.run_path(str(ROOT / "fldropper" / "__init__.py"))["__version__"]
    return f"FLDropper-{version}-{'Windows' if sys.platform == 'win32' else 'macOS'}-{platform.machine()}"


def main():
    if sys.platform not in ("win32", "darwin"):
        raise SystemExit("Build on Windows or macOS.")
    windows = sys.platform == "win32"
    env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(HERE / "build" / "cache"),
               PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir",
        "--windowed", "--name", "FL Dropper", "--paths", str(ROOT),
        "--specpath", str(HERE / "build"),
        "--workpath", str(HERE / "build" / "work"),
        "--distpath", str(OUTPUT),
        "--add-data", f"{ROOT / 'fldropper/assets'}:fldropper/assets",
        "--add-data", f"{ROOT / 'fldropper/defaults.json'}:fldropper",
        "--collect-all", "pyflp",
        "--icon", str(ROOT / "fldropper/assets" /
                      ("FL_Dropper.ico" if windows else "FL_Dropper.png")),
        str(HERE / "launcher.py"),
    ], cwd=HERE, env=env, check=True)
    executable = (OUTPUT / "FL Dropper" / "FL Dropper.exe" if windows else
                  OUTPUT / "FL Dropper.app" / "Contents" / "MacOS" / "FL Dropper")
    # Test the distributable, never the incomplete executable in build/.
    subprocess.run([str(executable), "--packaging-smoke-test"],
                   env=dict(env, QT_QPA_PLATFORM="offscreen"), cwd=OUTPUT,
                   check=True, timeout=60)
    label = archive_label()
    archive = OUTPUT / f"{label}.zip"
    if windows:
        shutil.make_archive(str(OUTPUT / label), "zip", OUTPUT, "FL Dropper")
    else:
        # Preserve executable permissions and bundle symlinks in the Mac archive.
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(OUTPUT / "FL Dropper.app"), str(archive)], check=True)
    print(f"Distributable: {archive}")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"artifact_name={label}\n")
            stream.write(f"archive_path={archive.as_posix()}\n")


if __name__ == "__main__":
    main()
