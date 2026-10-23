"""Read script imports as data; never import or execute dropped Python code."""
from __future__ import annotations

import ast
import io
import tokenize
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_SCRIPT_BYTES = 512 * 1024
SCRIPT_ROUTES = {"piano": "Piano Roll scripts", "edison": "Edison audio scripts", "hardware": "MIDI hardware scripts"}


@dataclass
class ScriptInfo:
    imports: list[tuple[str, int]]
    kinds: set[str]
    problem: str = ""


def inspect_script(data: bytes) -> ScriptInfo:
    if len(data) > MAX_SCRIPT_BYTES:
        return ScriptInfo([], set(), "Script exceeds metadata scan limit")
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
        tree = ast.parse(data.decode(encoding))
    except (SyntaxError, UnicodeError, LookupError, ValueError, RecursionError):
        return ScriptInfo([], set(), "Cannot parse script imports")
    imports = []
    kinds = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "", node.level))
            imports.extend((".".join(filter(None, (node.module, alias.name))), node.level)
                           for alias in node.names if alias.name != "*")
    for name, level in imports:
        if not level:
            root = name.split(".")[0]
            if root == "flpianoroll":
                kinds.add("piano")
            elif root == "enveditor":
                kinds.add("edison")
    return ScriptInfo(imports, kinds)


def classify_scripts(files: dict[Path, ScriptInfo]) -> tuple[str | None, list[str]]:
    """Follow only imports resolving to files already supplied in the package."""
    entries = [p for p in files if p.suffix.casefold() == ".pyscript" or
               (p.suffix.casefold() == ".py" and p.name.casefold().startswith("device_"))]
    notes = []
    detected = set()
    unresolved = False
    for entry in entries:
        kinds = {"hardware"} if entry.suffix.casefold() == ".py" else set()
        pending, visited = [entry], set()
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            info = files[path]
            kinds.update(info.kinds)
            if info.problem:
                notes.append(f"{path}: {info.problem}")
                unresolved = True
            for name, level in info.imports:
                base = path.parent
                for _ in range(max(0, level - 1)):
                    base = base.parent
                module = Path(*name.split(".")) if name else Path()
                bases = [base] if level else [base, Path()]
                found = False
                for root in bases:
                    options = [root / module.with_suffix(".py"), root / module / "__init__.py"] if name else []
                    pending.extend(p for p in options if p in files)
                    found |= any(p in files for p in options)
                if not found and name and (level or name.split(".")[0] not in
                        sys.stdlib_module_names | {"flpianoroll", "enveditor", "device", "midi", "channels", "mixer", "patterns", "playlist", "transport", "ui", "general", "arrangement", "plugins", "utils", "screen", "launchMapPages", "autogen"}):
                    notes.append(f"{path}: dependency {'.' * level}{name} is not among supplied modules; verify it is available in FL Studio.")
        if len(kinds) != 1:
            unresolved = True
            notes.append(f"{entry}: script type is missing or conflicting; choose a destination.")
        detected.update(kinds)
    if not entries:
        notes.append("Python helpers have no supplied .pyscript or device_*.py entry point; choose a destination.")
    if len(detected) > 1:
        notes.append("This package contains different script types; keep it together only in a destination you choose, or import each script folder separately.")
    notes.append("Only supplied files are copied. Include all local Python helpers and resources; external or dynamic dependencies cannot be verified.")
    return (next(iter(detected)) if len(detected) == 1 and not unresolved else None), notes
