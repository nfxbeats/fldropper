from pathlib import Path
from dataclasses import replace

from .config import Config, Destination
from .catalog import PLUGIN_PRESETS
from .transfers import Package


def fst_package_groups(package: Package, *, split: bool = True) -> list[Package]:
    """Separate FSTs by outer plugin while preserving package-relative paths."""
    if not split or not package.file_plugins or any(p.suffix.casefold() == ".flp" for p in package.files):
        return [package]  # Project packages retain their intact-ZIP choice.
    other_primary = {".flp", ".pyscript", ".zgeproj", ".mid", ".midi"}
    companions = [p for p in package.files if p not in package.file_plugins and p.suffix.casefold() not in other_primary]
    remaining = [p for p in package.files if p not in package.file_plugins and p not in companions]
    groups: dict[str, list[Path]] = {}
    names = {}
    for path, name in package.file_plugins.items():
        key = name.casefold() if name else ""
        groups.setdefault(key, []).append(path)
        names[key] = name
    result = [replace(package, selected_files=paths + companions, plugin_name=names[key],
                      group_name=names[key] or "Unidentified FST presets", is_fst_group=True)
              for key, paths in groups.items()]
    if remaining:
        result.append(replace(package, selected_files=remaining + companions, group_name="Other content"))
    return result


def plugin_destination_id(plugin_name: str | None) -> str | None:
    if not plugin_name:
        return None
    names = {name.casefold(): f"preset-{id}" for id, name, _, _ in PLUGIN_PRESETS}
    names["zgameeditor visualizer"] = "visualizer"
    return names.get(plugin_name.casefold())


def matches_plugin(dest: Destination, plugin_name: str) -> bool:
    tag = dest.extra.get("plugin_name")
    return (dest.id == plugin_destination_id(plugin_name) or
            (isinstance(tag, str) and tag.casefold() == plugin_name.casefold()) or
            dest.name.casefold() == plugin_name.casefold())


def compatible(config: Config, path: Path, automatic: bool = False,
               plugin_name: str | None = None) -> list[Destination]:
    choices = [d for d in config.destinations if d.enabled and d.accepts(path)
            and (not automatic or (d.automatic and bool(d.extensions)))]
    if automatic and path.suffix.casefold() == ".fst" and plugin_name:
        return [d for d in choices if matches_plugin(d, plugin_name)]
    return choices


def package_matches(config: Config, paths: list[Path], dest: Destination) -> tuple[bool, list[str]]:
    """Recognized content must match; unknown companion assets travel with it."""
    if not dest.extensions:
        return True, []
    recognized = {ext for d in config.destinations for ext in d.extensions} - {".zip"}
    primary = {".pyscript", ".zgeproj", ".fst", ".flp", ".mid", ".midi"}
    present = [p for p in paths if p.suffix.casefold() in primary]
    if not present:
        present = [p for p in paths if p.suffix.casefold() in recognized]
    bad = [str(p) for p in present if not dest.accepts(p)]
    return bool(present) and not bad, bad
