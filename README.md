# FL Dropper

A compact Windows desktop utility for copying FL Studio content. Sources and ZIP archives are preserved. It never executes imported content or loads plugins.

## Quick start

Install Python 3.12 or newer first. On Windows, double-click **setup.bat** once, then **run.bat** to open the app. Rerun setup after updating the downloaded source. Both scripts use the project-local `.venv` and work regardless of the current working directory; activation is unnecessary.

On macOS, open Terminal in the downloaded folder and run `bash setup.command`. Setup makes both `.command` files executable; afterward, double-click **run.command**, or run `bash run.command` in Terminal. These are equivalent launch scripts, not a claim of verified macOS support: Windows discovery and installation-root validation remain Windows-specific. Use manually configured user-data or absolute destinations. The macOS scripts have been syntax-checked but not run on macOS.

## Setup and run (PowerShell, manual alternative)

Requires Windows and Python 3.12 or newer. Tested with Python 3.12.10 and PySide6 6.12.0.

```powershell
# Open PowerShell in your downloaded or cloned FL Dropper folder.
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
python -m fldropper
# Alternatively, after installation:
fldropper
```

If PowerShell prevents activation, use `.\.venv\Scripts\python.exe` in place of `python`; activation is optional. There is no installer or executable packaging.

## Use

1. Open **Settings** and click **Auto detect folders**, or browse manually. Detection populates empty folder fields automatically when each has one valid candidate. Existing values remain unchanged; multiple candidates require a choice, and missing candidates leave the field empty with guidance. Click **Save** to apply. **User Data Folder** is the FL Studio content folder containing `Settings` and `Presets`/`Projects`. **Shared User Data Folder** is the Image-Line parent shown in FL Studio's File settings; custom ZGE effects use this root. The install folder must contain `FL64.exe` and `Plugins`.
2. Edit the destination catalog. Piano Roll scripts, ZGameEditor objects, and the twelve plugin preset destinations below have relative paths. Generic preset categories, samples, MIDI, and projects need your chosen folder. Prefer user-data destinations so presets carry over between FL Studio installation upgrades. Use a base root and relative subfolder, or choose an existing absolute folder. New subfolders may be created beneath that root. Changing a base root updates derived destinations; absolute choices stay fixed.
3. Use the **folder-plus glyph** to add a destination: select its folder, then enter the plugin name. The new `.fst` location is saved and selected in the dropdown. Folders beneath a configured root use a relative path; others use an absolute path. The entered plugin name is also matched against FST metadata for Auto Detect; multiple matching locations require a choice. Edit extensions and other options in Settings.
4. Drop multiple files/folders or click the panel for files. **Auto Detect** resolves files individually. Loose `.fst` files with a recognized native plugin identifier route to that plugin's configured destination; unidentified/shared formats require a choice. Explicit destinations reject incompatible extensions and suggest compatible routes. Empty extensions make a custom destination accept any file, manual only.
5. Review folder/ZIP imports. In **Auto Detect**, FST presets inside subfolders or ZIP entries are identified and grouped by plugin. Each group is preselected to its matching plugin destination. Shared companion files (samples, images, notes) are copied with every group, preserving their relative paths. Each destination gets a wrapper named after the dropped folder or archive; existing wrapper subfolders are not stripped. Unidentified FSTs and other primary content appear as separate rows requiring a choice or skip. ZIP projects containing `.flp` remain whole and offer **Keep ZIP as file**. Choosing an explicit destination before dropping retains whole-package handling. Nested ZIPs remain files and are never recursively extracted.
6. Existing-file conflicts offer **Replace**, **Skip** (default), **Keep both**, or **Cancel remaining**. The optional repeated choice applies only to this import. Settings also offers **Always replace duplicate files (without prompting)**, off by default. Enabling it replaces file conflicts automatically for future imports until disabled. Keep both adds ` (2)`, ` (3)`, etc. Cancellation preserves already committed copies. Expand details for per-file results, skipped links, and errors.

