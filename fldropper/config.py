from __future__ import annotations

import copy
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any

from .catalog import CATALOG_REVISION, PLUGIN_PRESETS, CHANNEL_PRESETS, PLUGIN_EXTENSIONS


class ConfigError(ValueError):
    pass


def default_config_path() -> Path:
    """Keep each source-folder installation's settings beside its launchers."""
    return Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class Destination:
    id: str
    name: str
    extensions: list[str]
    root: str = "absolute"
    path: str = ""
    enabled: bool = True
    automatic: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def accepts(self, path: Path) -> bool:
        return not self.extensions or path.suffix.casefold() in self.extensions

    def to_dict(self) -> dict:
        return self.extra | {k: getattr(self, k) for k in
                             ("id", "name", "extensions", "root", "path", "enabled", "automatic")}


@dataclass
class Config:
    roots: dict[str, str] = field(default_factory=lambda: {"user_data": "", "shared_data": "", "fl_install": ""})
    destinations: list[Destination] = field(default_factory=list)
    last_selection: str = "auto"
    zip_limits: dict[str, int] = field(default_factory=lambda: {
        "entries": 10000, "bytes": 2 * 1024**3, "ratio": 200})
    extra: dict[str, Any] = field(default_factory=dict)
    always_replace_duplicates: bool = False

    def to_dict(self) -> dict:
        return self.extra | {"version": 1, "roots": self.roots,
                             "destinations": [d.to_dict() for d in self.destinations],
                             "last_selection": self.last_selection, "zip_limits": self.zip_limits,
                             "always_replace_duplicates": self.always_replace_duplicates}


def plugin_destinations() -> list[Destination]:
    return [Destination(f"preset-{id}", name, list(PLUGIN_EXTENSIONS.get(id, (".fst",))), "user_data",
                        f"Presets/Plugin presets/{category}/{folder}")
            for id, name, category, folder in PLUGIN_PRESETS]


def channel_destinations() -> list[Destination]:
    return [Destination(f"channel-{id}", name, [".fst"], "fl_install", path)
            for id, name, path in CHANNEL_PRESETS]


def default_config() -> Config:
    # Deliberately unconfigured entries are visible, editable, and never guessed.
    return Config(destinations=[
        Destination("piano", "Piano Roll scripts", [".pyscript", ".py"], "user_data", "Settings/Piano roll scripts"),
        Destination("edison", "Edison audio scripts", [".pyscript", ".py"], "user_data", "Settings/Audio scripts"),
        Destination("hardware", "MIDI hardware scripts", [".py"], "user_data", "Settings/Hardware"),
        Destination("zge", "ZGameEditor objects (.zgeproj)", [".zgeproj"], "shared_data",
                    "ZGameEditor Visualizer/Effects"),
        Destination("visualizer", "Visualizer plugin presets", [".fst"], "user_data",
                    "Presets/Plugin presets/Effects/ZGameEditor Visualizer"),
        Destination("channel-presets", "Channel presets", [".fst"], "user_data", "Presets/Channel presets"),
        Destination("channel-envelopes", "Channel envelopes", [".chenv"], "user_data", "Presets/Channel envelopes"),
        Destination("mixer", "Mixer presets", [".fst"], "user_data", "Presets/Mixer presets"),
        Destination("generator", "Generator presets", [".fst"], "user_data", "Presets/Plugin presets/Generators"),
        Destination("effect", "Effect presets", [".fst"], "user_data", "Presets/Plugin presets/Effects"),
        Destination("samples", "Samples (choose an organization folder)", [".wav", ".aif", ".aiff", ".mp3", ".ogg", ".flac"]),
        Destination("scores", "Scores", [".fsc", ".mid", ".midi"], "user_data", "Presets/Scores"),
        Destination("projects", "FL Studio projects (choose a folder)", [".flp", ".zip"]),
    ] + plugin_destinations() + channel_destinations(), extra={"catalog_revision": CATALOG_REVISION})


def relative_path(value: str) -> Path:
    win = PureWindowsPath(value)
    if win.is_absolute() or win.drive or win.root or ".." in win.parts:
        raise ConfigError(f"Relative path must stay beneath its root: {value}")
    from .transfers import safe_relative
    if value:
        safe_relative(value)
    return Path(*win.parts)


