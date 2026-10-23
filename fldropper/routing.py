from pathlib import Path
from dataclasses import replace

from .config import Config, Destination
from .catalog import PLUGIN_PRESETS, NATIVE_PRESET_PLUGINS
from .transfers import Package


def needs_plugin_name(package: Package) -> bool:
    return (not package.has_scripts and package.route_path.suffix.casefold() in (".fst", ".fxp", ".h2p") and
            (not package.plugin_name or package.plugin_name.casefold() in ("fruity wrapper", "fruit wrapper")))


def fst_package_groups(package: Package, *, split: bool = True) -> list[Package]:
    """Separate FSTs by outer plugin while preserving package-relative paths."""
    if not split or package.has_scripts or not package.file_plugins or any(p.suffix.casefold() == ".flp" for p in package.files):
        return [package]  # Project packages retain their intact-ZIP choice.
    other_primary = {".flp", ".pyscript", ".zgeproj", ".mid", ".midi", ".fsc", ".fxp", ".h2p"} | NATIVE_PRESET_PLUGINS.keys()
    companions = [p for p in package.files if p not in package.file_plugins and p.suffix.casefold() not in other_primary]
    remaining = [p for p in package.files if p not in package.file_plugins and p not in companions]
    groups = {}
    names = {}
    for path, name in package.file_plugins.items():
        generic = not name or name.casefold() in ("fruity wrapper", "fruit wrapper")
        kind = package.file_plugin_kinds.get(path) if generic or name.casefold() == "patcher" else None
        state_type = package.file_fst_types.get(path) or ("plugin" if path.suffix.casefold() in NATIVE_PRESET_PLUGINS or path.suffix.casefold() in (".fxp", ".h2p") else None)
        key = (name.casefold() if name else "", kind, state_type, path if generic else None)
        groups.setdefault(key, []).append(path)
        names[key] = name
    result = [replace(package, selected_files=paths + companions, plugin_name=names[key], plugin_kind=key[1], fst_type=key[2],
                      display_name=package.file_display_names.get(paths[0]),
                      hosted_plugin_name=package.file_hosted_plugin_names.get(paths[0]),
                      group_name=((f"{names[key]} ({key[1].title()})" if key[1] else names[key] or "Unidentified FST presets")
                                  + (" — Channel state" if key[2] == "channel" else "")), is_fst_group=True)
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


def matches_plugin(dest: Destination, plugin_name: str, plugin_kind: str | None = None, fst_type: str | None = None) -> bool:
    tag = dest.extra.get("plugin_name")
    if plugin_kind and dest.extra.get("plugin_kind") and dest.extra["plugin_kind"] != plugin_kind:
        return False
    if plugin_name.replace(" ", "").casefold() == "3xosc" and fst_type == "channel":
        return dest.id == "channel-3x-osc"
    if dest.id == "channel-3x-osc":
        return False
    if plugin_name.casefold() == "patcher":
        known = {"preset-patcher": "effect", "preset-patcher-generator": "generator"}
        identity = dest.id in known or (isinstance(tag, str) and tag.casefold() == "patcher") or dest.name.casefold() in ("patcher", "patcher (effect)", "patcher (generator)")
        kind = dest.extra.get("plugin_kind") or known.get(dest.id)
        if not kind:
            parts = dest.path.replace("\\", "/").casefold().split("/")
            kind = "generator" if "generators" in parts else "effect" if "effects" in parts else None
        return identity and (not plugin_kind or kind == plugin_kind)
    return (dest.id == plugin_destination_id(plugin_name) or
            (isinstance(tag, str) and tag.casefold() == plugin_name.casefold()) or
            dest.name.casefold() == plugin_name.casefold())


def compatible(config: Config, path: Path, automatic: bool = False,
               plugin_name: str | None = None, plugin_kind: str | None = None, fst_type: str | None = None) -> list[Destination]:
    choices = [d for d in config.destinations if d.enabled and d.accepts(path)
            and (not automatic or (d.automatic and bool(d.extensions)))]
    if automatic and path.suffix.casefold() == ".fst" and plugin_name:
        return [d for d in choices if matches_plugin(d, plugin_name, plugin_kind, fst_type)]
    if automatic and path.suffix.casefold() in (".fxp", ".h2p"):
        return [d for d in choices if plugin_name and matches_plugin(d, plugin_name, plugin_kind)]
    if automatic and path.suffix.casefold() in (".fsc", ".mid", ".midi"):
        return [d for d in choices if d.id == "scores"]
    if automatic and path.suffix.casefold() in NATIVE_PRESET_PLUGINS:
        return [d for d in choices if matches_plugin(d, NATIVE_PRESET_PLUGINS[path.suffix.casefold()], "generator")]
    return choices


def package_choices(config: Config, package: Package, automatic: bool = True) -> list[Destination]:
    if not package.has_scripts:
        primary = {p.suffix.casefold() for p in package.planned_files} & ({".fsc", ".mid", ".midi", ".fst", ".flp", ".pyscript", ".zgeproj", ".fxp", ".h2p"} | NATIVE_PRESET_PLUGINS.keys())
        if automatic and primary and primary <= {".fsc", ".mid", ".midi"}:
            return compatible(config, Path("score.fsc"), automatic)
        return compatible(config, package.route_path, automatic, package.plugin_name, package.plugin_kind, package.fst_type)
    choices = [d for d in config.destinations if d.enabled and (not automatic or d.automatic)]
    if automatic:
        return [d for d in choices if package.script_kind and
                not (package.script_kind == "hardware" and package.hardware_nested) and
                (d.id == package.script_kind or d.extra.get("script_type") == package.script_kind)]
    return [d for d in choices if
            (not package.script_kind or d.id not in ("piano", "edison", "hardware") or d.id == package.script_kind) and
            (not d.extensions or any(d.accepts(p) for p in package.planned_files))]


def group_loose_scripts(packages: list[Package], cancel=None) -> list[Package]:
    """Keep explicitly dropped sibling scripts together, without reading siblings."""
    from .transfers import inspect_script_files
    parents = {}
    for package in packages:
        if package.source.is_file() and not package.is_zip and package.source.suffix.casefold() in (".py", ".pyscript"):
            parents.setdefault(package.source.parent, []).append(package)
    result = list(packages)
    for parent, group in parents.items():
        if len(group) < 2:
            continue
        files = [Path(p.source.name) for p in group]
        combined = Package(parent, files, selected_files=files)
        inspect_script_files(combined, cancel)
        entries = [p for p in files if p.suffix.casefold() == ".pyscript" or p.name.casefold().startswith("device_")]
        if len(entries) == 1:
            combined.destination_subfolder = entries[0].stem.removeprefix("device_") or "Scripts"
        result = [p for p in result if all(p is not member for member in group)]
        result.append(combined)
    return result


def package_matches(config: Config, paths: list[Path], dest: Destination) -> tuple[bool, list[str]]:
    """Recognized content must match; unknown companion assets travel with it."""
    if not dest.extensions:
        return True, []
    recognized = {ext for d in config.destinations for ext in d.extensions} - {".zip"}
    primary = {".pyscript", ".zgeproj", ".fst", ".flp", ".mid", ".midi", ".fsc", ".fxp", ".h2p"} | NATIVE_PRESET_PLUGINS.keys()
    present = [p for p in paths if p.suffix.casefold() in primary]
    if not present:
        present = [p for p in paths if p.suffix.casefold() in recognized]
    bad = [str(p) for p in present if not dest.accepts(p)]
    return bool(present) and not bad, bad
