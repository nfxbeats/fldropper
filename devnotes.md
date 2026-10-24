# FL Dropper development notes

Installation and basic usage are in [README.md](README.md).

## Setup implementation

Setup creates the app’s `.venv` and installs dependencies from `pyproject.toml`; no `requirements.txt`, manual dependency installation, or environment activation is needed. It reuses a healthy `.venv` and automatically rebuilds one that is broken, missing pip, or uses an incompatible Python. Settings and other app files are preserved. Close FL Dropper before rerunning setup. Links or junctions inside `.venv` require manual removal.

Setup reuses a healthy `.venv` and automatically rebuilds an unusable one, preserving `config.json` and other app files. Close FL Dropper before rerunning setup. A `.venv` that is itself a symlink requires manual removal.

## Preset detection and routing

The generic **Generator presets** and **Effect presets** destinations default to `Presets/Plugin presets/Generators` and `Presets/Plugin presets/Effects` inside User Data Folder.

For wrapped plugins, the factory plugin name from VST metadata is used automatically. For example, Strum GS-2 uses `Generators/Fruity Wrapper - Strum GS-2` even if its channel was renamed to `Gtr Lead1`. The channel label appears separately in details. If the factory name is unavailable, choose a previously used plugin name or type one; the channel label is never assumed to be the plugin identity. Wrapped-plugin folder names always use **Fruity Wrapper - <plugin name>**. You choose Generator or Effect when the file does not identify its category. Named locations are remembered for future imports.

Patcher presets are identified as **Effect** or **Generator** and go to their respective `Effects/Patcher` or `Generators/Patcher` preset folders. Both destinations appear in Settings. If a preset does not include enough information to identify its type, you choose the destination.

FPC kits use `Presets/Plugin presets/Generators/FPC` inside User Data Folder. The preset and its accompanying samples are copied together into the kit folder.

Morphine presets in either `.fst` or native `.mrp` format use the same destination: `Presets/Plugin presets/Generators/Morphine` inside User Data Folder.

Sampler channel-state `.fst` files with an empty internal plugin identity use `Presets/Channel presets` inside User Data Folder.

Channel envelope `.chenv` files use `Presets/Channel envelopes` inside User Data Folder.

Mixer-track `.fst` presets are recognized by their mixer-state header and copied to `Presets/Mixer presets` inside User Data Folder, including folder and ZIP imports.

Sawer presets in `.fst` or `.sawer` format use `Presets/Plugin presets/Generators/Sawer` inside User Data Folder.

Toxic Biohazard presets in `.fst`, `.txd`, or `.tbio` format use `Presets/Plugin presets/Generators/Toxic Biohazard` inside User Data Folder.

FXP imports look up the embedded VST2 plugin ID in the FST files under your configured User Data folder’s `Presets/Plugin database/Installed/Generators` and `Effects`. The matching FST supplies the plugin identity and category; its Plugin Manager `.nfo` name (or database FST filename) supplies the destination name, using the normal `Fruity Wrapper - <plugin name>` destination. No plugin is loaded or executed. Missing or conflicting matches fail with a message; scan the plugin in FL Studio Plugin Manager before retrying. Verified native-plugin IDs, such as PoiZone’s `SawW`, can also match their installed native FST, which has no VST ID. This applies to loose FXPs and FXPs inside folders or ZIPs. If a package contains an unmatched FXP, that package fails inspection before copying.

The supplied Albino CracklePad FXP uses ID `H4M9` and an omitted outer size. FL Dropper checks its exact inner chunk length and, if no direct match exists, looks up installed Albino ID `g7U0`. A matching installed FST is still required; this alias comes from the user-identified sample and local Albino metadata.

