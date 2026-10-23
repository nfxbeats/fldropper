"""Bounded VST2 FXP identity inspection; never loads or decodes plugin state."""
from dataclasses import dataclass
from pathlib import Path
import struct

from .catalog import FXP_PLUGIN_IDS

HEADER_BYTES = 60


@dataclass(frozen=True)
class FxpMetadata:
    plugin_name: str | None = None
    plugin_kind: str | None = None
    plugin_id: str | None = None
    preset_name: str | None = None
    reason: str = ""


def inspect_bytes(data: bytes, file_size: int | None = None) -> FxpMetadata:
    size = len(data) if file_size is None else file_size
    if len(data) < 56 or size < 56 or data[:4] != b"CcnK":
        return FxpMetadata(reason="Missing or truncated FXP header")
    magic = data[8:12]
    if magic not in (b"FPCh", b"FxCk"):
        return FxpMetadata(reason="Not a single-program FXP format")
    plugin_id = data[16:20]
    known = FXP_PLUGIN_IDS.get(plugin_id)
    declared = struct.unpack_from(">I", data, 4)[0]
    # The supplied PoiZone file counts the size field itself (size - 4),
    # whereas standard FXP excludes both the magic and size fields (size - 8).
    if declared != size - 8 and not (known and declared == size - 4):
        return FxpMetadata(reason="FXP declared length does not match file size")
    if struct.unpack_from(">I", data, 12)[0] != 1:
        return FxpMetadata(reason="Unsupported FXP format version")
    if magic == b"FPCh":
        if len(data) < 60 or size < 60 or struct.unpack_from(">I", data, 56)[0] != size - 60:
            return FxpMetadata(reason="FXP chunk length does not match file size")
    elif 56 + 4 * struct.unpack_from(">I", data, 24)[0] != size:
        return FxpMetadata(reason="FXP parameter count does not match file size")
    preset_name = data[28:56].split(b"\0", 1)[0].decode("latin-1")
    return FxpMetadata(known[0] if known else None, known[1] if known else None,
                       plugin_id.decode("latin-1"), preset_name,
                       "" if known else "Unrecognized FXP plugin ID")


def inspect_file(path: Path) -> FxpMetadata:
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            stream.seek(0)
            return inspect_bytes(stream.read(HEADER_BYTES), size)
    except OSError as exc:
        return FxpMetadata(reason=f"Cannot read FXP file: {exc}")


def _product_key(name: str) -> str:
    # u-he's observed VST3 factory name is "Diva(x64)" while H2P declares
    # "Diva". Remove only a terminal architecture tag, never arbitrary suffixes.
    import re
    return re.sub(r"\s*\(x(?:64|86)\)$", "", name, flags=re.I).strip().casefold()


class InstalledPluginLookup:
    """Lazily index verified FST identity metadata once per import batch."""

    def __init__(self, user_data: Path | None, cancel=None):
        self.root = user_data / "Presets/Plugin database/Installed" if user_data else None
        self.cancel = cancel
        self.entries = None
        self.names = {}

    def _build(self):
        from .fst import inspect_file
        from .transfers import is_link
        if self.entries is None:
            import os
            self.entries = {}
            if self.root and self.root.is_dir():
                for category, kind in (("Generators", "generator"), ("Effects", "effect")):
                    base = self.root / category
                    if not base.is_dir() or is_link(base):
                        continue
                    for folder, dirs, files in os.walk(base, followlinks=False):
                        dirs[:] = sorted(d for d in dirs if not is_link(Path(folder) / d))
                        for filename in sorted(files):
                            if self.cancel and self.cancel.is_set():
                                from .transfers import Cancelled
                                raise Cancelled()
                            path = Path(folder) / filename
                            if path.suffix.casefold() != ".fst" or is_link(path):
                                continue
                            info = inspect_file(path)
                            if info.plugin_name and info.hosted_plugin_name and not info.reason:
                                entry = (path, info, kind)
                                self.names.setdefault(_product_key(info.hosted_plugin_name), []).append(entry)
                                if info.vst2_id is not None:
                                    self.entries.setdefault(info.vst2_id, []).append(entry)

    def resolve(self, metadata: FxpMetadata):
        from .fst import inspect_file
        if not metadata.plugin_id:
            raise ValueError(metadata.reason or "Invalid FXP header")
        self._build()
        ident = int.from_bytes(metadata.plugin_id.encode("latin-1"), "big")
        matches = self.entries.get(ident, [])
        if not matches:
            raise ValueError(f"No installed-plugin FST matches FXP ID 0x{ident:08X}. Scan the plugin in FL Studio Plugin Manager and try again.")
        identities = {(info.hosted_plugin_name.casefold(), kind) for _, info, kind in matches}
        if len(identities) != 1:
            raise ValueError(f"Multiple installed plugins match FXP ID 0x{ident:08X}; import cannot determine a unique plugin.")
        path, info, kind = matches[0]
        # Read the matched FST again to use its current routing metadata.
        from dataclasses import replace
        info = inspect_file(path)
        if info.vst2_id != ident or not info.hosted_plugin_name or info.reason:
            raise ValueError(f"Matched plugin FST could not be read: {path}")
        return replace(info, plugin_kind=kind, fst_type="plugin")


    def resolve_name(self, name: str):
        """Resolve a native preset's declared product name, including VST3 FSTs."""
        from dataclasses import replace
        from .fst import inspect_file
        self._build()
        matches = self.names.get(_product_key(name), [])
        if not matches:
            raise ValueError(f"No installed-plugin FST matches H2P plugin '{name}'. Scan the plugin in FL Studio Plugin Manager and try again.")
        if len({(_product_key(info.hosted_plugin_name), kind) for _, info, kind in matches}) != 1:
            raise ValueError(f"Conflicting installed-plugin FST matches for H2P plugin '{name}'.")
        path, _, kind = matches[0]
        info = inspect_file(path)
        if info.reason or not info.hosted_plugin_name or _product_key(info.hosted_plugin_name) != _product_key(name):
            raise ValueError(f"Matched plugin FST could not be read: {path}")
        return replace(info, plugin_kind=kind, fst_type="plugin")
