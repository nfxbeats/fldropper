from __future__ import annotations

import copy
import gc
import sys
import threading
import uuid
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLayout, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QTableWidget,
    QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from .config import Config, ConfigError, Destination, default_config, default_config_path, load, parse, resolve, save
from .branding import APP_IMAGE, WINDOW_ICON, WindowsIcons, set_windows_app_id
from .discovery import Candidate, PluginFolderSearch, find_plugin_folders, installation_suggestions, registry_candidates, user_suggestions, validate_root
from .routing import compatible, fst_package_groups, matches_plugin, package_matches, package_choices, group_loose_scripts, needs_plugin_name
from .transfers import Cancelled, Job, Package, Result, run_jobs, safe_relative, scan, validate_target, is_link


STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 10pt; }
QPushButton, QComboBox, QLineEdit { padding: 7px; border: 1px solid #626262; border-radius: 5px; }
QPushButton:hover { background: #484848; }
QPushButton:focus, QComboBox:focus, QLineEdit:focus { border: 2px solid #ffc15a; }
QPushButton#drop { background: #2b2b2b; border: 2px dashed #ffc15a; font-size: 20pt; min-height: 160px; }
QPushButton#drop:hover { background: #404040; }
QLabel#title { font-size: 23pt; font-weight: 600; }
QLabel#lastDrop { color: #ffc15a; font-size: 16pt; font-weight: 600; padding: 6px 0; }
QPushButton#detectFolders { background: #ffc15a; color: #242424; font-weight: 600; }
QPushButton#detectFolders:hover { background: #ffd083; }
QPushButton#detectFolders:pressed { background: #e5a53c; }
QPushButton#detectFolders:disabled { background: #786344; color: #d1c5b1; }
QLabel#muted { color: #c2c2c2; }
QProgressBar { min-height: 20px; border: 1px solid #626262; }
QProgressBar::chunk { background: #ffc15a; }
"""


def open_path(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def folder_icon(add: bool = False) -> QIcon:
    plus = '<path d="M14 11v7m-3.5-3.5h7" stroke="#ffc15a"/>' if add else ""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
           '<g fill="none" stroke="#c2c2c2" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7h18"/>'
           + plus + '</g></svg>')
    pixmap = QPixmap()
    pixmap.loadFromData(svg.encode("utf-8"), "SVG")
    return QIcon(pixmap)


class Worker(QThread):
    done = Signal(object)
    progress = Signal(str)
    question = Signal(object)

    def __init__(self, task: Callable, parent=None):
        super().__init__(parent)
        self.task = task
        self.cancel = threading.Event()
        self.answer_ready = threading.Event()
        self.answer = "skip"
        self.remaining_action = None

    def ask_conflict(self, path: Path) -> str:
        if self.remaining_action:
            return self.remaining_action
        self.answer_ready.clear()
        self.question.emit(path)
        while not self.answer_ready.wait(0.1):
            if self.cancel.is_set():
                return "cancel"
        return self.answer

    def run(self):
        try:
            self.done.emit(self.task(self))
        except Cancelled:
            self.done.emit(Cancelled())
        except Exception as exc:
            self.done.emit(exc)


class DropButton(QPushButton):
    paths = Signal(list)

    def __init__(self):
        super().__init__("Drop files here\n\nor click to choose files")
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.clicked.connect(self.choose)

    def choose(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose content to copy")
        if files:
            self.paths.emit([Path(p) for p in files])

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and all(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.paths.emit([Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()])
        event.acceptProposedAction()


class DestinationEditor(QDialog):
    def __init__(self, config: Config, dest: Destination, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit destination")
        self.config, self.dest = config, copy.deepcopy(dest)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.name = QLineEdit(dest.name)
        self.extensions = QLineEdit(", ".join(dest.extensions))
        self.root = QComboBox()
        for label, value in [("User Data Folder", "user_data"), ("Shared User Data Folder", "shared_data"), ("FL Studio Install Folder", "fl_install"), ("Absolute folder", "absolute")]:
            self.root.addItem(label, value)
        self.root.setCurrentIndex(self.root.findData(dest.root))
        self.path = QLineEdit(dest.path)
        self.enabled = QCheckBox("Enabled")
        self.enabled.setChecked(dest.enabled)
        self.automatic = QCheckBox("Participates in Auto Detect")
        self.automatic.setChecked(dest.automatic)
        self.resolved = QLabel()
        self.resolved.setWordWrap(True)
        for label, widget in [("Name", self.name), ("Extensions (comma separated)", self.extensions),
                              ("Base root", self.root), ("Relative path / absolute folder", self.path),
                              ("", self.enabled), ("", self.automatic)]:
            form.addRow(label, widget)
        note = QLabel("Empty extensions = manual-only, accept any file.\nRelative paths remain beneath the selected base root.")
        layout.addWidget(note)
        row = QHBoxLayout()
        browse = QPushButton("Browse absolute folder…")
        browse.clicked.connect(self.browse)
        opening = QPushButton("Open resolved folder")
        opening.clicked.connect(self.open_resolved)
        row.addWidget(browse)
        row.addWidget(opening)
        layout.addLayout(row)
        layout.addWidget(self.resolved)
        self.root.currentIndexChanged.connect(self.preview)
        self.path.textChanged.connect(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.preview()
        self.resize(570, 400)

    def current(self) -> Destination:
        d = copy.deepcopy(self.dest)
        d.name = self.name.text().strip()
        d.extensions = [e.strip() for e in self.extensions.text().split(",") if e.strip()]
        d.root, d.path = self.root.currentData(), self.path.text().strip()
        d.enabled, d.automatic = self.enabled.isChecked(), self.automatic.isChecked()
        return d

    def preview(self):
        try:
            self.resolved.setText(str(resolve(self.config, self.current())[1]))
        except ValueError as exc:
            self.resolved.setText(str(exc))

    def open_resolved(self):
        try:
            open_path(resolve(self.config, self.current())[1])
        except ValueError as exc:
            QMessageBox.warning(self, "Destination", str(exc))

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose absolute destination")
        if folder:
            self.root.setCurrentIndex(self.root.findData("absolute"))
            self.path.setText(folder)

    def accept(self):
        try:
            trial = copy.deepcopy(self.config)
            trial.destinations = [self.current()]
            self.dest = parse(trial.to_dict()).destinations[0]
            super().accept()
        except ValueError as exc:
            QMessageBox.warning(self, "Check destination", str(exc))


class Settings(QDialog):
    def __init__(self, config: Config, config_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FL Dropper settings")
        self.config, self.config_path = copy.deepcopy(config), config_path
        if not self.config.roots["shared_data"] and self.config.roots["user_data"]:
            self.config.roots["shared_data"] = str(Path(self.config.roots["user_data"]).parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.roots = {}
        for key, label in [("fl_install", "FL Studio Install Folder"), ("shared_data", "Shared User Data Folder")]:
            row = QHBoxLayout()
            edit = QLineEdit(self.config.roots[key])
            self.roots[key] = edit
            browse = QPushButton("Browse…")
            browse.clicked.connect(lambda _, e=edit: self.browse(e))
            row.addWidget(edit, 1)
            row.addWidget(browse)
            form.addRow(label, row)
        self.roots["user_data"] = QLabel()
        self.roots["user_data"].setTextFormat(Qt.TextFormat.PlainText)
        self.roots["user_data"].setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.roots["user_data"].setWordWrap(True)
        form.addRow("User Data Folder", self.roots["user_data"])
        layout.addLayout(form)
        detect = QPushButton("Auto detect folders")
        detect.setObjectName("detectFolders")
        self.detect_button = detect
        detect.clicked.connect(self.detect)
        layout.addWidget(detect)
        self.detection_status = QLabel("Empty folder fields are populated automatically; existing values are preserved.")
        self.detection_status.setWordWrap(True)
        layout.addWidget(self.detection_status)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Destination", "Extensions", "Resolved folder"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit())
        layout.addWidget(self.table)
        row = QHBoxLayout()
        for label, action in [("Add…", self.add), ("Edit…", self.edit), ("Delete", self.delete),
                              ("Open configuration", self.open_config), ("Reload", self.reload)]:
            button = QPushButton(label)
            button.clicked.connect(action)
            row.addWidget(button)
        layout.addLayout(row)
        self.always_replace = QCheckBox("Always replace duplicate files (without prompting)")
        self.always_replace.setChecked(config.always_replace_duplicates)
        layout.addWidget(self.always_replace)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for key in ("fl_install", "shared_data"):
            self.roots[key].textChanged.connect(self.refresh)
        self.refresh()
        self.resize(880, 640)

    def sync_roots(self):
        self.config.roots.update({key: self.roots[key].text().strip() for key in ("fl_install", "shared_data")})
        shared = self.config.roots["shared_data"]
        self.config.roots["user_data"] = str(Path(shared) / "FL Studio") if shared else ""
        self.roots["user_data"].setText(self.config.roots["user_data"])

    def refresh(self):
        self.sync_roots()
        self.table.setRowCount(len(self.config.destinations))
        for row, d in enumerate(self.config.destinations):
            try:
                path = str(resolve(self.config, d)[1])
            except ValueError:
                path = "Setup required"
            for col, text in enumerate([d.name + (" (disabled)" if not d.enabled else ""),
                                         ", ".join(d.extensions) or "Any file · manual only", path]):
                self.table.setItem(row, col, QTableWidgetItem(text))

    def browse(self, edit):
        folder = QFileDialog.getExistingDirectory(self, "Select root folder", edit.text())
        if folder:
            edit.setText(folder)

    def detect(self):
        if getattr(self, "discovery_worker", None) is not None:
            return
        self.detect_button.setEnabled(False)
        self.detection_status.setText("Detecting folders…")
        self.discovery_worker = Worker(lambda _: self.find_candidates(), self)
        self.discovery_worker.done.connect(lambda value: setattr(self.discovery_worker, "result", value))
        self.discovery_worker.finished.connect(self.discovery_finished)
        self.discovery_worker.start()

    @staticmethod
    def find_candidates():
        registered = registry_candidates()
        data = [("user_data", c.path, c.source) for c in registered] if registered else [
            ("user_data", p, "Conventional Documents suggestion") for p in user_suggestions(include_registry=False)]
        data += [("shared_data", c.shared_root, c.source) for c in registered if c.shared_root is not None]
        if not registered:
            data += [("shared_data", p.parent, "Conventional shared-data parent suggestion")
                     for kind, p, _ in list(data) if kind == "user_data" and p.name.casefold() == "fl studio"]
        return data + [("fl_install", c.path, c.source + " · newest identifiable folder version first")
                       for c in installation_suggestions()]

    def discovery_finished(self):
        candidates = self.discovery_worker.result
        self.discovery_worker.deleteLater()
        self.discovery_worker = None
        self.detect_button.setEnabled(True)
        if isinstance(candidates, Exception):
            self.detection_status.setText("Detection failed. Browse to the folders manually.")
            QMessageBox.warning(self, "Folder detection", str(candidates))
            return
        ambiguous = {}
        labels = {"user_data": "User Data Folder", "shared_data": "Shared User Data Folder", "fl_install": "FL Studio Install Folder"}
        filled, missing = [], []
        for kind, edit in self.roots.items():
            if kind == "user_data":
                continue
            if edit.text().strip():
                continue
            options = {}
            for candidate_kind, path, source in candidates:
                if candidate_kind == kind:
                    options.setdefault(str(path).casefold(), (path, source))
            options = list(options.values())
            if len(options) == 1:
                edit.setText(str(options[0][0]))
                edit.setToolTip(options[0][1])
                filled.append(labels[kind])
            elif options:
                ambiguous[kind] = options
            else:
                missing.append(labels[kind])
        if ambiguous:
            self.choose_detected_folders(ambiguous, labels, filled)
        text = "Populated " + ", ".join(filled) + ". Click Save to apply." if filled else "Existing folder values preserved."
        if missing:
            text += " No valid candidate for " + ", ".join(missing) + "; browse manually."
        if any(not self.roots[kind].text().strip() for kind in ambiguous):
            text += " Multiple candidates found; choose a folder or browse manually."
        self.detection_status.setText(text)

    def choose_detected_folders(self, ambiguous, labels, filled):
        dialog = QDialog(self)
        dialog.setWindowTitle("Choose detected folders")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Multiple valid folders were found. Choose which to use.\nInstall versions are ordered newest identifiable version first."))
        choices = {}
        for kind, options in ambiguous.items():
            layout.addWidget(QLabel(labels[kind]))
            combo = QComboBox()
            combo.addItem("Choose a folder…", None)
            for path, source in options:
                combo.addItem(str(path), (path, source))
                combo.setItemData(combo.count() - 1, source, Qt.ItemDataRole.ToolTipRole)
            choices[kind] = combo
            layout.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            for kind, combo in choices.items():
                if combo.currentData() and not self.roots[kind].text().strip():
                    path, source = combo.currentData()
                    self.roots[kind].setText(str(path))
                    self.roots[kind].setToolTip(source)
                    filled.append(labels[kind])

    def done(self, result):
        # Keep the owning dialog alive while a read-only discovery worker finishes.
        if getattr(self, "discovery_worker", None) is not None:
            QMessageBox.information(self, "Detection in progress", "Wait for folder detection to finish before closing Settings.")
            return
        super().done(result)

    def add(self):
        editor = DestinationEditor(self.config, Destination(str(uuid.uuid4()), "Custom destination", [], root="user_data", automatic=False), self)
        if editor.exec():
            self.config.destinations.append(editor.dest)
            self.refresh()

    def edit(self):
        row = self.table.currentRow()
        if row >= 0:
            editor = DestinationEditor(self.config, self.config.destinations[row], self)
            if editor.exec():
                self.config.destinations[row] = editor.dest
                self.refresh()

    def delete(self):
        row = self.table.currentRow()
        if row >= 0:
            self.config.destinations.pop(row)
            self.refresh()

    def open_config(self):
        if self.config_path.exists():
            open_path(self.config_path)
        else:
            QMessageBox.information(self, "Configuration", "Save settings first to create the configuration file.")

    def reload(self):
        try:
            self.config = load(self.config_path)
            for key, edit in self.roots.items():
                if key != "user_data":
                    edit.blockSignals(True)
                    edit.setText(self.config.roots[key])
                    edit.blockSignals(False)
            self.always_replace.setChecked(self.config.always_replace_duplicates)
            self.refresh()
        except ConfigError as exc:
            QMessageBox.warning(self, "Configuration preserved", str(exc))

    def accept(self):
        try:
            self.sync_roots()
            self.config.always_replace_duplicates = self.always_replace.isChecked()
            self.config = parse(self.config.to_dict())
            for key, value in self.config.roots.items():
                if value:
                    validate_root(Path(value), key)
            for d in self.config.destinations:
                if d.enabled and (d.path if d.root == "absolute" else self.config.roots[d.root]):
                    root, target = resolve(self.config, d)
                    validate_target(root, target)
            # If the on-disk config is malformed, require fixing/reloading it first.
            if self.config_path.exists():
                load(self.config_path)
            save(self.config, self.config_path)
            super().accept()
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Settings were not saved", str(exc))


class ScoreFolderDialog(QDialog):
    def __init__(self, root: Path, scores: Path, folders: list[Path], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose score folder")
        self.root, self.scores, self.selected_path = root, scores, None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a folder for this batch of scores and MIDI files."))
        self.folders = QComboBox()
        self.folders.addItem("Scores (root folder)", scores)
        for folder in folders:
            self.folders.addItem(str(folder.relative_to(scores)), folder)
        layout.addWidget(self.folders)
        self.new_folder = QLineEdit()
        self.new_folder.setPlaceholderText("New subfolder inside the selected folder (optional)")
        layout.addWidget(self.new_folder)
        self.preview_path = QLabel()
        self.preview_path.setTextFormat(Qt.TextFormat.PlainText)
        self.preview_path.setWordWrap(True)
        layout.addWidget(self.preview_path)
        self.folders.currentIndexChanged.connect(self.preview)
        self.new_folder.textChanged.connect(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use folder")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.preview()
        self.resize(560, 180)

    def target(self):
        path = self.folders.currentData()
        if self.new_folder.text().strip():
            path /= safe_relative(self.new_folder.text().strip())
        if not path.is_relative_to(self.scores):
            raise ValueError("Score folder must remain beneath Scores.")
        validate_target(self.root, path)
        return path

    def preview(self):
        try:
            self.preview_path.setText(str(self.target()))
        except ValueError as exc:
            self.preview_path.setText(str(exc))

    def accept(self):
        try:
            path = self.target()
            path.mkdir(parents=True, exist_ok=True)
            validate_target(self.root, path)
            self.selected_path = path
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Cannot use score folder", str(exc))
            return
        super().accept()


class PresetNameDialog(QDialog):
    def __init__(self, config, package, selected="auto", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Identify preset plugin")
        self.package = package
        self.wrapper = bool(package.plugin_name and package.plugin_name.casefold() in ("fruity wrapper", "fruit wrapper"))
        layout = QVBoxLayout(self)
        label = QLabel(f"Plugin name needed for {package.source.name}")
        label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(label)
        self.names = QComboBox()
        self.names.setEditable(True)
        self.names.addItem("")
        known = {name for name in config.extra.get("preset_name_history", []) if isinstance(name, str)}
        for d in config.destinations:
            if d.extra.get("plugin_name"):
                known.add(d.extra["plugin_name"])
            elif d.id.startswith("preset-"):
                known.add(d.name.replace(" (Effect)", "").replace(" (Generator)", ""))
        self.names.addItems(sorted(name for name in known if isinstance(name, str) and name.strip() and name.casefold() not in ("fruity wrapper", "fruit wrapper")))
        self.names.setEditText(package.hosted_plugin_name or "")
        layout.addWidget(self.names)
        if package.display_name:
            channel = QLabel(f"Channel name: {package.display_name}")
            channel.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(channel)
        self.category = QComboBox()
        self.category.addItem("Generator", "generator")
        self.category.addItem("Effect", "effect")
        self.category.setCurrentIndex(1 if package.plugin_kind == "effect" or selected == "effect" else 0)
        layout.addWidget(self.category)
        if self.wrapper:
            layout.addWidget(QLabel("Folder name: Fruity Wrapper - <plugin name>"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.plugin_name = None
        self.resize(500, 180)

    def accept(self):
        try:
            self.plugin_name = formatted_plugin_name(self.names.currentText(), self.wrapper)
        except ValueError as exc:
            QMessageBox.warning(self, "Plugin name required", str(exc))
            return
        super().accept()


def formatted_plugin_name(name: str, wrapper: bool) -> str:
    name = name.strip()
    if wrapper:
        for prefix in ("Fruity Wrapper - ", "Fruit Wrapper - "):
            if name.casefold().startswith(prefix.casefold()):
                name = name[len(prefix):].strip()
                break
    if not name or name.casefold() in ("fruity wrapper", "fruit wrapper") or len(safe_relative(name).parts) != 1:
        raise ValueError("Enter a plugin name without folder separators.")
    return "Fruity Wrapper - " + name if wrapper else name


class PluginLocationDialog(QDialog):
    def __init__(self, config: Config, plugin_name: str, candidates: list[Candidate], parent=None, *, plugin_kind: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Add location for {plugin_name}")
        self.path = None
        self.base = None
        layout = QVBoxLayout(self)
        note = QLabel(f"New plugin detected: {plugin_name}\nUser Data is preferred so presets remain available after FL Studio upgrades. Choose an installation folder only if needed.")
        note.setTextFormat(Qt.TextFormat.PlainText)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.choices = QComboBox()
        self.choices.setMinimumContentsLength(35)
        self.choices.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        user_root = Path(config.roots["user_data"]) if config.roots.get("user_data") else None
        user_candidates = [c for c in candidates if user_root and c.path.is_relative_to(user_root)]
        others = [c for c in candidates if c not in user_candidates]
        seen = set()

        def add_choice(label, base, path):
            if str(path).casefold() in seen:
                return
            seen.add(str(path).casefold())
            self.choices.addItem(f"{label}: {path}", (base, path))
            self.choices.setItemData(self.choices.count() - 1, str(path), Qt.ItemDataRole.ToolTipRole)

        for candidate in user_candidates:
            add_choice("User Data (preferred)", user_root, candidate.path)
        try:
            relative = safe_relative(plugin_name)
            if len(relative.parts) == 1 and config.roots.get("user_data"):
                base = Path(config.roots["user_data"])
                if base.is_dir():
                    categories = ("Effects", "Generators") if plugin_kind == "effect" else ("Generators", "Effects")
                    for category in categories:
                        path = base / "Presets/Plugin presets" / category / relative
                        add_choice(f"User Data {category.lower()} (preferred)", base, path)
        except ValueError:
            pass
        preferred_count = self.choices.count()
        for candidate in others:
            base = next((Path(config.roots[k]) for k in ("shared_data", "fl_install")
                         if config.roots.get(k) and candidate.path.is_relative_to(Path(config.roots[k]))), candidate.path)
            add_choice(candidate.source, base, candidate.path)
        self.choices.addItem("Other… browse for a folder", None)
        if not preferred_count:
            self.choices.setCurrentIndex(self.choices.count() - 1)
        layout.addWidget(self.choices)
        self.path_status = QLabel()
        self.path_status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.path_status)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Browse to a base folder, then append a new subfolder if needed")
        layout.addWidget(self.path_edit)
        browse = QPushButton("Other… browse")
        browse.clicked.connect(self.browse)
        layout.addWidget(browse)
        self.choices.currentIndexChanged.connect(self.preview)
        self.path_edit.textChanged.connect(self.update_path_status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Add location and copy")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Skip this plugin")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.preview()
        self.resize(760, 280)

    def preview(self):
        choice = self.choices.currentData()
        self.base = choice[0] if choice else None
        self.path_edit.setText(str(choice[1]) if choice else "")
        self.update_path_status()

    def update_path_status(self):
        raw = self.path_edit.text().strip()
        self.path_edit.setToolTip(raw)
        found = bool(raw) and Path(raw).is_dir()
        self.path_status.setText("Path found. Use…" if found else "Path not found. Use…")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Add location and copy" if found else "Create folder, add location and copy")

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose plugin preset folder or parent for a new folder", self.path_edit.text())
        if folder:
            self.choices.setCurrentIndex(self.choices.count() - 1)
            self.base = Path(folder)
            self.path_edit.setText(folder)

    def accept(self):
        if self.base is None:
            self.browse()
            if self.base is None:
                return
        try:
            path = Path(self.path_edit.text().strip())
            if path != self.base:
                safe_relative(path.relative_to(self.base).as_posix())
            validate_target(self.base, path)
            # Creation is explicitly approved by this dialog, beneath the chosen
            # existing root. Recheck ancestors before the normal copy pipeline.
            path.mkdir(parents=True, exist_ok=True)
            validate_target(self.base, path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Cannot use this folder", str(exc))
            return
        self.path = path
        super().accept()


class RoutingDialog(QDialog):
    def __init__(self, config: Config, packages: list[Package], selected: str, parent=None):
        super().__init__(parent)
        self.config, self.packages, self.selected = config, packages, selected
        self.setWindowTitle("Review import destinations")
        layout = QVBoxLayout(self)
        note = QLabel("Choose a destination for each item. FST package groups route by plugin; companions are copied with each group.\n"
                      "Package names and internal paths are preserved. Unidentified items require a choice or can be skipped.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(len(packages), 3)
        self.table.setHorizontalHeaderLabels(["Source", "Destination", "ZIP handling"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.choices, self.modes = [], []
        explicit = next((d for d in config.destinations if d.id == selected), None)
        for row, p in enumerate(packages):
            is_package = p.is_zip or p.source.is_dir()
            group = f" — {p.group_name}" if p.group_name else ""
            source_item = QTableWidgetItem(f"{p.source.name}{group} ({len(p.planned_files)} files)")
            source_item.setToolTip(str(p.source) + (f"\nPlugin: {p.plugin_name}" if p.plugin_name else "") +
                                   "\n" + "\n".join(str(f) for f in p.planned_files[:30]))
            self.table.setItem(row, 0, source_item)
            choice, mode = QComboBox(), QComboBox()
            mode.addItem("Extract package", False)
            mode.addItem("Keep ZIP as file", True)
            mode.setEnabled(p.is_zip and p.selected_files is None)
            self.choices.append(choice)
            self.modes.append(mode)
            self.table.setCellWidget(row, 1, choice)
            self.table.setCellWidget(row, 2, mode)
            def populate(_, r=row, pkg=p, combo=choice, zip_mode=mode):
                prior = combo.currentData()
                combo.clear()
                combo.addItem("Skip", None)
                keep = pkg.is_zip and zip_mode.currentData()
                for d in config.destinations:
                    if not d.enabled or (explicit and d.id != explicit.id):
                        continue
                    if pkg.hardware_nested and (d.id == "hardware" or d.extra.get("script_type") == "hardware"):
                        continue
                    if pkg.has_scripts and pkg.script_kind and d.id in ("piano", "edison", "hardware") and d.id != pkg.script_kind:
                        continue
                    if keep:
                        ok = d.accepts(pkg.source) and (not d.extensions or (".flp" in d.extensions and any(f.suffix.casefold() == ".flp" for f in pkg.files)))
                    elif pkg.is_zip or pkg.source.is_dir():
                        ok, _bad = package_matches(config, pkg.planned_files, d)
                    else:
                        ok = d.accepts(pkg.source)
                    if ok:
                        try:
                            _, target = resolve(config, d)
                            if (pkg.is_zip or pkg.source.is_dir()) and not keep:
                                target = pkg.displayed_target(target)
                            elif pkg.destination_subfolder:
                                target /= pkg.destination_subfolder
                            combo.addItem(f"{d.name} → {target}", d.id)
                            combo.setItemData(combo.count() - 1, str(target), Qt.ItemDataRole.ToolTipRole)
                        except ValueError:
                            pass
                suggested = package_choices(config, pkg) if pkg.plugin_name or pkg.has_scripts or any(f.suffix.casefold() in (".fsc", ".mid", ".midi") for f in pkg.planned_files) else []
                preferred = prior or (explicit.id if explicit else suggested[0].id if len(suggested) == 1 else None)
                index = combo.findData(preferred) if preferred else -1
                if index > 0:
                    combo.setCurrentIndex(index)
                elif combo.count() == 2 and not (pkg.has_scripts and not pkg.script_kind and not explicit) and not (
                        not explicit and not pkg.plugin_name and any(f.suffix.casefold() in (".fxp", ".h2p") for f in pkg.planned_files)):
                    combo.setCurrentIndex(1)
            mode.currentIndexChanged.connect(populate)
            populate(0)
        layout.addWidget(self.table)
        self.summary = QLabel()
        if explicit:
            problems = []
            for p in packages:
                if p.is_zip or p.source.is_dir():
                    ok, bad = package_matches(config, p.planned_files, explicit)
                    if not ok:
                        problems.append(f"{p.source.name}: incompatible or unrecognized primary content" +
                                        (" (" + ", ".join(bad[:3]) + ")" if bad else ""))
                elif not explicit.accepts(p.source):
                    suggestions = compatible(config, p.source)
                    problems.append(f"{p.source.name}: incompatible with {explicit.name}. Compatible: " +
                                    (", ".join(d.name for d in suggestions) or "manual accept-any destination"))
            self.summary.setText("\n".join(problems))
        script_notes = [f"{p.source.name}: {note}" for p in packages for note in p.script_notes]
        if script_notes:
            self.summary.setText("\n".join(filter(None, [self.summary.text(), *script_notes[:6]])))
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Copy selected")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(1000, 370)
        self.jobs = []

    def accept(self):
        jobs = []
        try:
            for p, choice, mode in zip(self.packages, self.choices, self.modes):
                if not choice.currentData():
                    continue
                d = next(d for d in self.config.destinations if d.id == choice.currentData())
                root, target = resolve(self.config, d)
                validate_root(root, d.root)
                keep = p.is_zip and mode.currentData()
                if p.source.is_dir() or (p.is_zip and not keep):
                    target = p.extraction_target(target)
                elif p.destination_subfolder:
                    target /= p.destination_subfolder
                validate_target(root, target)
                jobs.append(Job(p, root, target, bool(keep)))
            self.jobs = jobs
            super().accept()
        except ValueError as exc:
            QMessageBox.warning(self, "Destination needs setup", str(exc))


class MainWindow(QMainWindow):
    def __init__(self, config_path: Path | None = None):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("FL Dropper - Produced by NFX @ Warbeats")
        self.setWindowIcon(QIcon(str(WINDOW_ICON)))
        self.native_icons = WindowsIcons()
        self.destroyed.connect(self.native_icons.release)
        self.config_path = config_path if config_path is not None else default_config_path()
        self.config_error = ""
        try:
            self.config = load(self.config_path)
        except ConfigError as exc:
            self.config, self.config_error = default_config(), str(exc)
        self.worker = None
        self.last_target = None
        self.pending_skipped = 0
        widget = QWidget()
        self.setCentralWidget(widget)
        self.main_layout = QVBoxLayout(widget)
        # Geometry is controlled explicitly below. Dynamic text, progress states,
        # and hidden details must not make Qt resize the window automatically.
        self.main_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.main_layout.setContentsMargins(24, 22, 24, 22)
        self.main_layout.setSpacing(12)
        self.controls = QWidget()
        self.controls.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self.controls)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        row = QHBoxLayout()
        self.app_logo = QLabel()
        self.app_logo.setFixedSize(44, 44)
        self.app_logo.setAccessibleName("FL Dropper logo")
        scale = self.devicePixelRatioF()
        logo = QPixmap(str(APP_IMAGE)).scaled(round(44 * scale), round(44 * scale),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        logo.setDevicePixelRatio(scale)
        self.app_logo.setPixmap(logo)
        row.addWidget(self.app_logo)
        title = QLabel("FL Dropper")
        title.setObjectName("title")
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.settings)
        row.addWidget(title, 1)
        row.addWidget(self.settings_button)
        layout.addLayout(row)
        self.destinations = QComboBox()
        self.destinations.currentIndexChanged.connect(self.selection_changed)
        layout.addWidget(self.destinations)
        self.last_drop_label = QLabel("No file dropped yet")
        self.last_drop_label.setObjectName("lastDrop")
        self.last_drop_label.setTextFormat(Qt.TextFormat.PlainText)
        self.last_drop_label.setWordWrap(False)
        self.last_drop_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.last_drop_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        file_row = QHBoxLayout()
        file_row.addWidget(self.last_drop_label, 1)
        self.folder_button = QPushButton()
        self.folder_button.setIcon(folder_icon(add=True))
        self.folder_button.setToolTip("Choose folder and add a plugin location")
        self.folder_button.setAccessibleName("Add plugin folder")
        self.folder_button.clicked.connect(self.choose_folder)
        self.open_button = QPushButton()
        self.open_button.setIcon(folder_icon())
        self.open_button.setToolTip("Open destination")
        self.open_button.setAccessibleName("Open destination")
        self.open_button.clicked.connect(self.open_destination)
        for button in (self.folder_button, self.open_button):
            button.setIconSize(QSize(24, 24))
            button.setFixedSize(38, 38)
            file_row.addWidget(button)
        layout.addLayout(file_row)
        self.last_dropped_path = None
        self.drop = DropButton()
        self.drop.paths.connect(self.import_paths)
        layout.addWidget(self.drop)
        self.cancel_button = QPushButton("Cancel", widget)
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setEnabled(False)
        self.cancel_button.hide()
        self.progress = QProgressBar()
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        feedback = QVBoxLayout()
        feedback.setSpacing(0)
        feedback.setContentsMargins(0, 0, 0, 0)
        feedback.addWidget(self.progress)
        self.status = QLabel(self.config_error or "Ready. Choose Settings to configure your folders.")
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.addWidget(self.status, 1)
        self.details_button = QToolButton()
        self.details_button.setAutoRaise(True)
        self.details_button.setFixedSize(24, 24)
        self.details_button.setCheckable(True)
        self.details_button.setArrowType(Qt.ArrowType.DownArrow)
        self.details_button.setToolTip("Show details")
        self.details_button.setAccessibleName("Show details")
        status_row.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignRight)
        feedback.addLayout(status_row)
        layout.addLayout(feedback)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.details.setVisible(False)
        self.details_button.toggled.connect(self.toggle_details)
        self.main_layout.addWidget(self.controls)
        self.main_layout.addWidget(self.details, 1)
        self._adjusting_details = True
        self._resizing_window = False
        self.refresh()
        self.setFixedWidth(690)
        self.ensurePolished()
        self.main_layout.activate()
        self.controls.setFixedHeight(max(self.controls.sizeHint().height(), self.controls.minimumSizeHint().height()))
        self.setMinimumHeight(self.compact_height())
        self.resize(self.width(), self.compact_height())
        self._adjusting_details = False

    def compact_height(self) -> int:
        margins = self.main_layout.contentsMargins()
        if self.controls.minimumHeight() == self.controls.maximumHeight():
            return self.controls.height() + margins.top() + margins.bottom()
        controls_layout = self.controls.layout()
        width = self.width() - margins.left() - margins.right()
        height = max(controls_layout.totalMinimumSize().height(), controls_layout.totalHeightForWidth(width))
        return height + margins.top() + margins.bottom()

    def showEvent(self, event):
        super().showEvent(event)
        self.native_icons.apply(int(self.winId()), self.devicePixelRatioF())

    def toggle_details(self, expanded: bool):
        self._adjusting_details = True
        self.details.setVisible(expanded)
        self.details_button.setArrowType(Qt.ArrowType.UpArrow if expanded else Qt.ArrowType.DownArrow)
        label = "Hide details" if expanded else "Show details"
        self.details_button.setToolTip(label)
        self.details_button.setAccessibleName(label)
        compact = self.compact_height()
        self.main_layout.activate()
        self.setMinimumHeight(compact)
        if not self._resizing_window:
            self.resize(self.width(), max(self.height(), compact + 160) if expanded else compact)
        self._adjusting_details = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "_adjusting_details") or self._adjusting_details:
            return
        expanded = self.height() > self.compact_height() + 16
        if expanded != self.details_button.isChecked():
            self._resizing_window = True
            try:
                self.details_button.setChecked(expanded)
            finally:
                self._resizing_window = False

    def refresh(self):
        self.destinations.blockSignals(True)
        self.destinations.clear()
        self.destinations.addItem("Auto Detect", "auto")
        for d in self.config.destinations:
            if d.enabled:
                self.destinations.addItem(d.name + (" · any file, manual only" if not d.extensions else ""), d.id)
        self.destinations.setCurrentIndex(max(0, self.destinations.findData(self.config.last_selection)))
        self.destinations.blockSignals(False)
        self.selection_changed()

    def selection_changed(self):
        selection = self.destinations.currentData()
        self.config.last_selection = selection or "auto"
        self.last_target = None
        try:
            if selection == "auto":
                self.destinations.setToolTip("Detect a destination for each file")
            else:
                d = next(d for d in self.config.destinations if d.id == selection)
                self.last_target = resolve(self.config, d)[1]
                self.destinations.setToolTip(str(self.last_target))
            if not self.config_error:
                if self.config_path.exists():
                    load(self.config_path)
                save(self.config, self.config_path)
        except ConfigError as exc:
            self.config_error = str(exc)
            self.status.setText(self.config_error)
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))
            self.destinations.setToolTip(str(exc))
        self.open_button.setEnabled(self.last_target is not None)

    def settings(self):
        dialog = Settings(self.config, self.config_path, self)
        if dialog.exec():
            self.config, self.config_error = dialog.config, ""
            self.refresh()
            self.status.setText("Settings saved.")

    def detect_missing_roots(self):
        if self.config_error or self.worker or all(self.config.roots.get(k) for k in ("user_data", "shared_data", "fl_install")):
            return
        self.status.setText("Detecting FL Studio folders…")

        def discover(_):
            candidates = []
            for kind, path, source in Settings.find_candidates():
                try:
                    validate_root(path, kind)
                    if kind == "user_data" and not ((path / "Settings").is_dir() and
                            any((path / name).is_dir() for name in ("Presets", "Projects"))):
                        continue
                    candidates.append((kind, path, source))
                except (OSError, ValueError):
                    pass
            return candidates

        self.start_worker(discover, self.missing_roots_detected)

    def missing_roots_detected(self, candidates):
        if isinstance(candidates, Exception):
            self.status.setText("Folder detection failed. Choose folders in Settings.")
            self.details.appendPlainText(str(candidates))
            return
        trial = copy.deepcopy(self.config)
        filled, unresolved = [], []
        labels = {"user_data": "User Data", "shared_data": "Shared User Data", "fl_install": "Install"}
        for kind, label in labels.items():
            if kind == "user_data":
                continue
            if trial.roots.get(kind):
                continue
            options = {str(path).casefold(): path for candidate_kind, path, _ in candidates if candidate_kind == kind}
            if len(options) == 1:
                trial.roots[kind] = str(next(iter(options.values())))
                filled.append(label)
            else:
                unresolved.append(label)
        if trial.roots.get("shared_data"):
            derived = str(Path(trial.roots["shared_data"]) / "FL Studio")
            if trial.roots.get("user_data") != derived:
                trial.roots["user_data"] = derived
                filled.append("User Data")
        if filled:
            try:
                if self.config_path.exists():
                    load(self.config_path)
                save(trial, self.config_path)
            except (ConfigError, OSError) as exc:
                self.status.setText(f"Could not save detected folders: {exc}")
                return
            self.config = trial
            self.refresh()
        message = "Detected " + ", ".join(filled) + "." if filled else "No unique folder matches found."
        if unresolved:
            message += " Choose " + ", ".join(unresolved) + " in Settings."
        self.status.setText(message)

    def choose_folder(self):
        if self.worker:
            return
        if self.config_error:
            QMessageBox.warning(self, "Repair configuration first", self.config_error)
            return
        folder = QFileDialog.getExistingDirectory(self, "Choose plugin destination folder", self.config.roots.get("user_data", ""))
        if not folder:
            return
        name, accepted = QInputDialog.getText(self, "Plugin name", "Plugin name for this location:")
        if not accepted:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Plugin name required", "Enter a plugin name to add this location.")
            return
        try:
            path = Path(folder)
            validate_target(path, path)
            self.add_plugin_location(name, path, select=True)
            self.status.setText(f"Added {name}. Ready to copy presets to this location.")
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Location was not added", str(exc))

    def add_plugin_location(self, name: str, path: Path, *, select: bool = False, plugin_kind: str | None = None):
        from .catalog import PLUGIN_PRESETS, PLUGIN_EXTENSIONS
        validate_target(path, path)
        trial = copy.deepcopy(self.config)
        extensions = next((list(PLUGIN_EXTENSIONS.get(id, (".fst",))) for id, plugin, _, _ in PLUGIN_PRESETS
                           if plugin.casefold() == name.casefold()), [".fst"])
        destination = Destination(str(uuid.uuid4()), name, extensions, path=str(path),
                                  extra={"plugin_name": name})
        if plugin_kind:
            destination.extra["plugin_kind"] = plugin_kind
        for kind in ("user_data", "shared_data", "fl_install"):
            raw = trial.roots.get(kind)
            if raw and path.is_relative_to(Path(raw)):
                destination.root = kind
                destination.path = path.relative_to(Path(raw)).as_posix()
                break
        trial.destinations.append(destination)
        if select:
            trial.last_selection = destination.id
        if self.config_path.exists():
            load(self.config_path)
        save(trial, self.config_path)
        self.config = trial
        self.refresh()

    def open_destination(self):
        if self.last_target:
            open_path(self.last_target)

    def set_busy(self, busy: bool):
        for widget in (self.drop, self.folder_button, self.settings_button, self.destinations):
            widget.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.progress.setRange(0, 0 if busy else 1)
        self.progress.setValue(0 if busy else 1)

    def start_worker(self, task, callback):
        self.set_busy(True)
        worker = Worker(task, self)
        self.worker = worker
        worker.progress.connect(self.status.setText)
        worker.question.connect(self.conflict)
        # Wait for QThread.finished before starting the next worker or deleting it.
        worker.done.connect(lambda value: setattr(worker, "result", value))
        def finished():
            self.worker = None
            self.set_busy(False)
            callback(worker.result)
            worker.deleteLater()
        worker.finished.connect(finished)
        worker.start()

    def import_paths(self, paths: list[Path]):
        if self.worker or not paths:
            return
        if self.config_error:
            QMessageBox.warning(self, "Repair configuration first", self.config_error)
            return
        self.last_dropped_path = paths[-1].absolute()
        label = "Score/MIDI file" if self.last_dropped_path.suffix.casefold() in (".fsc", ".mid", ".midi") else "Detecting plugin…"
        self.last_drop_label.setText(f"{label}: {self.last_dropped_path.name}")
        self.last_drop_label.setToolTip(self.last_drop_label.text())
        self.details.clear()
        self.pending_skipped = 0
        selection = self.destinations.currentData()
        self.status.setText("Inspecting sources…")
        def inspect(worker):
            packages, errors = [], []
            from .fxp import InstalledPluginLookup
            user_data = self.config.roots.get("user_data")
            fxp_lookup = InstalledPluginLookup(Path(user_data) if user_data else None, worker.cancel)
            for path in paths:
                try:
                    package = scan(path.absolute(), self.config.zip_limits, worker.cancel, fxp_lookup)
                    packages.extend(fst_package_groups(package) if selection == "auto" else [package])
                except Cancelled:
                    raise
                except Exception as exc:
                    errors.append(f"Failed to inspect {path}: {exc}")
            packages = group_loose_scripts(packages, worker.cancel)
            scores = next((d for d in self.config.destinations if d.id == "scores" and d.enabled), None)
            if scores and any(f.suffix.casefold() in (".fsc", ".mid", ".midi") for p in packages for f in p.planned_files):
                try:
                    root, base = resolve(self.config, scores)
                    validate_target(root, base)
                    folders = sorted((p for p in base.iterdir() if not is_link(p) and p.is_dir()),
                                     key=lambda p: p.name.casefold()) if base.is_dir() else []
                    for package in packages:
                        package.score_subfolders = folders
                except (ValueError, OSError) as exc:
                    errors.append(f"Cannot inspect score folders: {exc}")
            names = list({p.plugin_name.casefold(): p.plugin_name for p in packages
                          if selection == "auto" and p.plugin_name and not needs_plugin_name(p) and not any(
                              matches_plugin(d, p.plugin_name, p.plugin_kind, p.fst_type) and d.accepts(p.route_path)
                              for d in self.config.destinations)}.values())
            if names:
                worker.progress.emit("Searching for preset folders for new plugins…")
            search = find_plugin_folders(self.config.roots, names, worker.cancel) if names else PluginFolderSearch({}, [])
            return packages, errors, search
        self.start_worker(inspect, lambda result: self.scanned(result, selection))

    def scanned(self, result, selection):
        if not isinstance(result, Exception) and selection in ("auto", "generator", "effect"):
            packages, errors, search = result
            had_generic = any(needs_plugin_name(p) for p in packages)
            packages = self.resolve_preset_identities(packages, selection, errors)
            result = packages, errors, search
            if had_generic and selection in ("generator", "effect"):
                selection = "auto"
        if self.last_dropped_path is not None:
            plugin = None
            if not isinstance(result, Exception):
                from .scripts import SCRIPT_ROUTES
                names = list(dict.fromkeys((p.plugin_label or SCRIPT_ROUTES.get(p.script_kind, "Script type not identified")) for p in result[0]
                             if (p.source == self.last_dropped_path or
                                 (p.source == self.last_dropped_path.parent and Path(self.last_dropped_path.name) in p.planned_files))
                             and (p.plugin_name or p.has_scripts)))
                plugin = ", ".join(names) or None
            label = "Score/MIDI file" if self.last_dropped_path.suffix.casefold() in (".fsc", ".mid", ".midi") else plugin or "Plugin not identified"
            if self.last_dropped_path.suffix.casefold() == ".chenv":
                label = "Channel envelope"
            self.last_drop_label.setText(f"{label}: {self.last_dropped_path.name}")
            self.last_drop_label.setToolTip(self.last_drop_label.text())
        if isinstance(result, Exception):
            self.status.setText("Inspection cancelled." if isinstance(result, Cancelled) else str(result))
            return
        packages, errors, search = result
        self.scan_errors = errors
        self.details.setPlainText("\n".join(errors))
        self.details.appendPlainText("\n".join(search.notes))
        for p in packages:
            if p.has_scripts:
                from .scripts import SCRIPT_ROUTES
                self.details.appendPlainText(f"Script type: {SCRIPT_ROUTES.get(p.script_kind, 'Needs destination choice')}")
                self.details.appendPlainText("\n".join(p.script_notes))
            if p.plugin_name:
                kind = f" ({p.plugin_kind.title()})" if p.plugin_kind else ""
                state = " — Channel state" if p.fst_type == "channel" else ""
                self.details.appendPlainText(f"Identified plugin: {p.source.name} → {p.plugin_name}{kind}{state}")
                if p.display_name:
                    self.details.appendPlainText(f"Channel name: {p.display_name}")
        skipped_plugins = set()
        self.set_busy(True)
        try:
            for name, candidates in search.matches.items():
                kinds = {p.plugin_kind for p in packages if p.plugin_name == name and p.plugin_kind}
                plugin_kind = next(iter(kinds)) if len(kinds) == 1 else None
                user_matches = [c for c in candidates if self.config.roots.get("user_data") and
                                c.path.is_relative_to(Path(self.config.roots["user_data"]))]
                if len(user_matches) == 1:
                    try:
                        self.add_plugin_location(name, user_matches[0].path)
                        self.details.appendPlainText(f"Added user-data plugin location: {name} → {user_matches[0].path}")
                        continue
                    except (ValueError, OSError) as exc:
                        self.details.appendPlainText(f"Could not automatically add {name}: {exc}")
                dialog = PluginLocationDialog(self.config, name, candidates, self, plugin_kind=plugin_kind)
                accepted = dialog.exec()
                chosen_path = dialog.path
                dialog.deleteLater()
                if accepted and chosen_path is not None:
                    try:
                        self.add_plugin_location(name, chosen_path)
                        self.details.appendPlainText(f"Added plugin location: {name} → {chosen_path}")
                        continue
                    except (ValueError, OSError) as exc:
                        QMessageBox.warning(self, "Location was not added", str(exc))
                skipped_plugins.add(name.casefold())
        finally:
            self.set_busy(False)
        if skipped_plugins:
            for p in packages:
                if p.plugin_name and p.plugin_name.casefold() in skipped_plugins:
                    self.pending_skipped += len(p.planned_files)
                    self.details.appendPlainText(f"Skipped plugin location choice: {p.source.name}")
            packages = [p for p in packages if not p.plugin_name or p.plugin_name.casefold() not in skipped_plugins]
        if not packages:
            self.status.setText(errors[0] if errors else f"No imports ready. {self.pending_skipped} skipped.")
            return
        jobs = []
        review = False
        try:
            for p in packages:
                if p.is_zip or p.source.is_dir():
                    review = True
                    break
                choices = package_choices(self.config, p, automatic=selection == "auto")
                if selection != "auto":
                    choices = [d for d in choices if d.id == selection]
                if len(choices) != 1:
                    review = True
                    suggestions = compatible(self.config, p.source)
                    self.details.appendPlainText(f"{p.source.name}: routing choice required. Compatible: " +
                                                 (", ".join(d.name for d in suggestions) or "create an accept-any destination"))
                    continue
                root, target = resolve(self.config, choices[0])
                if p.destination_subfolder:
                    target /= p.destination_subfolder
                validate_root(root, choices[0].root)
                validate_target(root, target)
                jobs.append(Job(p, root, target))
        except ValueError as exc:
            QMessageBox.warning(self, "Setup required", str(exc))
            self.status.setText("Import stopped; configure a valid destination in Settings.")
            return
        if review:
            dialog = RoutingDialog(self.config, packages, selection, self)
            accepted = dialog.exec()
            jobs = dialog.jobs
            dialog.deleteLater()
            if not accepted:
                self.status.setText("Import cancelled before copying.")
                return
            skipped = [p for p in packages if not any(j.package is p for j in jobs)]
            self.pending_skipped += sum(len(p.planned_files) for p in skipped)
            for p in skipped:
                self.details.appendPlainText(f"Skipped by routing choice: {p.source}")
        if not jobs:
            self.status.setText(f"No files selected. {self.pending_skipped} skipped; {len(errors)} failed inspections.")
            return
        if not self.choose_score_subfolder(jobs, selection):
            self.status.setText("Import cancelled before copying.")
            return
        self.last_target = jobs[0].target
        if jobs[0].package.zip_root_folder and not jobs[0].keep_zip:
            self.last_target /= jobs[0].package.zip_root_folder
        self.open_button.setEnabled(True)
        conflict = (lambda _path: "replace") if self.config.always_replace_duplicates else None
        self.start_worker(lambda w: run_jobs(jobs, self.config.zip_limits, w.cancel, conflict or w.ask_conflict, w.progress.emit), self.transferred)

    def choose_score_subfolder(self, jobs, selection="auto"):
        if selection not in ("auto", "scores"):
            return True
        scores = next((d for d in self.config.destinations if d.id == "scores"), None)
        if not scores:
            return True
        try:
            root, base = resolve(self.config, scores)
        except ValueError:
            return True
        score_jobs = [j for j in jobs if not j.keep_zip and j.target.is_relative_to(base) and
                      any(f.suffix.casefold() in (".fsc", ".mid", ".midi") for f in j.package.planned_files)]
        folders = next((j.package.score_subfolders for j in score_jobs if j.package.score_subfolders), [])
        if not folders:
            return True
        dialog = ScoreFolderDialog(root, base, folders, self)
        accepted = dialog.exec()
        selected_path = dialog.selected_path
        dialog.deleteLater()
        if not accepted or selected_path is None:
            return False
        for job in score_jobs:
            job.target = selected_path / job.target.relative_to(base)
        return True

    def resolve_preset_identities(self, packages, selection, errors):
        result = []
        self.set_busy(True)
        try:
            for p in packages:
                if not needs_plugin_name(p):
                    result.append(p)
                    continue
                wrapper = bool(p.plugin_name and p.plugin_name.casefold() in ("fruity wrapper", "fruit wrapper"))
                kind = p.plugin_kind or (selection if selection in ("generator", "effect") else None)
                name = None
                if wrapper and p.hosted_plugin_name and kind:
                    try:
                        name = formatted_plugin_name(p.database_name or p.hosted_plugin_name, True)
                    except ValueError:
                        pass
                if not name:
                    dialog = PresetNameDialog(self.config, p, selection, self)
                    accepted = dialog.exec()
                    name, kind = dialog.plugin_name, dialog.category.currentData()
                    dialog.deleteLater()
                    if not accepted or not name:
                        self.pending_skipped += len(p.planned_files)
                        continue
                try:
                    existing = [d for d in self.config.destinations if matches_plugin(d, name, kind, p.fst_type)]
                    if not existing:
                        destination = next((d for d in self.config.destinations if d.id == kind),
                                           Destination(kind, kind, [".fst"], "user_data",
                                                       "Presets/Plugin presets/" + ("Effects" if kind == "effect" else "Generators")))
                        root, base = resolve(self.config, destination)
                        validate_root(root, destination.root)
                        target = base / safe_relative(name)
                        validate_target(root, target)
                        target.mkdir(parents=True, exist_ok=True)
                        validate_target(root, target)
                        self.add_plugin_location(name, target, plugin_kind=kind)
                    preset_extensions = {f.suffix.casefold() for f in p.planned_files} & {".fxp", ".h2p"}
                    for dest in self.config.destinations:
                        if matches_plugin(dest, name, kind, p.fst_type):
                            dest.extensions.extend(sorted(preset_extensions - set(dest.extensions)))
                    history = self.config.extra.get("preset_name_history", [])
                    history = [n for n in history if isinstance(n, str) and n.casefold() != name.casefold()]
                    self.config.extra["preset_name_history"] = (history + [name])[-256:]
                    if self.config_path.exists():
                        load(self.config_path)
                    save(self.config, self.config_path)
                    p.plugin_name, p.plugin_kind = name, kind
                    if p.is_fst_group:
                        p.group_name = name
                    result.append(p)
                except (ValueError, OSError, StopIteration) as exc:
                    errors.append(f"Cannot set preset location for {p.source.name}: {exc or 'Configure Generator and Effect destinations in Settings.'}")
                    self.pending_skipped += len(p.planned_files)
        finally:
            self.set_busy(False)
        merged, groups = [], {}
        for package in result:
            if not package.is_fst_group or not package.plugin_name:
                merged.append(package)
                continue
            key = (package.source, package.plugin_name, package.plugin_kind, package.fst_type)
            if key in groups:
                first = groups[key]
                first.selected_files = list(dict.fromkeys(first.planned_files + package.planned_files))
            else:
                groups[key] = package
                merged.append(package)
        return merged

    def conflict(self, path):
        worker = self.worker
        if not worker or worker.cancel.is_set():
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("File already exists")
        dialog.setText(f"Choose what to do with:\n{path}")
        apply = QCheckBox("Apply to remaining conflicts in this import")
        dialog.setCheckBox(apply)
        buttons = {}
        for label, action, role in [("Replace", "replace", QMessageBox.ButtonRole.AcceptRole),
                                    ("Skip", "skip", QMessageBox.ButtonRole.RejectRole),
                                    ("Keep both", "keep", QMessageBox.ButtonRole.ActionRole),
                                    ("Cancel remaining", "cancel", QMessageBox.ButtonRole.DestructiveRole)]:
            buttons[dialog.addButton(label, role)] = action
        dialog.setDefaultButton(next(b for b, action in buttons.items() if action == "skip"))
        dialog.exec()
        worker.answer = buttons.get(dialog.clickedButton(), "skip")
        if apply.isChecked():
            worker.remaining_action = worker.answer
        worker.answer_ready.set()

    def transferred(self, result):
        if isinstance(result, Exception):
            self.status.setText(f"Transfer stopped: {result}")
            return
        result.skipped += self.pending_skipped
        result.failed += len(self.scan_errors)
        self.status.setText(f"{result.copied} copied · {result.skipped} skipped · {result.cancelled} cancelled · {result.failed} failed")
        self.details.appendPlainText("\n".join(result.details))

    def cancel(self):
        if self.worker:
            self.worker.cancel.set()
            self.status.setText("Cancelling after the current copy chunk…")

    def closeEvent(self, event):
        if self.worker:
            self.cancel()
            event.ignore()
            self.status.setText("Cancelling import. Close the window again once it finishes.")
        else:
            event.accept()


def create_application():
    set_windows_app_id()
    app = QApplication(sys.argv)
    # Python can otherwise collect cyclic Qt widget references on whichever
    # worker triggers the allocation threshold. Qt widgets must be destroyed
    # on the GUI thread, so perform cyclic cleanup here instead.
    automatic_gc = gc.isenabled()
    gc.disable()
    app.gc_timer = QTimer(app)
    app.gc_timer.timeout.connect(gc.collect)
    app.gc_timer.start(1000)
    if automatic_gc:
        app.destroyed.connect(gc.enable)
    app.setWindowIcon(QIcon(str(APP_IMAGE)))
    app.setApplicationName("FLDropper")
    app.setOrganizationName("FLDropper")
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in [(QPalette.ColorRole.Window, "#343434"), (QPalette.ColorRole.WindowText, "#eeeeee"),
                        (QPalette.ColorRole.Base, "#272727"), (QPalette.ColorRole.AlternateBase, "#3c3c3c"),
                        (QPalette.ColorRole.Text, "#eeeeee"), (QPalette.ColorRole.Button, "#404040"),
                        (QPalette.ColorRole.ButtonText, "#eeeeee"), (QPalette.ColorRole.Highlight, "#75603c"),
                        (QPalette.ColorRole.HighlightedText, "#ffffff"), (QPalette.ColorRole.ToolTipBase, "#404040"),
                        (QPalette.ColorRole.ToolTipText, "#eeeeee")]:
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#919191"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#919191"))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
    return app


def main():
    app = create_application()
    window = MainWindow()
    window.show()
    window.detect_missing_roots()
    sys.exit(app.exec())
