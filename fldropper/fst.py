"""Bounded, read-only FST metadata reader. Never loads plugin state.

See FST_FORMAT.md for observed layouts, sources, and coverage limitations.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import struct

from construct import ConstructError
from pyflp._events import AsciiEvent, UnicodeEvent
from pyflp.plugin import WrapperEvent, VSTPluginEvent, _WrapperFlags
from pyflp.project import FileFormat

MAX_PREFIX = 64 * 1024
WRAPPER_NAMES = {"fruity wrapper", "fruit wrapper"}


def _hosted_plugin_id(payload: bytes) -> int | None:
    if len(payload) < 4 or struct.unpack_from("<I", payload)[0] not in (8, 10, 12):
        return None
    cursor = 4
    while cursor + 12 <= len(payload):
        event, size = struct.unpack_from("<IQ", payload, cursor)
        cursor += 12
        if cursor + size > len(payload):
            return None
        if event == 51:
            return int.from_bytes(payload[cursor:cursor + size], "little") if size == 4 else None
        cursor += size
    return None


def _hosted_plugin_name(payload: bytes, declared_size: int) -> str | None:
    """Read VST identity records, skipping the plugin's own state by length."""
    if len(payload) < 4 or struct.unpack_from("<I", payload)[0] not in (8, 10, 12):
        return None
    cursor = 4
    while cursor + 12 <= len(payload):
        event, size = struct.unpack_from("<IQ", payload, cursor)
        start = cursor
        cursor += 12
        if cursor + size > declared_size:
            return None
        if event == 54:  # PyFLP VSTPluginEvent Name: factory plugin name.
            if not 0 < size <= 512 or cursor + size > len(payload):
                return None
            try:
                # Decode only this metadata record through PyFLP. Do not parse,
                # decompress, or search the potentially large State record.
                parsed = VSTPluginEvent.STRUCT.parse(payload[:4] + payload[start:cursor + size])
                name = parsed["events"][0]["data"].rstrip("\0")
            except (ConstructError, UnicodeError, IndexError, KeyError, ValueError):
                return None
            return name if name and all(c.isprintable() for c in name) else None
        cursor += size
    return None


def _has_version_banner(data: bytes, cursor: int, end: int) -> bool:
    """Validate the length-prefixed UTF-16 banner at an event boundary."""
    length = 0
    for shift in range(0, 35, 7):
        if cursor >= end:
            return False
        value = data[cursor]
        cursor += 1
        length |= (value & 0x7f) << shift
        if not value & 0x80:
            break
    else:
        return False
    if length > 512 or length % 2 or cursor + length > end:
        return False
    try:
        banner = data[cursor:cursor + length].decode("utf-16-le")
    except UnicodeError:
        return False
    return re.fullmatch(r"FL Studio \d+(?:\.\d+)+\x00", banner) is not None


@dataclass(frozen=True)
class FstMetadata:
    plugin_name: str | None = None
    fl_version: str | None = None
    encoding: str | None = None
    name_offset: int | None = None
    reason: str = ""
    plugin_kind: str | None = None
    fst_type: str | None = None
    display_name: str | None = None
    hosted_plugin_name: str | None = None

    vst2_id: int | None = None
    database_name: str | None = None

    @property
    def channel_name(self) -> str | None:
        return self.display_name


