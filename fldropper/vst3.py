"""Documented VST3 folders and additive, local configuration updates."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .config import Config, Destination
from .discovery import known_folder
from .transfers import checked_ancestors


# Steinberg VST3 Developer Portal, Plug-in Locations; Microsoft KNOWNFOLDERID.
WINDOWS_FOLDERS = (
    ("vst3-windows-user", "VST3 plugins (current user)", "BCBD3057-CA5C-4622-B42D-BC56DB0AE516"),
    ("vst3-windows-global", "VST3 plugins (all users)", "6365D5A7-0F0D-45E5-87F6-0DA56B6A4F7D"),
    ("vst3-windows-x86", "VST3 plugins (32-bit)", "DE974D24-D9C6-4D3E-BF91-F4455120B917"),
)


def candidates() -> list[tuple[str, str, Path]]:
    if sys.platform == "win32":
        return [(key, name, base / "VST3") for key, name, guid in WINDOWS_FOLDERS
                if (base := known_folder(guid)) is not None]
    if sys.platform == "darwin":
        return [
            ("vst3-macos-user", "VST3 plugins (current user)", Path.home() / "Library/Audio/Plug-ins/VST3"),
            ("vst3-macos-global", "VST3 plugins (all users)", Path("/Library/Audio/Plug-ins/VST3")),
        ]
    return []


def verified_destinations() -> list[Destination]:
    """Require an existing readable directory and reject redirected ancestors.

    Write permission is checked by the actual transfer, without probe files or
    elevation. Discovery never creates folders or loads plugin binaries.
    """
    found, seen = [], set()
    for key, name, path in candidates():
        try:
            if not path.is_absolute() or not path.is_dir() or not os.access(path, os.R_OK | os.X_OK):
                continue
            checked_ancestors(path)
            identity = os.path.normcase(str(path))
            if identity not in seen:
                seen.add(identity)
                found.append(Destination(key, name, [".vst3"], path=str(path)))
        except (OSError, ValueError):
            continue
    return found


def add_missing_destinations(config: Config, verified: list[Destination]) -> list[str]:
    """Add newly verified routes, preserving edits and intentional deletions.

    Only successfully verified routes are recorded; absent folders are retried
    on later launches even after the application/catalog has been updated.
    """
    previous = config.extra.get("discovered_vst3_destinations", [])
    handled = set(previous) if isinstance(previous, list) and all(isinstance(x, str) for x in previous) else set()
    ids = {d.id for d in config.destinations}
    paths = {os.path.normcase(str(Path(d.path))) for d in config.destinations if d.root == "absolute" and d.path}
    added = []
    for destination in verified:
        if destination.id in handled:
            continue
        identity = os.path.normcase(str(Path(destination.path)))
        if destination.id not in ids and identity not in paths:
            config.destinations.append(destination)
            ids.add(destination.id)
            paths.add(identity)
            added.append(destination.name)
        handled.add(destination.id)
    if handled:
        config.extra["discovered_vst3_destinations"] = sorted(handled)
    return added