def resolve(config: Config, dest: Destination) -> tuple[Path, Path]:
    if dest.root == "absolute":
        if not dest.path or not Path(dest.path).is_absolute():
            raise ConfigError(f"Choose an absolute folder for {dest.name} in Settings.")
        base = Path(dest.path)
        target = base
    else:
        raw = config.roots.get(dest.root, "")
        if not raw:
            raise ConfigError(f"Set the {dest.root.replace('_', ' ')} folder in Settings.")
        base = Path(raw)
        target = base / relative_path(dest.path)
    return base, target


def parse(data: dict) -> Config:
    if not isinstance(data, dict):
        raise ConfigError("Configuration must be a JSON object.")
    data = copy.deepcopy(data)
    version = data.get("version", 0)
    if version == 0:  # Explicit migration of the original draft's root names.
        data["roots"] = data.get("roots", {"user_data": data.pop("user_data", ""),
                                            "fl_install": data.pop("fl_install", "")})
        data["version"] = 1
    elif version != 1:
        raise ConfigError(f"Unsupported configuration version: {version}")
    roots = data.get("roots", {})
    if not isinstance(roots, dict) or any(not isinstance(v, str) for v in roots.values()):
        raise ConfigError("Roots must contain folder strings.")
    roots = {"user_data": "", "shared_data": "", "fl_install": ""} | roots
    for value in roots.values():
        if value and not Path(value).is_absolute():
            raise ConfigError(f"Root must be absolute: {value}")
    destinations = []
    ids = set()
    if not isinstance(data.get("destinations", []), list):
        raise ConfigError("Destinations must be a list.")
    for item in data.get("destinations", []):
        if not isinstance(item, dict):
            raise ConfigError("Every destination must be an object.")
        known = {k: item[k] for k in ("id", "name", "extensions", "root", "path", "enabled", "automatic") if k in item}
        try:
            d = Destination(**known)
        except TypeError as exc:
            raise ConfigError(f"Invalid destination: {exc}") from exc
        if not isinstance(d.id, str) or not d.id or d.id == "auto" or d.id in ids:
            raise ConfigError("Destination IDs must be unique, nonempty, and not 'auto'.")
        ids.add(d.id)
        if not isinstance(d.name, str) or not d.name.strip() or not isinstance(d.path, str):
            raise ConfigError("Destination names and paths must be strings; names cannot be empty.")
        if type(d.enabled) is not bool or type(d.automatic) is not bool:
            raise ConfigError("Enabled and automatic must be booleans.")
        if not isinstance(d.extensions, list) or any(not isinstance(e, str) or not e.strip() or
             any(c in e for c in '/\\:*? ') for e in d.extensions):
            raise ConfigError(f"Invalid extensions for {d.name}.")
        d.extensions = sorted({"." + e.strip().lower().lstrip(".") for e in d.extensions})
        if not d.extensions:
            d.automatic = False
        if d.root not in ("absolute", "user_data", "shared_data", "fl_install"):
            raise ConfigError(f"Invalid root for {d.name}.")
        if d.root != "absolute":
            relative_path(d.path)
        elif d.path and not Path(d.path).is_absolute():
            raise ConfigError(f"Absolute destination requires an absolute path: {d.name}")
        d.extra = {k: v for k, v in item.items() if k not in known}
        destinations.append(d)
    if not isinstance(data.get("zip_limits", {}), dict):
        raise ConfigError("ZIP limits must be an object.")
    limits = {"entries": 10000, "bytes": 2 * 1024**3, "ratio": 200} | data.get("zip_limits", {})
    if any(type(limits[k]) is not int or limits[k] <= 0 for k in ("entries", "bytes", "ratio")):
        raise ConfigError("ZIP limits must be positive integers.")
    selection = data.get("last_selection", "auto")
    if not isinstance(selection, str):
        raise ConfigError("Last selection must be a string.")
    always_replace = data.get("always_replace_duplicates", False)
    if type(always_replace) is not bool:
        raise ConfigError("Always replace duplicates must be a boolean.")
    return Config(roots, destinations, selection, limits,
                  {k: v for k, v in data.items() if k not in
                   ("version", "roots", "destinations", "last_selection", "zip_limits", "always_replace_duplicates")},
                  always_replace_duplicates=always_replace)


