from __future__ import annotations

import os
import shutil
import stat
import tempfile
import threading
import zipfile
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Callable


class TransferError(ValueError):
    pass


class Cancelled(Exception):
    pass


def check_cancel(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise Cancelled()


def is_link(path: Path) -> bool:
    st = path.lstat()
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def safe_relative(raw: str) -> Path:
    raw = raw.replace("\\", "/")
    win = PureWindowsPath(raw)
    if not raw or win.drive or win.root or raw.startswith("/"):
        raise TransferError(f"Unsafe path: {raw!r}")
    parts = raw.rstrip("/").split("/")
    devices = {"CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$"} | {
        f"{prefix}{i}" for prefix in ("COM", "LPT") for i in "123456789¹²³"}
    for part in parts:
        if (not part or part in (".", "..") or part[-1:] in (".", " ") or
            any(c in part for c in '<>:"|?*') or any(ord(c) < 32 for c in part) or
                part.split(".")[0].upper() in devices):
            raise TransferError(f"Unsafe Windows filename: {raw!r}")
    return Path(*parts)


def checked_ancestors(path: Path) -> None:
    for parent in [path, *path.parents]:
        if parent.exists() or parent.is_symlink():
            if is_link(parent):
                raise TransferError(f"Links/reparse points are not allowed: {parent}")


def validate_target(root: Path, target: Path) -> None:
    if not root.is_absolute() or not root.is_dir():
        raise TransferError(f"Configured root must be an existing folder: {root}")
    if not target.is_relative_to(root):
        raise TransferError(f"Destination escapes configured root: {target}")
    checked_ancestors(target)


@dataclass
class Package:
    source: Path
    files: list[Path]
    skipped: list[str] = field(default_factory=list)
    is_zip: bool = False
    directories: list[Path] = field(default_factory=list)
    plugin_name: str | None = None
    file_plugins: dict[Path, str | None] = field(default_factory=dict)
    selected_files: list[Path] | None = None
    group_name: str | None = None
    is_fst_group: bool = False
    plugin_kind: str | None = None
    file_plugin_kinds: dict[Path, str | None] = field(default_factory=dict)
    script_kind: str | None = None
    has_scripts: bool = False
    script_notes: list[str] = field(default_factory=list)
    destination_subfolder: str | None = None
    hardware_nested: bool = False
    zip_root_folder: Path | None = None
    fst_type: str | None = None
    file_fst_types: dict[Path, str | None] = field(default_factory=dict)

    @property
    def planned_files(self) -> list[Path]:
        return self.files if self.selected_files is None else self.selected_files

    @property
    def plugin_label(self) -> str:
        label = self.plugin_name or ""
        if self.plugin_name == "Patcher" and self.plugin_kind:
            label += f" ({self.plugin_kind.title()})"
        if label and self.fst_type == "channel":
            label += " (Channel state)"
        return label

    @property
    def route_path(self) -> Path:
        return Path("preset.fst") if self.is_fst_group else self.source

    @property
    def folder_name(self) -> str:
        return self.destination_subfolder or (self.source.stem if self.is_zip else self.source.name)

    def extraction_target(self, base: Path) -> Path:
        # The original archive paths already contain this enclosing folder.
        # Copy them beneath base instead of prepending another wrapper.
        return base if self.is_zip and self.zip_root_folder else base / self.folder_name

    def displayed_target(self, base: Path) -> Path:
        return base / self.zip_root_folder if self.is_zip and self.zip_root_folder else base / self.folder_name


def inspect_zip(source: Path, limits: dict[str, int], cancel: threading.Event) -> list[Path]:
    checked_ancestors(source)
    paths = []
    kinds: dict[str, bool] = {}
    expanded = 0
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > limits["entries"]:
            raise TransferError("ZIP exceeds entry-count limit.")
        for info in entries:
            check_cancel(cancel)
            relative = safe_relative(info.filename)
            key = relative.as_posix().casefold()
            if key in kinds:
                raise TransferError(f"ZIP has colliding names: {relative}")
            kinds[key] = info.is_dir()
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise TransferError(f"ZIP contains a link/special entry: {relative}")
            if info.flag_bits & 1:
                raise TransferError("Encrypted ZIP archives are not supported.")
            expanded += info.file_size
            if expanded > limits["bytes"] or info.file_size > max(1, info.compress_size) * limits["ratio"]:
                raise TransferError("ZIP exceeds expanded-size or compression-ratio limit.")
            if not info.is_dir():
                paths.append(relative)
        for key in kinds:
            for parent in Path(key).parents:
                if str(parent) != "." and kinds.get(parent.as_posix(), True) is False:
                    raise TransferError(f"ZIP file/directory collision: {key}")
    return paths


def scan(source: Path, limits: dict[str, int], cancel: threading.Event) -> Package:
    check_cancel(cancel)
    checked_ancestors(source)
    if source.is_file() and source.suffix.casefold() == ".zip":
        files = inspect_zip(source, limits, cancel)
        with zipfile.ZipFile(source) as archive:
            directories = [safe_relative(i.filename) for i in archive.infolist() if i.is_dir()]
            from .fst import MAX_PREFIX, inspect_bytes
            plugins = {}
            kinds = {}
            fst_types = {}
            scripts = {}
            from .scripts import MAX_SCRIPT_BYTES, inspect_script, classify_scripts
            metadata_bytes = 0
            for info in archive.infolist():
                check_cancel(cancel)
                relative = safe_relative(info.filename)
                if not info.is_dir() and relative.suffix.casefold() == ".fst":
                    with archive.open(info) as stream:
                        prefix = stream.read(min(MAX_PREFIX, info.file_size))
                    metadata_bytes += len(prefix)
                    if metadata_bytes > limits["bytes"]:
                        raise TransferError("ZIP metadata scan exceeded expanded byte limit.")
                    metadata = inspect_bytes(prefix, info.file_size)
                    plugins[relative], kinds[relative] = metadata.plugin_name, metadata.plugin_kind
                    fst_types[relative] = metadata.fst_type
                elif not info.is_dir() and relative.suffix.casefold() in (".py", ".pyscript"):
                    with archive.open(info) as stream:
                        prefix = stream.read(min(MAX_SCRIPT_BYTES + 1, info.file_size))
                    metadata_bytes += len(prefix)
                    if metadata_bytes > limits["bytes"]:
                        raise TransferError("ZIP metadata scan exceeded expanded byte limit.")
                    scripts[relative] = inspect_script(prefix)
        kind, notes = classify_scripts(scripts) if scripts else (None, [])
        package = Package(source, files, is_zip=True, directories=directories, file_plugins=plugins, file_plugin_kinds=kinds,
                          has_scripts=bool(scripts), script_kind=kind, script_notes=notes, file_fst_types=fst_types)
        top_levels = {path.parts[0] for path in [*files, *directories]}
        if len(top_levels) == 1 and all(len(path.parts) > 1 for path in files):
            package.zip_root_folder = Path(next(iter(top_levels)))
        check_hardware_layout(package)
        return package
    if source.is_file():
        safe_relative(source.name)
        from .fst import inspect_file
        metadata = inspect_file(source)
        package = Package(source, [Path(source.name)], plugin_name=metadata.plugin_name, plugin_kind=metadata.plugin_kind, fst_type=metadata.fst_type)
        if source.suffix.casefold() in (".py", ".pyscript"):
            inspect_script_files(package)
            if package.script_kind == "hardware":
                package.destination_subfolder = source.stem[7:] or "Controller"
        return package
    if not source.is_dir():
        raise TransferError(f"Source is not a regular file or folder: {source}")
    files, skipped, directories = [], [], []
    def visit(folder: Path) -> None:
        for child in sorted(folder.iterdir()):
            check_cancel(cancel)
            if is_link(child):
                skipped.append(f"{child}: link/reparse point skipped")
            elif child.is_dir():
                directories.append(child.relative_to(source))
                visit(child)
            elif child.is_file():
                relative = child.relative_to(source)
                safe_relative(relative.as_posix())
                files.append(relative)
            else:
                skipped.append(f"{child}: special entry skipped")
    visit(source)
    from .fst import inspect_file
    plugins = {}
    kinds = {}
    fst_types = {}
    for relative in files:
        check_cancel(cancel)
        if relative.suffix.casefold() == ".fst":
            checked_ancestors(source / relative)
            metadata = inspect_file(source / relative)
            plugins[relative], kinds[relative] = metadata.plugin_name, metadata.plugin_kind
            fst_types[relative] = metadata.fst_type
    package = Package(source, files, skipped, directories=directories, file_plugins=plugins, file_plugin_kinds=kinds, file_fst_types=fst_types)
    inspect_script_files(package, cancel)
    return package


def inspect_script_files(package: Package, cancel: threading.Event | None = None) -> None:
    from .scripts import MAX_SCRIPT_BYTES, inspect_script, classify_scripts
    scripts = {}
    for relative in package.planned_files:
        if cancel:
            check_cancel(cancel)
        if relative.suffix.casefold() in (".py", ".pyscript"):
            path = package.source / relative if package.source.is_dir() else package.source
            checked_ancestors(path)
            with path.open("rb") as stream:
                scripts[relative] = inspect_script(stream.read(MAX_SCRIPT_BYTES + 1))
    package.has_scripts = bool(scripts)
    if scripts:
        package.script_kind, package.script_notes = classify_scripts(scripts)
        check_hardware_layout(package)


def check_hardware_layout(package: Package) -> None:
    entries = [p for p in package.planned_files if p.suffix.casefold() == ".py" and p.name.casefold().startswith("device_")]
    root = package.zip_root_folder or Path()
    package.hardware_nested = bool(entries) and any(p.parent != root for p in entries)
    if package.hardware_nested:
        package.script_notes.append("Hardware entry points are inside subfolders. Extract the ZIP if necessary and drop each device_ file's containing folder, so it is installed as one controller folder.")


def extract(package: Package, stage: Path, limits: dict[str, int], cancel: threading.Event,
            progress: Callable[[str], None]) -> None:
    # Revalidate just before extraction, so changed archives cannot bypass inspection.
    paths = inspect_zip(package.source, limits, cancel)
    if paths != package.files:
        raise TransferError("Archive changed after its import plan was shown. Please import again.")
    total = 0
    with zipfile.ZipFile(package.source) as archive:
        for info in archive.infolist():
            check_cancel(cancel)
            relative = safe_relative(info.filename)
            if info.is_dir():
                (stage / relative).mkdir(parents=True, exist_ok=True)
                continue
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            progress(f"Extracting {relative}")
            with archive.open(info) as incoming, target.open("xb") as outgoing:
                written = 0
                while chunk := incoming.read(1024 * 1024):
                    check_cancel(cancel)
                    total += len(chunk)
                    written += len(chunk)
                    if total > limits["bytes"] or written > info.file_size:
                        raise TransferError("ZIP exceeded expanded byte limit while extracting.")
                    outgoing.write(chunk)


@dataclass
class Job:
    package: Package
    root: Path
    target: Path
    keep_zip: bool = False


@dataclass
class Result:
    copied: int = 0
    skipped: int = 0
    cancelled: int = 0
    failed: int = 0
    details: list[str] = field(default_factory=list)


def collision(path: Path) -> Path | None:
    if not path.parent.exists():
        return None
    return next((p for p in path.parent.iterdir() if p.name.casefold() == path.name.casefold()), None)


def fingerprint(path: Path) -> tuple:
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns


def copy_file(source: Path, target: Path, root: Path, cancel: threading.Event,
              conflict: Callable[[Path], str], progress: Callable[[str], None]) -> str:
    checked_ancestors(source)
    if not source.is_file():
        raise TransferError(f"Source is no longer a regular file: {source}")
    validate_target(root, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    validate_target(root, target)
    if target.exists() and os.path.samefile(source, target):
        raise TransferError(f"Same-file copy refused: {source}")
    fd, temporary = tempfile.mkstemp(prefix=".fldropper-", suffix=".tmp", dir=target.parent)
    staged = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as outgoing, source.open("rb") as incoming:
            while chunk := incoming.read(1024 * 1024):
                check_cancel(cancel)
                outgoing.write(chunk)
                progress(f"Copying {source.name}")
            outgoing.flush()
            os.fsync(outgoing.fileno())
        shutil.copystat(source, staged, follow_symlinks=False)
        while True:
            check_cancel(cancel)
            validate_target(root, target)
            existing = collision(target)
            expected = None
            if existing is not None:
                if os.path.samefile(source, existing):
                    raise TransferError(f"Same-file copy refused: {source}")
                if is_link(existing) or not existing.is_file():
                    raise TransferError(f"Destination is a link or directory: {existing}")
                expected = fingerprint(existing)
                action = conflict(existing)
                check_cancel(cancel)
                if action == "cancel":
                    cancel.set()
                    raise Cancelled()
                if action == "skip":
                    return "skipped"
                if action == "keep":
                    index = 2
                    original = target
                    while collision(target) is not None:
                        target = original.with_name(f"{original.stem} ({index}){original.suffix}")
                        index += 1
                    continue
                if action != "replace":
                    raise TransferError(f"Unknown conflict action: {action}")
                validate_target(root, existing)
                if not existing.exists() or fingerprint(existing) != expected:
                    continue  # A new conflict requires another decision.
                os.replace(staged, existing)
                return "copied"
            try:
                # Atomic, no-clobber commit on the destination filesystem.
                os.link(staged, target)
                staged.unlink()
                return "copied"
            except FileExistsError:
                continue
            except OSError:
                if os.name == "nt":
                    try:
                        os.rename(staged, target)  # Windows rename does not replace.
                        return "copied"
                    except FileExistsError:
                        continue
                raise
    finally:
        staged.unlink(missing_ok=True)


def run_jobs(jobs: list[Job], limits: dict[str, int], cancel: threading.Event,
             conflict: Callable[[Path], str], progress: Callable[[str], None]) -> Result:
    with ExitStack() as staging:
        return _run_jobs(jobs, limits, cancel, conflict, progress, staging)


def _run_jobs(jobs: list[Job], limits: dict[str, int], cancel: threading.Event,
              conflict: Callable[[Path], str], progress: Callable[[str], None], staging: ExitStack) -> Result:
    result = Result()
    total_files = sum(1 if j.keep_zip else len(j.package.planned_files) for j in jobs)
    processed = 0
    zip_stages: dict[Path, Path] = {}
    reported_skips = set()
    for job in jobs:
        p = job.package
        if p.source not in reported_skips:
            result.skipped += len(p.skipped)
            result.details.extend(p.skipped)
            reported_skips.add(p.source)
        paths = [Path(p.source.name)] if job.keep_zip else p.planned_files
        try:
            check_cancel(cancel)
            validate_target(job.root, job.target)
            for other in jobs:
                if other.package.source.is_dir() and job.target.resolve().is_relative_to(other.package.source.resolve()):
                    raise TransferError(f"Destination is inside source tree: {job.target}")
            if p.is_fst_group and job.keep_zip:
                raise TransferError("A routed FST group cannot keep the entire ZIP as a file.")
            if not job.keep_zip and not set(paths).issubset(p.files):
                raise TransferError("Selected files are not part of the validated package.")
            source_root = p.source
            if p.is_zip and not job.keep_zip:
                if p.source not in zip_stages:
                    directory = staging.enter_context(tempfile.TemporaryDirectory(prefix="fldropper-"))
                    stage = Path(directory)
                    extract(p, stage, limits, cancel, progress)
                    zip_stages[p.source] = stage
                source_root = zip_stages[p.source]
            if p.source.is_dir() or (p.is_zip and not job.keep_zip):
                needed = {parent for relative in paths for parent in relative.parents}
                populated = {parent for relative in p.files for parent in relative.parents}
                directories = p.directories if p.selected_files is None else [
                    directory for directory in p.directories if directory in needed or directory not in populated]
                for relative in [Path(), *directories]:
                    check_cancel(cancel)
                    directory = job.target / relative
                    validate_target(job.root, directory)
                    directory.mkdir(parents=True, exist_ok=True)
            for relative in paths:
                check_cancel(cancel)
                source = source_root / relative if p.source.is_dir() or (p.is_zip and not job.keep_zip) else p.source
                target = job.target / relative
                try:
                    state = copy_file(source, target, job.root, cancel, conflict, progress)
                    setattr(result, state, getattr(result, state) + 1)
                    result.details.append(f"{state.capitalize()}: {source} → {target}")
                except Cancelled:
                    raise
                except (OSError, ValueError) as exc:
                    result.failed += 1
                    result.details.append(f"Failed: {source} → {target}: {exc}")
                processed += 1
                progress(f"{processed}/{total_files} files processed")
        except Cancelled:
            result.cancelled = total_files - processed
            result.details.append("Cancelled remaining files; committed copies were preserved.")
            break
        except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
            remaining = max(1, len(paths))
            result.failed += remaining
            processed += remaining
            result.details.append(f"Failed package {p.source}: {exc}")
    return result
