"""Reject tags that do not exactly match the checkout's application version."""
import os
from pathlib import Path
import runpy


def main():
    if os.environ.get("GITHUB_REF_TYPE") != "tag":
        print("Not a tag build; version check skipped.")
        return
    root = Path(__file__).resolve().parents[2]
    version = runpy.run_path(str(root / "fldropper" / "__init__.py"))["__version__"]
    expected = f"v{version}"
    actual = os.environ.get("GITHUB_REF_NAME", "")
    if actual != expected:
        raise SystemExit(
            f"Tag {actual!r} does not match __version__ {version!r}. "
            f"Expected tag {expected!r}. Update the version and tag the matching commit."
        )
    print(f"Version verified: {actual}")


if __name__ == "__main__":
    main()