Auto Detect requires configuration when a unique matching route has no usable path. New plugin names in folder/ZIP FST groups use the same folder-discovery flow as loose presets. Package planning only offers configured compatible destinations. For a mixed package that should stay together, explicitly select a custom accept-any destination before dropping it. Project archives are not split even when they contain FST presets. Files and directories at the same destination path cannot replace one another.

When Auto Detect identifies a **new plugin name** in a loose FST, it searches the configured user-data and shared-data roots before the installation root for existing folders with that exact name (case-insensitive). The search runs in the worker, skips links/reparse points, and is limited to 50,000 entries per root and ten folder levels; limits/access errors appear in details. A unique user-data or shared-user-data match is added to the known locations and used automatically, even if an installation match also exists. Multiple user-data matches, installation-only matches, or no matches still ask once per plugin in the batch: **Path found. Use…** lists existing matches, with user-data choices first. **Path not found. Use…** offers new user-data `Presets/Plugin presets/Generators/<plugin>` or `Effects/<plugin>` folders; choose the appropriate category and confirm creation. These are proposed organizational destinations, not a claim that the app inferred generator versus effect type from the plugin name. **Other… browse** selects a different folder, or a parent under which you can enter a new subfolder. Confirming creates the folder if needed, saves the plugin location, and continues copying. **Skip this plugin** skips only that plugin's files for this batch; the originals remain intact. Existing named destinations, including disabled entries, are respected. An identified plugin is never silently routed to another plugin just because both use `.fst`.

Protected installation directories may fail with a permission error that identifies the path. FL Dropper never elevates or silently redirects. Configure a documented writable location, or manage folder permissions independently.

## Configuration

UTF-8 JSON is stored at Qt's per-user `AppConfigLocation` under organization/application `FLDropper`, in `config.json`. **Open configuration** reveals the actual file. **Reload** reads external edits; **Save** validates the whole configuration and writes atomically. Malformed files are preserved and imports are disabled until the file is repaired and reloaded. Saving settings also checks the existing file before replacing it. The bundled [example configuration](example-config.json) has no personal paths.

Schema version 1 stores roots, stable destination IDs, names, enabled states, extensions, root type, path, automatic participation, last selection, and ZIP limits. Unknown top-level and destination fields survive edits. A small version-0 migration accepts the earlier top-level root names. Other schema versions require an explicit upgrade. Blank root/path values mean setup is incomplete. ZIP limits are editable in Settings: 10,000 entries, 2 GiB expanded data, and a maximum 200:1 per-entry compression ratio by default.

Catalog revision 1 adds the twelve named plugin destinations to older configurations on load. Existing destination edits are preserved; after saving the upgraded catalog, deleted entries stay deleted. Restart the app or use Settings **Reload** to load the expansion. All twelve use the user-data root, not a version-specific installation. The supplied `FL Studio` prefix is omitted from their relative paths because the configured content root already includes it. Only `.fst` is assumed; add plugin-specific formats in Settings after verifying them. Unidentified `.fst` files still require a destination choice in Auto Detect.

Catalog revision 2 corrects the ZGE objects default to `shared_data/ZGameEditor Visualizer/Effects` and sets Visualizer `.fst` presets to `user_data/Presets/Plugin presets/Effects/ZGameEditor Visualizer`. Only unchanged older defaults are migrated; custom overrides remain intact. The additional `shared_data` root is explicitly editable and discovered from the registry's `Shared data` parent. It is not inferred by allowing `..` paths to escape the content root. Custom ZGE effects no longer default to a version-specific install directory.

## Discovery and path evidence

Sources were checked on 2026-10-14. Shared registry values and corresponding folder structures were also verified read-only against the local FL Studio 2026 installation. Import behavior inside FL Studio itself remains unverified.

