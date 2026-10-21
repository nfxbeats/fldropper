"""Read-only Windows discovery; saved paths always take precedence."""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    path: Path
    source: str
    shared_root: Path | None = None


@dataclass
class PluginFolderSearch:
    matches: dict[str, list[Candidate]]
    notes: list[str]


def find_plugin_folders(roots: dict[str, str], names: list[str], cancel: threading.Event,
                        *, max_entries: int = 50000, max_depth: int = 10) -> PluginFolderSearch:
    """Find existing exact-name folders, user roots first, without following links."""
    from .transfers import Cancelled, checked_ancestors, is_link
    matches = {name: [] for name in names}
    wanted = {name.casefold(): name for name in names}
    notes = []
    seen = set()
    labels = {"user_data": "User data (preferred)", "shared_data": "Shared user data (preferred)",
              "fl_install": "Installation folder"}
    for kind in ("user_data", "shared_data", "fl_install"):
        raw = roots.get(kind)
        if not raw:
            continue
        base = Path(raw)
        try:
            validate_root(base, kind)
            checked_ancestors(base)
        except (ValueError, OSError) as exc:
            notes.append(str(exc))
            continue
        pending = [(base, 0)]
        examined = 0
        while pending:
            if cancel.is_set():
                raise Cancelled()
            folder, depth = pending.pop()
            key = str(folder).casefold()
            if key in seen:
                continue
            seen.add(key)
            plugin = wanted.get(folder.name.casefold())
            if plugin:
                matches[plugin].append(Candidate(folder, labels[kind]))
            if depth >= max_depth:
                notes.append(f"Depth limit reached at {folder}; browse manually if needed.")
                continue
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        if cancel.is_set():
                            raise Cancelled()
                        examined += 1
                        if examined > max_entries:
                            break
                        try:
                            path = Path(entry.path)
                            if entry.is_dir(follow_symlinks=False) and not is_link(path):
                                pending.append((path, depth + 1))
                        except OSError as exc:
                            notes.append(f"Cannot inspect {entry.path}: {exc}")
            except OSError as exc:
                notes.append(f"Cannot search {folder}: {exc}")
            if examined > max_entries:
                notes.append(f"Search limit reached beneath {base}; browse manually if needed.")
                break
    for candidates in matches.values():
        candidates.sort(key=lambda c: (c.source == "Installation folder", str(c.path).casefold()))
    return PluginFolderSearch(matches, notes)


def _data_root(raw: str) -> Path | None:
    """Shared data is an Image-Line parent, while our routes use its FL Studio child."""
    base = Path(os.path.expandvars(raw.strip()))
    if not base.is_absolute():
        return None
    for path in (base / "FL Studio", base):
        try:
            if (path.is_dir() and (path / "Settings").is_dir() and
                    any((path / marker).is_dir() for marker in ("Presets", "Projects")) and
                    os.access(path, os.R_OK | os.X_OK)):
                return path
        except OSError:
            pass
    return None