H2P presets are identified by their embedded `#AM` product name and matched to an installed-plugin FST, including VST3 entries. The FST supplies the identity and category, and the Plugin Manager name supplies the normal `Fruity Wrapper - <plugin name>` destination. Missing or conflicting matches stop the import with a message. Loose files, folders, and ZIPs are supported; source files remain unchanged. H2P is shared by multiple u-he plugins, so the extension alone does not imply Diva. See [u-he’s Diva user guide](https://u-he.com/downloads/manuals/plugins/diva/Diva-user-guide.pdf).


FST headers distinguish **channel states** from **plugin presets**. **3x Osc channel states** are an exception to the User Data preference: they go to `Data/Patches/Channel presets/3x Osc` inside FL Studio Install Folder. The detected channel-state type appears in the highlighted filename and import details. Installation-folder permissions may prevent copying; the app reports the failing path.

When a new plugin is recognized, FL Dropper looks for its folder in User Data first. A single matching user-data folder is remembered automatically. Otherwise, the location dialog defaults to a User Data folder, offering to create it even if a matching installation folder already exists. You can explicitly choose an installation folder or browse elsewhere. New destinations in Settings also default to User Data.

## Structured packages and scripts

### Folders and ZIP files

- In **Auto Detect**, `.fst` presets are grouped by plugin, including presets in subfolders. Companion files such as samples and images are copied with each plugin group, keeping their relative paths.
- Each destination receives a folder named after the dropped folder or ZIP archive. If a ZIP already has one enclosing folder containing everything, that folder is reused without adding a second ZIP-name folder.
- To keep a package together in one place, select a destination before dropping it. For a general mixed package, use a custom destination that accepts any file.
- ZIP archives containing an FL Studio project offer **Keep ZIP as file**. Nested ZIP archives are not unpacked automatically.

### Scripts and helper files

Auto Detect reads script imports without running them:

| Script type | Recognized by | Destination inside User Data Folder |
| --- | --- | --- |
| [Piano Roll](https://il-group.github.io/FL-Studio-API-Stubs/piano_roll_scripting/) | A `.pyscript` importing `flpianoroll`, directly or through a supplied helper | `Settings/Piano roll scripts` |
| [Edison / Slicex](https://il-group.github.io/FL-Studio-API-Stubs/edison_scripting/) | A `.pyscript` importing `enveditor`, directly or through a supplied helper | `Settings/Audio scripts` |
| [MIDI hardware](https://il-group.github.io/FL-Studio-API-Stubs/midi_controller_scripting/script_files/) | A `device_*.py` entry point | `Settings/Hardware/<script folder>` |

Drop the complete script folder or ZIP to include its `.py` helpers and resources. Script packages stay together, preserving internal paths. If you drop loose script files together from the same folder, only those selected files are grouped and copied; other files beside them are not included automatically.

Unidentified scripts, helpers without an entry point, and packages containing different script types require a destination choice. Import separate script folders individually when they need different destinations. Review dependency notes in the import summary or expandable details; external and dynamic imports cannot be fully verified.

Hardware entry points must be directly inside their controller folder. ZIPs with a single enclosing controller folder are handled automatically. For deeper nesting or multiple controller folders, extract the ZIP and drop each folder containing `device_*.py`. FL Dropper flags these deeper layouts rather than automatically installing them at the wrong depth.

### Scores and MIDI

`.fsc`, `.mid`, and `.midi` files use **Scores**, which defaults to `Presets/Scores` inside your FL Studio User Data Folder. If Scores has subfolders, an import asks which folder to use. Choose the Scores root, an existing subfolder, or enter a new subfolder name to create it. The choice applies to all scores in that import. With no existing subfolders, scores copy directly into Scores. Folder and ZIP imports preserve their package structure inside the chosen location.

## Your settings

Folders, custom destinations, and preferences are saved in **config.json in the app folder**, beside `run.bat` and `setup.command`. Each copy of FL Dropper has its own settings. A new directory starts with the bundled known destinations and preferences, including previously learned plugin locations. Install, Shared User Data, and User Data root paths start blank and are detected on that computer. Existing configuration files keep their own settings.

To reset a copy, close the app and rename its `config.json` as a backup. To move your settings to another copy, copy that file. **Settings → Open configuration** opens the configuration file after it has been saved. Keep the app in a writable folder.

Settings from older versions stored under your user profile are not imported automatically. To keep them, copy the old `config.json` into the app folder before launching.

First-install destinations and preferences come from `fldropper/defaults.json`, with blank root paths. `example-config.json` mirrors that portable snapshot. Existing configs retain their settings, subject to explicit catalog migrations.

## Checking macOS setup without a Mac

A manually triggered **macOS test** workflow is included in `.github/workflows/macos-test.yaml`. After pushing the repository to GitHub, open **Actions → macOS test → Run workflow**. It uses a real GitHub-hosted macOS runner to install dependencies, rebuild a broken environment, verify reuse and config preservation, and create a Qt window offscreen. No FL Studio installation is required. [GitHub-hosted runners](https://docs.github.com/en/actions/how-tos/manage-runners/github-hosted-runners/use-github-hosted-runners).

The workflow has not been run from this Windows development machine. It tests setup using preinstalled Python, not Homebrew installation on a clean Mac or the interactive Python installer. Finder launching, macOS permission dialogs, FL Studio paths, and actual imports still need a Mac user to verify. Windows shell simulations cannot establish macOS compatibility.
