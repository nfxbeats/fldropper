"""Bounded, read-only FST metadata reader. Never loads plugin state.

See FST_FORMAT.md for observed layouts, sources, and coverage limitations.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import struct

MAX_PREFIX = 64 * 1024


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


def inspect_bytes(data: bytes, file_size: int | None = None) -> FstMetadata:
    """Read the first outer InternalName, with strict bounds and no payload search."""
    version_text = None
    version: tuple[int, ...] = ()
    encoding = None

    def unknown(reason: str) -> FstMetadata:
        return FstMetadata(fl_version=version_text, encoding=encoding, reason=reason)

    try:
        if data[:4] != b"FLhd" or len(data) < 22:
            return unknown("Missing or truncated FLhd header")
        header_size = struct.unpack_from("<I", data, 4)[0]
        if header_size != 6 or data[8:10] != b"\x30\x00":
            return unknown("Unsupported header size or non-plugin-preset format")
        if data[14:18] != b"FLdt":
            return unknown("Missing FLdt event chunk")
        size = struct.unpack_from("<I", data, 18)[0]
        if 22 + size != (file_size if file_size is not None else len(data)):
            return unknown("Declared FLdt length does not match file size")
        end = min(22 + size, len(data), MAX_PREFIX)
        cursor = 22
        while cursor < end:
            event = data[cursor]
            cursor += 1
            if event == 213:
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
                if length < 2 or length > 512:
                    return unknown("Invalid plugin-name length")
                raw = data[cursor:cursor + length]
                selected_encoding = encoding or ("utf-16-le" if raw.endswith(b"\x00\x00") else "ascii")
                terminator = b"\x00\x00" if selected_encoding == "utf-16-le" else b"\x00"
                if not raw.endswith(terminator) or (selected_encoding == "utf-16-le" and length % 2):
                    return unknown("Invalid plugin-name termination or encoding")
                name = raw[:-len(terminator)].decode(selected_encoding)
                if not name or not all(32 <= ord(c) < 127 for c in name):
                    return unknown("Plugin name contains unsupported/control characters")
                return FstMetadata(name, version_text, selected_encoding, cursor)
            cursor += length
    except (ValueError, struct.error, UnicodeError):
        return unknown("Invalid binary or text metadata")
    return unknown("No outer plugin name in metadata prefix")


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
