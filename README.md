# FL Dropper

Producer: **Nelson Fernandez Jr. (NFX @ Warbeats)**

Drop FL Studio presets, samples, scripts, projects, folders, or ZIP files into one small window and copy them to the right place. FL Dropper keeps your original files and archives unchanged.

## Install on Windows

1. Install **Python 3.12 or newer** from [python.org](https://www.python.org/downloads/). If the installer offers **Add Python to PATH**, enable it.
2. Download this repository and extract the ZIP, or clone it. Keep the entire folder together in a location you can write to, such as your Documents folder.
3. Double-click **setup.bat**. An internet connection is needed to download the app's dependencies. Wait for **Setup complete**.
4. Double-click the **FL Dropper** desktop shortcut, or **run.bat**, to open FL Dropper.

After setup, use **run.bat** whenever you want to open the app. You do not need to activate Python or enter commands.

Setup creates or refreshes a Windows desktop shortcut with the bundled FL Dropper icon. Its target, working folder, and icon paths come from the current project location. If you move the project folder, rerun **setup.bat** to update the shortcut. The icon file stays in the project folder; it is referenced by the shortcut, not embedded in it. If shortcut creation fails, setup reports it and **run.bat** remains available.

## First-time setup

1. On launch, FL Dropper automatically looks for missing folder settings and saves unique valid matches. Saved paths are kept; no detection dialog is shown. If a folder is missing or several matches exist, open **Settings** to choose it. You can also click **Auto detect folders** to retry.
2. Check the detected folders. Empty fields are filled when there is one valid match; if several installations are found, choose the one you use. Saved folder choices are kept. You can also browse manually.
3. Choose destinations for content you organize yourself, such as samples and projects.
4. Click **Save**.

The folder settings mean:

| Setting | What to select |
| --- | --- |
| **FL Studio Install Folder** | Your FL Studio program folder, containing `FL64.exe` and `Plugins`. |
| **Shared User Data Folder** | The Image-Line parent folder shown in FL Studio's File settings. Custom ZGameEditor Visualizer effects use this location. |
| **User Data Folder** | Read-only: the `FL Studio` subfolder inside Shared User Data. Updates automatically when you change the shared folder. |

Prefer user-data destinations for your own presets so they carry over when you upgrade FL Studio. You only need to configure the folders used by your destinations.

## Copy files

1. Leave the destination dropdown on **Auto Detect**, or select a destination yourself.
2. Drop files, folders, or ZIP archives onto **Drop files here**. You can also click the panel to select files.
3. Review any destination choices or folder/ZIP import summary, then confirm.

**Auto Detect** handles each loose file separately. Recognized `.fst` presets go to the matching plugin's configured folder. If the plugin or destination cannot be determined, FL Dropper asks you to choose.

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

FXP imports look up the embedded VST2 plugin ID in the FST files under your configured User Data folder’s `Presets/Plugin database/Installed/Generators` and `Effects`. The matching FST supplies the plugin identity and category; its Plugin Manager `.nfo` name (or database FST filename) supplies the destination name, using the normal `Fruity Wrapper - <plugin name>` destination. No plugin is loaded or executed. Missing or conflicting matches fail with a message; scan the plugin in FL Studio Plugin Manager before retrying. This applies to loose FXPs and FXPs inside folders or ZIPs. If a package contains an unmatched FXP, that package fails inspection before copying.

The supplied Albino CracklePad FXP uses ID `H4M9` and an omitted outer size. FL Dropper checks its exact inner chunk length and, if no direct match exists, looks up installed Albino ID `g7U0`. A matching installed FST is still required; this alias comes from the user-identified sample and local Albino metadata.

H2P presets are identified by their embedded `#AM` product name and matched to an installed-plugin FST, including VST3 entries. The FST supplies the identity and category, and the Plugin Manager name supplies the normal `Fruity Wrapper - <plugin name>` destination. Missing or conflicting matches stop the import with a message. Loose files, folders, and ZIPs are supported; source files remain unchanged. H2P is shared by multiple u-he plugins, so the extension alone does not imply Diva. See [u-he’s Diva user guide](https://u-he.com/downloads/manuals/plugins/diva/Diva-user-guide.pdf).


FST headers distinguish **channel states** from **plugin presets**. **3x Osc channel states** are an exception to the User Data preference: they go to `Data/Patches/Channel presets/3x Osc` inside FL Studio Install Folder. The detected channel-state type appears in the highlighted filename and import details. Installation-folder permissions may prevent copying; the app reports the failing path.

When a new plugin is recognized, FL Dropper looks for its folder in User Data first. A single matching user-data folder is remembered automatically. Otherwise, the location dialog defaults to a User Data folder, offering to create it even if a matching installation folder already exists. You can explicitly choose an installation folder or browse elsewhere. New destinations in Settings also default to User Data.

The highlighted text shows the last dropped filename and plugin. The status line reports the results; click its caret to see individual file details. Use the **folder icon** to open the destination.

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

### Duplicate filenames

If a destination already contains a file with the same name, choose **Replace**, **Skip**, **Keep both**, or **Cancel remaining**. **Keep both** adds a number to the new filename. You can apply your choice to the remaining conflicts in that import.

In Settings, **Always replace duplicate files (without prompting)** enables automatic replacement for future imports. It is **off by default**.

## Add or change destinations

Click the **folder-plus icon**, choose a folder, and enter the plugin name. The location is saved in the dropdown for future use.

Use **Settings** to rename, edit, disable, or delete destinations and change their accepted file extensions. A destination with no extensions accepts any file when selected manually. Samples and projects can go into folders of your choice. The Scores destination is also editable.

## Update

Close FL Dropper, update or replace the downloaded app files, and run **setup.bat** again. Then open **run.bat**. Keep your `config.json` when updating to preserve settings.

## Your settings

Folders, custom destinations, and preferences are saved in **config.json in the app folder**, beside `run.bat` and `setup.command`. Each copy of FL Dropper has its own settings. A new directory starts with the bundled known destinations and preferences, including previously learned plugin locations. Install, Shared User Data, and User Data root paths start blank and are detected on that computer. Existing configuration files keep their own settings.

To reset a copy, close the app and rename its `config.json` as a backup. To move your settings to another copy, copy that file. **Settings â†’ Open configuration** opens the configuration file after it has been saved. Keep the app in a writable folder.

Settings from older versions stored under your user profile are not imported automatically. To keep them, copy the old `config.json` into the app folder before launching.

## Troubleshooting

- **Python is missing or too old:** install Python 3.12 or newer, then rerun setup.
- **The app will not start:** run setup again. On Windows, check any messages in the launcher window. On macOS, use `bash run.command` in Terminal to see errors, or check `~/Library/Logs/FLDropper.log`.
- **Auto Detect finds nothing:** browse to your folders in Settings. Automatic discovery is optional.
- **A preset is not recognized:** choose its destination manually. Not every preset format can be identified automatically.
- **Access denied:** check the destination shown in the error. Choose a writable user-data location where appropriate; FL Studio's program folder may be protected.
- **A ZIP cannot be imported:** check that it opens normally and is not encrypted. Unsafe or oversized archives may be rejected.

## macOS (experimental)

macOS launchers are included, but the app has not been verified on macOS. Automatic folder discovery and installation-folder validation currently support Windows only. Use manually selected user-data folders or absolute destinations.

Install Python 3.12 or newer, open Terminal in the extracted app folder, and run:

```bash
bash setup.command
```

After setup, double-click **FL Dropper.app** to open the app without a Terminal window. Keep it inside the downloaded folder beside `setup.command`; it uses the Python environment created there. To put a shortcut elsewhere, create a Finder alias rather than moving the app launcher.

For troubleshooting, **run.command** still opens the app with Terminal messages:

```bash
bash run.command
```

Rerun `bash setup.command` after updating the app.

Plugin metadata decoding uses [PyFLP](https://github.com/demberto/PyFLP). Setup installs it automatically.