def inspect_bytes(data: bytes, file_size: int | None = None) -> FstMetadata:
    """Read the first outer InternalName, with strict bounds and no payload search."""
    version_text = None
    version: tuple[int, ...] = ()
    encoding = None
    plugin_name = None
    name_offset = None
    plugin_kind = None
    fst_type = None
    display_name = None
    hosted_plugin_name = None
    vst2_id = None

    def unknown(reason: str) -> FstMetadata:
        return FstMetadata(plugin_name, version_text, encoding, name_offset, reason, plugin_kind, fst_type, display_name, hosted_plugin_name, vst2_id)

    def identified() -> FstMetadata:
        return FstMetadata(plugin_name, version_text, encoding, name_offset, plugin_kind=plugin_kind, fst_type=fst_type, display_name=display_name, hosted_plugin_name=hosted_plugin_name, vst2_id=vst2_id)

    try:
        if data[:4] != b"FLhd" or len(data) < 22:
            return unknown("Missing or truncated FLhd header")
        header_size = struct.unpack_from("<I", data, 4)[0]
        file_format = struct.unpack_from("<H", data, 8)[0]
        if header_size != 6 or file_format not in (FileFormat.PluginState, FileFormat.ChannelState, FileFormat.InsertState):
            return unknown("Unsupported header size or non-plugin-preset format")
        fst_type = "channel" if file_format == FileFormat.ChannelState else "plugin"
        if data[14:18] != b"FLdt":
            return unknown("Missing FLdt event chunk")
        size = struct.unpack_from("<I", data, 18)[0]
        if 22 + size != (file_size if file_size is not None else len(data)):
            return unknown("Declared FLdt length does not match file size")
        if file_format == FileFormat.InsertState:
            # The outer state is the complete mixer insert. Never identify it
            # by one of the effect plugins nested inside its event stream.
            if not size:
                return unknown("Empty mixer preset event chunk")
            plugin_name, fst_type = "Mixer preset", "mixer"
            return identified()
        end = min(22 + size, len(data), MAX_PREFIX)
        cursor = 22
        while cursor < end:
            event = data[cursor]
            cursor += 1
            if event == 213:
                if plugin_name and plugin_name.casefold() not in WRAPPER_NAMES:
                    return identified()
                if not plugin_name:
                    return unknown("Reached opaque plugin state before outer plugin name")
            if event < 192:
                length = 1 if event < 64 else 2 if event < 128 else 4
                if event == 172 and data[cursor:cursor + 4] == b"\x01\x01\x00\xc0":
                    # Recognize the observed three-byte layout by its framing,
                    # independent of the FL release. Require a valid banner so
                    # an ordinary four-byte payload is not silently shortened.
                    if not _has_version_banner(data, cursor + 4, end):
                        return unknown("Invalid event-172 version banner")
                    length = 3
            else:
                length = 0
                for shift in range(0, 35, 7):
                    if cursor >= end:
                        return unknown("Truncated event length")
                    value = data[cursor]
                    cursor += 1
                    length |= (value & 0x7f) << shift
                    if not value & 0x80:
                        break
                else:
                    return unknown("Oversized event length varint")
            if event == 213:
                if cursor + length > 22 + size:
                    return unknown("Wrapper data exceeds declared event chunk")
                vst2_id = _hosted_plugin_id(data[cursor:min(cursor + length, end)])
                hosted_plugin_name = _hosted_plugin_name(data[cursor:min(cursor + length, end)], length)
                return identified() if hosted_plugin_name else unknown("Hosted plugin name unavailable; channel label is not a plugin identity")
            if cursor + length > end:
                return unknown("Event exceeds available metadata prefix")
            if event == 199:
                raw_version = data[cursor:cursor + length]
                if not re.fullmatch(rb"\d+(?:\.\d+){1,3}\x00", raw_version):
                    return unknown("Invalid FL version metadata")
                version_text = raw_version[:-1].decode("ascii")
                version = tuple(int(part) for part in version_text.split("."))
                encoding = "utf-16-le" if version[:2] >= (11, 5) else "ascii"
            if event == 201:
                if plugin_name:
                    return identified()  # Never replace the first outer identity.
                if length < 2 or length > 512:
                    return unknown("Invalid plugin-name length")
                raw = data[cursor:cursor + length]
                selected_encoding = encoding or ("utf-16-le" if raw.endswith(b"\x00\x00") else "ascii")
                terminator = b"\x00\x00" if selected_encoding == "utf-16-le" else b"\x00"
                if not raw.endswith(terminator) or (selected_encoding == "utf-16-le" and length % 2):
                    return unknown("Invalid plugin-name termination or encoding")
                # Use PyFLP's text schema directly: its event-object constructor
                # has an empty-Enum incompatibility with Python 3.12.
                decoder = UnicodeEvent if selected_encoding == "utf-16-le" else AsciiEvent
                name = decoder.STRUCT.parse(raw)
                if "\x00" in raw[:-len(terminator)].decode(selected_encoding):
                    return unknown("Plugin name contains embedded terminators")
                if not name and fst_type == "channel":
                    plugin_name, name_offset, encoding = "Channel preset", cursor, selected_encoding
                    cursor += length
                    continue
                if not name or not all(32 <= ord(c) < 127 for c in name):
                    return unknown("Plugin name contains unsupported/control characters")
                plugin_name, name_offset, encoding = name, cursor, selected_encoding
            if event == 203 and plugin_name and 2 <= length <= 512:
                raw = data[cursor:cursor + length]
                decoder = UnicodeEvent if encoding == "utf-16-le" else AsciiEvent
                terminator = b"\x00\x00" if encoding == "utf-16-le" else b"\x00"
                if raw.endswith(terminator):
                    value = decoder.STRUCT.parse(raw)
                    if value and all(c.isprintable() for c in value):
                        display_name = value
            if event == 212 and length >= 18:
                # PyFLP WrapperEvent: uint16 flags at payload offset 16;
                # Generator is bit 4. Never inspect opaque plugin state.
                flags = WrapperEvent.STRUCT.parse(data[cursor:cursor + length])["flags"]
                plugin_kind = "generator" if flags & _WrapperFlags.Generator else "effect"
            cursor += length
    except (ValueError, struct.error, UnicodeError, ConstructError):
        return unknown("Invalid binary or text metadata")
    return identified() if plugin_name else unknown("No outer plugin name in metadata prefix")


def plugin_name_from_bytes(data: bytes, file_size: int | None = None) -> str | None:
    return inspect_bytes(data, file_size).plugin_name


def inspect_file(path: Path) -> FstMetadata:
    if path.suffix.casefold() != ".fst":
        return FstMetadata(reason="Not an FST file")
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            stream.seek(0)
            return inspect_bytes(stream.read(MAX_PREFIX), size)
    except OSError as exc:
        return FstMetadata(reason=f"Cannot read file: {exc}")


def read_plugin_name(path: Path) -> str | None:
    return inspect_file(path).plugin_name