def load(path: Path) -> Config:
    if not path.exists():
        # Ship a portable snapshot of known routes/preferences for new copies.
        # Existing config files never receive this snapshot over their edits.
        defaults = Path(__file__).with_name("defaults.json")
        if not defaults.exists():
            return default_config()
        config = load(defaults)
        config.roots = {key: "" for key in config.roots}
        return config
    try:
        config = parse(json.loads(path.read_text(encoding="utf-8")))
        # Add this catalog expansion once, without overwriting customizations or
        # reintroducing destinations a user deletes after the update.
        revision = config.extra.get("catalog_revision", 0)
        if revision == 0:
            ids = {d.id for d in config.destinations}
            config.destinations.extend(d for d in plugin_destinations() if d.id not in ids)
        if revision in (0, 1):
            for d in config.destinations:
                if (d.id == "zge" and d.root == "fl_install" and
                        d.path == "Plugins/Fruity/Effects/ZGameEditor Visualizer/Effects"):
                    d.root, d.path = "shared_data", "ZGameEditor Visualizer/Effects"
                elif d.id == "visualizer" and d.root == "absolute" and not d.path:
                    d.root = "user_data"
                    d.path = "Presets/Plugin presets/Effects/ZGameEditor Visualizer"
            # Existing content roots can identify the shared parent without guessing
            # when they have the documented FL Studio child name and ZGE folder.
            content = Path(config.roots["user_data"]) if config.roots["user_data"] else None
            if (not config.roots["shared_data"] and content is not None and
                    content.name.casefold() == "fl studio" and
                    (content.parent / "ZGameEditor Visualizer").is_dir()):
                config.roots["shared_data"] = str(content.parent)
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 3:
            if not any(d.id == "preset-patcher-generator" for d in config.destinations):
                config.destinations.extend(d for d in plugin_destinations() if d.id == "preset-patcher-generator")
            for d in config.destinations:
                if d.id == "preset-patcher" and d.name == "Patcher":
                    d.name = "Patcher (Effect)"
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 4:
            for destination in default_config().destinations:
                if destination.id in ("edison", "hardware") and not any(d.id == destination.id for d in config.destinations):
                    config.destinations.append(destination)
            for d in config.destinations:
                if d.id == "piano" and d.extensions == [".pyscript"]:
                    d.extensions.append(".py")
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 5:
            if not any(d.id == "preset-fpc" for d in config.destinations):
                existing = next((d for d in config.destinations if d.name.casefold() == "fpc" or
                                 str(d.extra.get("plugin_name", "")).casefold() == "fpc"), None)
                if existing is not None:
                    if config.last_selection == existing.id:
                        config.last_selection = "preset-fpc"
                    existing.id = "preset-fpc"
                else:
                    config.destinations.extend(d for d in plugin_destinations() if d.id == "preset-fpc")
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 6:
            if not any(d.id == "channel-3x-osc" for d in config.destinations):
                existing = next((d for d in config.destinations if
                                 d.name.replace(" ", "").casefold() == "3xosc" or
                                 str(d.extra.get("plugin_name", "")).replace(" ", "").casefold() == "3xosc"), None)
                known = channel_destinations()[0]
                if existing is not None:
                    if config.last_selection == existing.id:
                        config.last_selection = known.id
                    existing.id, existing.name = known.id, known.name
                    existing.root, existing.path = known.root, known.path
                else:
                    config.destinations.append(known)
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 7:
            for d in config.destinations:
                if d.id in ("generator", "effect") and d.root == "absolute" and not d.path:
                    d.root = "user_data"
                    d.path = "Presets/Plugin presets/" + ("Generators" if d.id == "generator" else "Effects")
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 8:
            if not any(d.id == "scores" for d in config.destinations):
                existing = next((d for d in config.destinations if d.id == "midi"), None)
                if existing:
                    if config.last_selection == existing.id:
                        config.last_selection = "scores"
                    existing.id, existing.name = "scores", "Scores"
                    existing.extensions = list(dict.fromkeys([".fsc", ".mid", ".midi", *existing.extensions]))
                    if not existing.path:
                        existing.root, existing.path = "user_data", "Presets/Scores"
                else:
                    config.destinations.extend(d for d in default_config().destinations if d.id == "scores")
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 9:
            existing = next((d for d in config.destinations if d.id == "preset-morphine"), None)
            if existing is None:
                existing = next((d for d in config.destinations if d.name.casefold() == "morphine" or
                                 str(d.extra.get("plugin_name", "")).casefold() == "morphine"), None)
                if existing:
                    if config.last_selection == existing.id:
                        config.last_selection = "preset-morphine"
                    existing.id = "preset-morphine"
                else:
                    existing = next(d for d in plugin_destinations() if d.id == "preset-morphine")
                    config.destinations.append(existing)
            existing.extensions = list(dict.fromkeys([*existing.extensions, ".fst", ".mrp"]))
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 10:
            existing = next((d for d in config.destinations if d.id == "preset-toxic-biohazard"), None)
            if existing is None:
                existing = next((d for d in config.destinations if d.name.casefold() == "toxic biohazard" or
                                 str(d.extra.get("plugin_name", "")).casefold() == "toxic biohazard"), None)
                if existing:
                    if config.last_selection == existing.id:
                        config.last_selection = "preset-toxic-biohazard"
                    existing.id = "preset-toxic-biohazard"
                else:
                    existing = next(d for d in plugin_destinations() if d.id == "preset-toxic-biohazard")
                    config.destinations.append(existing)
            existing.extensions = list(dict.fromkeys([*existing.extensions, ".fst", ".txd"]))
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 11:
            for d in config.destinations:
                if d.id == "preset-toxic-biohazard":
                    d.extensions = list(dict.fromkeys([*d.extensions, ".tbio"]))
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 12:
            for d in config.destinations:
                if (d.id == "preset-poizone" or d.name.casefold() == "poizone" or
                        str(d.extra.get("plugin_name", "")).casefold() == "poizone"):
                    d.extensions = list(dict.fromkeys([*d.extensions, ".fxp"]))
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 13:
            existing = next((d for d in config.destinations if d.id == "preset-sawer"), None)
            if existing is None:
                existing = next((d for d in config.destinations if d.name.casefold() == "sawer" or
                                 str(d.extra.get("plugin_name", "")).casefold() == "sawer"), None)
                if existing:
                    if config.last_selection == existing.id:
                        config.last_selection = "preset-sawer"
                    existing.id = "preset-sawer"
                else:
                    existing = next(d for d in plugin_destinations() if d.id == "preset-sawer")
                    config.destinations.append(existing)
            for d in config.destinations:
                if (d.id == "preset-sawer" or d.name.casefold() == "sawer" or
                        str(d.extra.get("plugin_name", "")).casefold() == "sawer"):
                    d.extensions = list(dict.fromkeys([*d.extensions, ".fst", ".sawer"]))
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 14:
            if not any(d.id == "mixer" for d in config.destinations):
                existing = next((d for d in config.destinations if d.name.casefold() in ("mixer preset", "mixer presets")), None)
                if existing:
                    if config.last_selection == existing.id:
                        config.last_selection = "mixer"
                    existing.id = "mixer"
                    existing.extensions = list(dict.fromkeys([*existing.extensions, ".fst"]))
                else:
                    config.destinations.extend(d for d in default_config().destinations if d.id == "mixer")
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 15:
            if not any(d.id == "channel-envelopes" for d in config.destinations):
                existing = next((d for d in config.destinations if d.name.casefold() == "channel envelopes"), None)
                if existing:
                    if config.last_selection == existing.id:
                        config.last_selection = "channel-envelopes"
                    existing.id = "channel-envelopes"
                    existing.extensions = list(dict.fromkeys([*existing.extensions, ".chenv"]))
                else:
                    config.destinations.extend(d for d in default_config().destinations if d.id == "channel-envelopes")
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 16:
            if not any(d.id == "channel-presets" for d in config.destinations):
                existing = next((d for d in config.destinations if d.name.casefold() == "channel presets"), None)
                if existing:
                    if config.last_selection == existing.id:
                        config.last_selection = "channel-presets"
                    existing.id = "channel-presets"
                    existing.extensions = list(dict.fromkeys([*existing.extensions, ".fst"]))
                else:
                    config.destinations.extend(d for d in default_config().destinations if d.id == "channel-presets")
            config.extra["catalog_revision"] = CATALOG_REVISION
        if revision < 17:
            old, new = "Fruity Wrapper - Albino3 64", "Fruity Wrapper - Albino3"
            for d in config.destinations:
                if d.name == old or d.extra.get("plugin_name") == old:
                    if d.name == old:
                        d.name = new
                    if d.extra.get("plugin_name") == old:
                        d.extra["plugin_name"] = new
                    if d.root == "user_data" and d.path == "Presets/Plugin presets/Generators/" + old:
                        d.path = "Presets/Plugin presets/Generators/" + new
            if isinstance(config.extra.get("preset_name_history"), list):
                config.extra["preset_name_history"] = list(dict.fromkeys(new if n == old else n for n in config.extra["preset_name_history"]))
            config.extra["catalog_revision"] = CATALOG_REVISION
        return config
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ConfigError(f"Cannot load {path}: {exc}. Original file has been preserved.") from exc


def save(config: Config, path: Path) -> None:
    validated = parse(config.to_dict())
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(validated.to_dict(), stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
