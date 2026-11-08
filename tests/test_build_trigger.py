"""Exercise real tag operations in temporary repositories; GitHub CLI is mocked."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows BAT/PowerShell build helper")
HELPER = Path(__file__).resolve().parents[1] / "scripts/start-github-build.ps1"


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "checkout with spaces"
    remote = tmp_path / "origin.git"
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    log = tmp_path / "gh.log"
    (mock_bin / "gh.cmd").write_text('@echo off\necho %* >>"%FLDROPPER_TEST_GH_LOG%"\nexit /b 0\n', encoding="ascii")
    env = dict(os.environ, PATH=str(mock_bin) + os.pathsep + os.environ["PATH"],
               FLDROPPER_TEST_GH_LOG=str(log), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    def git(*args, cwd=root, check=True):
        return subprocess.run([shutil.which("git"), *args], cwd=cwd, env=env,
                              text=True, capture_output=True, check=check)
    git("init", "--bare", str(remote), cwd=tmp_path)
    git("init", "-b", "main", str(root), cwd=tmp_path)
    git("config", "user.name", "Build Test")
    git("config", "user.email", "build@example.test")
    (root / "fldropper").mkdir()
    (root / "fldropper/__init__.py").write_text('__version__ = "0.9.0b4"\n', encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "Version b4")
    git("remote", "add", "origin", str(remote))
    git("push", "-u", "origin", "main")
    def run(*args):
        return subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                               "-File", str(HELPER), "-ProjectRoot", str(root), *args],
                              env=env, text=True, capture_output=True, timeout=30)
    return root, remote, log, git, run


def test_new_tag_pushes_exact_version_without_duplicate_dispatch(repository):
    root, remote, log, git, run = repository
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert git("rev-parse", "v0.9.0b4^{commit}").stdout == git("rev-parse", "HEAD").stdout
    assert "refs/tags/v0.9.0b4" in git("ls-remote", "--tags", "origin").stdout
    assert "workflow run" not in log.read_text()
    assert "--branch v0.9.0b4" in log.read_text(), result.stdout + result.stderr


@pytest.mark.parametrize("annotated", [False, True])
def test_existing_same_tag_dispatches_on_version_ref(repository, annotated):
    _, _, log, git, run = repository
    git("tag", *( ["-a", "v0.9.0b4", "-m", "Beta 4"] if annotated else ["v0.9.0b4"] ))
    git("push", "origin", "refs/tags/v0.9.0b4")
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "workflow run pyinstaller-build.yaml" in log.read_text()
    assert "--ref v0.9.0b4" in log.read_text()
    assert "--ref main" not in log.read_text()


@pytest.mark.parametrize("remote_tag", [False, True])
def test_tag_for_different_code_is_never_moved(repository, remote_tag):
    root, _, log, git, run = repository
    git("tag", "v0.9.0b4")
    original = git("rev-parse", "v0.9.0b4").stdout
    if remote_tag:
        git("push", "origin", "refs/tags/v0.9.0b4")
        git("tag", "-d", "v0.9.0b4")  # Exercise remote-only tag verification.
    (root / "change.txt").write_text("changed code")
    git("add", ".")
    git("commit", "-m", "Different code, same version")
    git("push", "origin", "main")
    result = run()
    assert result.returncode == 1
    assert "different code" in result.stdout
    assert "workflow run" not in log.read_text()
    if remote_tag:
        assert original.strip() in git("ls-remote", "--tags", "origin").stdout
    else:
        assert git("rev-parse", "v0.9.0b4").stdout == original


def test_check_only_does_not_create_or_push_tag(repository):
    _, _, log, git, run = repository
    result = run("-CheckOnly")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git("tag", "--list").stdout == ""
    assert git("ls-remote", "--tags", "origin").stdout == ""
    assert "workflow run" not in log.read_text()
