# FL Dropper

Drop FL Studio presets, samples, scripts, projects, folders, or ZIP files into one small window and copy them to the right place. FL Dropper keeps your original files and archives unchanged.

## Install on Windows

1. Install **Python 3.12 or newer** from [python.org](https://www.python.org/downloads/). If the installer offers **Add Python to PATH**, enable it.
2. Download this repository and extract the ZIP, or clone it. Keep the entire folder together in a location you can write to, such as your Documents folder.
3. Double-click **setup.bat**. An internet connection is needed to download the app's dependencies. Wait for **Setup complete**.
4. Double-click **run.bat** to open FL Dropper.

After setup, use **run.bat** whenever you want to open the app. You do not need to activate Python or enter commands.

## First-time setup

1. Open **Settings** and click **Auto detect folders**.
2. Check the detected folders. Empty fields are filled when there is one valid match; if several installations are found, choose the one you use. Saved folder choices are kept. You can also browse manually.
3. Choose destinations for content you organize yourself, such as samples, MIDI files, and projects.
4. Click **Save**.

The folder settings mean:

| Setting | What to select |
| --- | --- |
| **User Data Folder** | Your FL Studio content folder, containing folders such as `Presets`, `Projects`, and `Settings`. |
| **Shared User Data Folder** | The Image-Line parent folder shown in FL Studio's File settings. Custom ZGameEditor Visualizer effects use this location. |
| **FL Studio Install Folder** | Your FL Studio program folder, containing `FL64.exe` and `Plugins`. |

Prefer user-data destinations for your own presets so they carry over when you upgrade FL Studio. You only need to configure the folders used by your destinations.

## Copy files

1. Leave the destination dropdown on **Auto Detect**, or select a destination yourself.
2. Drop files, folders, or ZIP archives onto **Drop files here**. You can also click the panel to select files.
3. Review any destination choices or folder/ZIP import summary, then confirm.

**Auto Detect** handles each loose file separately. Recognized `.fst` presets go to the matching plugin's configured folder. If the plugin or destination cannot be determined, FL Dropper asks you to choose.

When a new plugin is recognized, FL Dropper looks for its folder and prefers your user-data location. A single matching user-data folder is remembered automatically. Otherwise, you can choose a suggested location, browse elsewhere, or create a new folder.

The highlighted text shows the last dropped filename and plugin. The status line reports the results; click its caret to see individual file details. Use the **folder icon** to open the destination.

### Folders and ZIP files

- In **Auto Detect**, `.fst` presets are grouped by plugin, including presets in subfolders. Companion files such as samples and images are copied with each plugin group, keeping their relative paths.
- Each destination receives a folder named after the dropped folder or ZIP archive.
- To keep a package together in one place, select a destination before dropping it. For a general mixed package, use a custom destination that accepts any file.
- ZIP archives containing an FL Studio project offer **Keep ZIP as file**. Nested ZIP archives are not unpacked automatically.

### Duplicate filenames

If a destination already contains a file with the same name, choose **Replace**, **Skip**, **Keep both**, or **Cancel remaining**. **Keep both** adds a number to the new filename. You can apply your choice to the remaining conflicts in that import.

In Settings, **Always replace duplicate files (without prompting)** enables automatic replacement for future imports. It is **off by default**.

## Add or change destinations

Click the **folder-plus icon**, choose a folder, and enter the plugin name. The location is saved in the dropdown for future use.

Use **Settings** to rename, edit, disable, or delete destinations and change their accepted file extensions. A destination with no extensions accepts any file when selected manually. Samples, MIDI files, and projects can go into folders of your choice.

## Update

Close FL Dropper, update or replace the downloaded app files, and run **setup.bat** again. Then open **run.bat**. Your settings are saved separately from the app folder.

## Troubleshooting

- **Python is missing or too old:** install Python 3.12 or newer, then rerun setup.
- **The app will not start:** run setup again and check the messages in the launcher window.
- **Auto Detect finds nothing:** browse to your folders in Settings. Automatic discovery is optional.
- **A preset is not recognized:** choose its destination manually. Not every preset format can be identified automatically.
- **Access denied:** check the destination shown in the error. Choose a writable user-data location where appropriate; FL Studio's program folder may be protected.
- **A ZIP cannot be imported:** check that it opens normally and is not encrypted. Unsafe or oversized archives may be rejected; archive limits are available in Settings.

## macOS (experimental)

macOS launch scripts are included, but the app has not been verified on macOS. Automatic folder discovery and installation-folder validation currently support Windows only. Use manually selected user-data folders or absolute destinations.

Install Python 3.12 or newer, open Terminal in the extracted app folder, and run:

```bash
bash setup.command
```

After setup, double-click **run.command**, or launch it from Terminal with:

```bash
bash run.command
```

Rerun `bash setup.command` after updating the app.
