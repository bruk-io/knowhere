"""Tests for scripts/branch-diff, run as a subprocess against a throwaway repository.

Set HOOK_PYTHON to run it under another interpreter.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def branch_diff(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "branch-diff"), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    git(work, "config", "user.email", "test@example.com")
    git(work, "config", "user.name", "Test")
    (work / "a.py").write_text("x = 1\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "start")
    git(work, "checkout", "-q", "-b", "build/thing/01")
    (work / "a.py").write_text("x = 2\n")
    git(work, "commit", "-q", "-am", "build 01: change x")
    return work


def test_prints_the_branchs_commits_and_diff(repo: Path) -> None:
    result = branch_diff("build/thing/01", cwd=repo)
    assert result.returncode == 0, result.stdout
    assert "build 01: change x" in result.stdout
    assert "-x = 1\n+x = 2" in result.stdout


def test_falls_back_to_origin_main_without_a_local_main(repo: Path, tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")
    git(repo, "branch", "-D", "main")
    result = branch_diff("build/thing/01", cwd=repo)
    assert result.returncode == 0 and "$ git diff origin/main...build/thing/01" in result.stdout


@pytest.mark.parametrize(
    "name",
    ["-x", "--output=leak", "x --output=leak", "main..x", "x;rm", "", "a b"],
)
def test_refuses_a_name_that_is_not_a_plain_branch(repo: Path, name: str) -> None:
    result = branch_diff(name, cwd=repo)
    assert result.returncode == 2
    assert not (repo / "leak").exists()


def test_a_branch_git_cannot_find_exits_2(repo: Path) -> None:
    result = branch_diff("build/thing/99", cwd=repo)
    assert result.returncode == 2 and result.stdout.startswith("branch-diff: git failed")
