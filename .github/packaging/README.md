# GitHub desktop builds

To trigger the GitHub build from Windows, install GitHub CLI, run `gh auth login`,
commit and push your changes, then double-click `build.bat` in the repository
root or run `.\build.bat --no-pause`. It requires a clean checkout, fetches the
current branch from `origin`, verifies that the remote commit matches HEAD,
and reads `__version__` to create and push its version tag, such as `v0.9.0b4`.
The tag push triggers `pyinstaller-build.yaml` once; a separate dispatch is not
sent. If the remote tag already points to HEAD, it dispatches on that tag instead.
If a local or remote tag points to different code, increment the version before
building; tags are never force-updated. Runs are named `Build v0.9.0b4` and use
the version tag as their ref. The PowerShell helper is `scripts/start-github-build.ps1`.
It prints recent runs
so you can follow progress. `.\build.bat --check` checks prerequisites without
creating/pushing tags or dispatching. Python is not required locally; builds run on GitHub's runners.
The ZIP names read `fldropper/__init__.py` from the pushed commit. The script
does not commit or push branch changes, or publish a release.

For a local build instead, install the CI build dependencies in your project
`.venv` and run `python .github/packaging/build.py`. Local ZIPs are written to
`.github/packaging/dist`.

Push these tracked helpers and `.github/workflows/pyinstaller-build.yaml` to
GitHub. Open **Actions → Build desktop apps → Run workflow**. Pushing a `v*` tag
also starts a build. No release is published automatically.

A prerequisite job checks tag builds before any platform build starts. The tag
must exactly equal `v` plus `__version__` (for example, `v0.9.0b4`). A mismatch
fails the workflow and skips every platform build. Manual runs on branches
skip this comparison; manual runs targeting tags must also match.

Update `fldropper/__init__.py`'s `__version__` before committing a release,
then use a matching `v<version>` tag. Both the uploaded artifact and its
distribution ZIP include this version, platform, and architecture. Manual
builds use the same version source. For example:
`FLDropper-0.9.0b4-Windows-AMD64.zip`. App bundle and executable names stay
stable so shortcuts and launchers continue to work.

The workflow builds Windows x64, Mac Apple Silicon, and Mac Intel separately,
using Python 3.12. Each job checks the actual bundled app offscreen before
uploading a ZIP. The distributable uses `actions/upload-artifact@v7` with
`archive: false`, so GitHub serves the versioned ZIP directly without wrapping
it in another ZIP. Download the matching artifact and extract it once.
Previously uploaded artifacts keep their old nested structure; start a new
workflow run after pushing this change. On Windows, keep FL Dropper.exe and
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