def registry_candidates(registry=None, *, kind: str = "user_data") -> list[Candidate]:
    """Shared Paths first, then existing version keys. Never write the registry.

    `registry` permits testing without importing Windows APIs on other platforms.
    Version keys are enumerated, not tied to an assumed current version number.
    """
    if kind not in ("user_data", "fl_install"):
        raise ValueError(f"Unknown discovery kind: {kind}")
    if registry is None:
        if os.name != "nt":
            return []
        import winreg as registry

    hives = [("HKCU", registry.HKEY_CURRENT_USER), ("HKLM", registry.HKEY_LOCAL_MACHINE)]
    views = [("64-bit", registry.KEY_WOW64_64KEY), ("32-bit", registry.KEY_WOW64_32KEY)]
    found: list[Candidate] = []
    seen = set()

    def read(hive_name, hive, view_name, view, key_path):
        values = ("Shared data",) if kind == "user_data" else ("Install path", "FL Studio")
        for value_name in values:
            try:
                with registry.OpenKey(hive, key_path, 0, registry.KEY_READ | view) as key:
                    value, value_type = registry.QueryValueEx(key, value_name)
                if value_type not in (registry.REG_SZ, registry.REG_EXPAND_SZ) or not isinstance(value, str):
                    continue
                if kind == "user_data":
                    path = _data_root(value)
                else:
                    path = Path(os.path.expandvars(value.strip().strip('"')))
                    if value_name == "FL Studio":
                        if path.name.casefold() != "fl64.exe":
                            continue
                        path = path.parent
                    if not path.is_absolute():
                        continue
                    validate_root(path, "fl_install")
                if path is not None and (identity := str(path).casefold()) not in seen:
                    seen.add(identity)
                    shared_root = None
                    if kind == "user_data":
                        base = Path(os.path.expandvars(value.strip()))
                        if path == base / "FL Studio":
                            shared_root = base
                        elif path == base and path.name.casefold() == "fl studio":
                            shared_root = path.parent
                    found.append(Candidate(path, f"{hive_name}\\{key_path} · {value_name} · {view_name}", shared_root))
            except (OSError, ValueError):
                pass

    shared = r"Software\Image-Line\Shared\Paths"
    for hive_name, hive in hives:
        for view_name, view in views:
            read(hive_name, hive, view_name, view, shared)
    if found and kind == "user_data":
        return found

    parent = r"Software\Image-Line"
    for hive_name, hive in hives:
        for view_name, view in views:
            try:
                with registry.OpenKey(hive, parent, 0, registry.KEY_READ | view) as key:
                    versions = []
                    index = 0
                    while True:
                        try:
                            name = registry.EnumKey(key, index)
                            index += 1
                        except OSError:
                            break
                        if re.fullmatch(r"FL Studio \d+(?:\.\d+)*", name, re.IGNORECASE):
                            versions.append(name)
                for version in sorted(versions, key=str.casefold):
                    version_path = parent + "\\" + version
                    read(hive_name, hive, view_name, view, version_path)
                    # Only probe actual existing path/general branches, not invented values.
                    branches = []
                    try:
                        with registry.OpenKey(hive, version_path, 0, registry.KEY_READ | view) as key:
                            index = 0
                            while True:
                                try:
                                    name = registry.EnumKey(key, index)
                                    index += 1
                                except OSError:
                                    break
                                if name.casefold() in ("paths", "general"):
                                    branches.append(name)
                    except OSError:
                        continue
                    for branch in branches:
                        read(hive_name, hive, view_name, view, version_path + "\\" + branch)
            except OSError:
                continue
    return found


def validate_root(path: Path, kind: str) -> None:
    if not path.is_dir():
        raise ValueError(f"Folder does not exist: {path}")
    if not os.access(path, os.R_OK | os.X_OK):
        raise ValueError(f"Cannot read folder: {path}")
    if kind == "fl_install" and not (
        (path / "FL64.exe").is_file() and (path / "Plugins").is_dir()
    ):
        raise ValueError(f"Not a verified FL Studio installation (needs FL64.exe and Plugins): {path}")


def documents_folder() -> Path | None:
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    import uuid

    class GUID(ctypes.Structure):
        _fields_ = [("data", ctypes.c_ubyte * 16)]

    guid = GUID.from_buffer_copy(uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7").bytes_le)
    result = wintypes.LPWSTR()
    shell = ctypes.windll.shell32
    shell.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD,
                                         wintypes.HANDLE, ctypes.POINTER(wintypes.LPWSTR)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    if shell.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(result)) != 0:
        return None
    try:
        return Path(result.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(result, ctypes.c_void_p))


def install_candidates(bases: list[Path] | None = None) -> list[Path]:
    if bases is None:
        bases = [Path(value) / "Image-Line" for key in ("ProgramFiles", "ProgramFiles(x86)")
                 if (value := os.environ.get(key))]
    candidates = set()
    for base in bases:
        try:
            for path in base.glob("FL Studio*"):
                try:
                    validate_root(path, "fl_install")
                    candidates.add(path)
                except (ValueError, OSError):
                    pass
        except OSError:
            pass
    return sorted(candidates, key=lambda p: str(p).casefold())


def installation_suggestions() -> list[Candidate]:
    candidates = registry_candidates(kind="fl_install") + [
        Candidate(path, "Conventional installation suggestion") for path in install_candidates()]
    unique = {}
    for candidate in candidates:
        unique.setdefault(str(candidate.path).casefold(), candidate)

    def version(candidate: Candidate):
        # Folder names identify a likely latest version, never proof of the active version.
        match = re.fullmatch(r"FL Studio[ -]*(\d+(?:\.\d+)*)", candidate.path.name, re.IGNORECASE)
        return tuple(int(n) for n in match[1].split(".")) if match else ()

    return sorted(unique.values(), key=lambda c: (version(c), str(c.path).casefold()), reverse=True)


def user_suggestions(*, include_registry: bool = True) -> list[Path]:
    registered = registry_candidates() if include_registry else []
    if registered:
        return [candidate.path for candidate in registered]
    docs = documents_folder()
    if docs is None:
        return []
    # Suggestions only: the active root must be confirmed against FL's File settings.
    return [p for p in (docs / "Image-Line" / "FL Studio", docs / "Image-Line") if p.is_dir()]
