# GitHub desktop builds

Push these tracked helpers and `.github/workflows/pyinstaller-build.yaml` to
GitHub. Open **Actions → Build desktop apps → Run workflow**. Pushing a `v*` tag
also starts a build. No release is published automatically.

The workflow builds Windows x64, Mac Apple Silicon, and Mac Intel separately,
using Python 3.12. Each job checks the actual bundled app offscreen before
uploading a ZIP. Download the matching artifact from the completed run, then
extract the distribution ZIP inside it. On Windows, keep FL Dropper.exe and
_internal together. On Mac, keep the complete FL Dropper.app bundle.

These builds are unsigned; Apple notarization and Windows code signing are not
configured. A successful smoke check verifies startup, artwork, defaults, and
main-window construction, not interactive drag/drop or FL Studio paths.

The launcher gives packaged builds their own per-user Qt AppConfigLocation.
Source config.json is neither bundled nor imported. The normal source launcher
and the gitignored local pyinstaller/ setup are unchanged. Generated build/ and
dist/ directories are ignored by the repository's existing rules.

The workflow must be pushed before GitHub can run it. Mac builds require the
hosted runners; they cannot be verified by running this helper on Windows.