| Catalog entry | Extensions | Destination policy / evidence |
| --- | --- | --- |
| Piano Roll scripts | `.pyscript` | `Settings/Piano roll scripts` relative to the selected FL Studio user-content root. [Image-Line scripting documentation](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/pianoroll_scripting_api.htm) shows `Documents/Image-Line/FL Studio/Settings/Piano roll scripts`. Confirm how the root displayed by your FL version relates to its `FL Studio` subfolder; edit this destination as needed. |
| ZGameEditor objects | `.zgeproj` | `ZGameEditor Visualizer/Effects` relative to **Shared User Data Folder**, outside the `FL Studio` subfolder. Confirmed present under the locally registered shared-data root on 2026-10-15. The older installation-folder example describes factory effects and is not the preferred custom import destination. Verify effect categories appear in your installed plugin; in-plugin validation is still pending. |
| Visualizer plugin presets | `.fst` | `Presets/Plugin presets/Effects/ZGameEditor Visualizer` relative to **User Data Folder**; confirmed present locally. Plugin-state presets are distinct from `.zgeproj` objects. |
| Generator / effect presets | `.fst` | Separate user-configured entries. Extension alone cannot identify category or plugin. [File settings](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/envsettings_files.htm) recommends saving a preset to establish its location. |
| Named plugin presets | `.fst` | User-provided locations under `Presets/Plugin presets/Generators` for Autogun, DirectWave, Harmless, Harmor, Kepler Exo, MiniSynth, Ogun, PoiZone, Sytrus, and Transistor Bass; under `Presets/Plugin presets/Effects` for Patcher and Wave Candy. Each has its own destination. |
| Samples | `.wav`, `.aif`, `.aiff`, `.mp3`, `.ogg`, `.flac` | Conservative common audio routes; user-selected organization folder, not a required system location. Edit the accepted extension list for your workflow. |
| MIDI | `.mid`, `.midi` | User-selected organization folder. |
| Projects | `.flp`, `.zip` | User-selected organization folder. [Image-Line Browser documentation](https://www.image-line.com/fl-studio-learning-content/fl-studio-online-manual/html/browser.htm) identifies FLP projects and zipped projects containing samples. Intact ZIP project routing requires an FLP entry in the inspected archive. |

**Registry discovery is read-only and Windows-only.** It checks `HKCU\Software\Image-Line\Shared\Paths` first, then `HKLM\SOFTWARE\Image-Line\Shared\Paths`, including both 64-bit and 32-bit views. The value names `Shared data`, `Install path`, and `FL Studio` were verified on the local installation. `Shared data` identifies the Image-Line parent; discovery resolves its `FL Studio` content subfolder rather than appending `Settings` directly to the parent. A content candidate must contain `Settings` and either `Presets` or `Projects`; stale, inaccessible, relative, and arbitrary folders are discarded. Fresh or nonstandard layouts that lack those markers can still be configured manually. [Image-Line File settings](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/envsettings_files.htm) describes the parent/FL Studio subfolder layout.

If neither shared key yields a valid data candidate, discovery enumerates existing `Software\Image-Line\FL Studio <version>` keys and their existing `General`/`Paths` branches for the same `Shared data` value. Version key names are discovered rather than hardcoded. Local version keys exist, but no data-path values were present in them: this fallback is best-effort and verified with mocks, not claimed as a universal historical schema. If registry detection fails, suggestions use `SHGetKnownFolderPath` for [FOLDERID_Documents](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid), including redirected Documents.

Install discovery uses `Install path`, or the parent of the `FL Studio` executable value (`FL64.exe`), and also checks existing version keys and conventional Program Files Image-Line directories. It verifies installation markers, deduplicates paths, and sorts identifiable folder versions numerically newest first. Version ranking is a folder-name hint; an unversioned/custom-named installation cannot reliably be ranked. All valid candidates remain selectable, registry evidence is shown, and no version is silently selected or saved. Saved roots are never overwritten by detection; clear a root explicitly before choosing a replacement. Scanning runs in a worker thread. No registry values are written and no imported content is launched.

Windows discovery is isolated in `discovery.py`. macOS discovery is deferred and needs verified platform-specific locations plus manual fallback. It does not use Windows registry logic on macOS. Worker communication follows [Qt's QThread signal guidance](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html); pure routing/configuration/transfer logic does not import widgets.

## Copy and archive behavior

FST identification reads at most 64 KiB per preset in the scanning worker, including FSTs in folders and validated ZIP entries. It validates `FLhd`/`FLdt` framing and walks length-prefixed events to the outer plugin's `InternalName` event (201 / `0xC9`), supporting legacy ASCII and modern UTF-16 names plus the measured FL 25.2.4/25.2.5 header variant. A read-only audit identified **all 2,966 presets across ten plugins** in the supplied FLUPI collection, with no disagreements against folder labels. It does not assume offset `0x2e`, search arbitrary binary payloads, decompress plugin state, or inspect Patcher's nested plugins. Recognition is a routing hint, not proof of preset validity; unsupported/malformed/unreadable metadata falls back to ordinary routing choices. Supported native names map only to their corresponding catalog destination; disabled/deleted plugin destinations do not silently reroute to another plugin. Explicit manual selection remains controlled by its accepted extensions. Auto Detect can split non-project FST packages into plugin groups with shared companions; manual destinations and project packages stay whole.

Each file is copied in cancellable 1 MiB chunks to a temporary file on the destination filesystem, flushed, timestamped, and committed. Failed replacement leaves the old destination intact. New-file commits are atomic and do not overwrite an existing path; a newly appeared file triggers conflict handling. Existing replacements recheck file identity/size/mtime after the decision. As with ordinary path-based desktop copying, simultaneous hostile filesystem mutations between a check and a commit are outside the security model; do not import into folders another process is actively restructuring.

Dropped symlinks, junctions, and reparse points are rejected or reported as skipped. Destination ancestors are checked before writes. Unsafe Windows names, traversal, drive/UNC paths, alternate data streams, ZIP symlinks/special files, case-insensitive duplicates and file/directory collisions are rejected. Archives are inspected before extraction and rechecked before staging. Extraction enforces actual byte counts as well as declared limits. Corrupt and encrypted archives report errors. Temporary extraction and copy staging are cleaned on ordinary success, failure, and cancellation. A forced process termination can leave a `.fldropper-*.tmp` file; imports are not globally transactional.

## Verification status

Latest run: **120 passed, 1 skipped** on Windows / Python 3.12.10. `pip check` reported no broken requirements; package compilation also passed.

Automated checks run on Windows with real temporary filesystem transfers and Qt widgets/worker threads. Native Windows Qt main/settings renders were visually inspected for readable dark styling. Tests cover configuration resolution/overrides, persistence/migration/invalid JSON, missing/multiple/stale suggestion candidates, routes, conflict choices, source preservation, same-file/recursive rejection, folder companions, ZIP structure/intact copies/traversal/collisions/limits/corruption/symlinks, partial failures, cancellation, cleanup, changed/new conflicts, custom settings, restart selection, and UI-to-worker conflict responses. The symlink creation test is skipped when Windows privileges prevent creating links.

Still needs a human Windows/FL Studio acceptance pass:

- Actual Explorer drag/drop and file/folder picker interaction with multiple items.
- Confirm active user root and both documented derived paths against the installed FL Studio version; verify imported content appears in FL Studio.
- Protected Program Files permission failures with a real installation (automated failure injection is covered).
- Interactive package/conflict dialogs, apply-to-remaining, and cancellation during a large real-world import.
- Redirected Documents/OneDrive suggestions and installations outside conventional folders.

Live read-only Shared Paths discovery returned the local FL Studio 2026 install and its user-content folder. Tests additionally cover HKCU/HKLM and 32/64-bit views, missing/denied keys, stale paths, string types and environment expansion, duplicate/multiple candidates, version-key fallback, install executable fallback, and latest-version ordering. In-FL-Studio validation is not claimed.
