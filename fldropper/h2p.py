"""Read bounded u-he H2P product metadata without interpreting preset state."""
from pathlib import Path
import re

HEADER_BYTES = 64 * 1024


def plugin_name(data: bytes) -> str:
    # Metadata prose may contain fake directives. Strip comments before reading
    # the actual line-oriented header, keeping newlines at comment boundaries.
    text = data.decode("latin-1").lstrip("\xef\xbb\xbf")
    text = re.sub(r"/\*.*?\*/", "\n", text, flags=re.S)
    if "/*" in text:
        text = text.split("/*", 1)[0]
    text = re.sub(r"//[^\r\n]*", "", text)
    names = re.findall(r"^#AM=([^\r\n]+)\r?$", text, re.M)
    if len(names) != 1:
        raise ValueError("H2P plugin identity (#AM) is missing or ambiguous.")
    name = names[0].strip()
    if not name or len(name) > 128 or not all(c.isprintable() for c in name):
        raise ValueError("Invalid H2P plugin name.")
    if not re.search(r"^#Vers=\d+\r?$", text, re.M) or not re.search(r"^#Endian=(?:little|big)\r?$", text, re.M):
        raise ValueError("Missing or invalid H2P format header.")
    return name


def inspect_bytes(data: bytes, lookup):
    if lookup is None:
        from .fxp import InstalledPluginLookup
        lookup = InstalledPluginLookup(None)
    return lookup.resolve_name(plugin_name(data))


def inspect_file(path: Path, lookup):
    with path.open("rb") as stream:
        return inspect_bytes(stream.read(HEADER_BYTES), lookup)
