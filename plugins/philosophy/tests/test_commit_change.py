"""Tests for scripts/commit-change: the pure functions, then the script as a subprocess
against a throwaway repository.

Set HOOK_PYTHON to run it under another interpreter.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)

# `commit-change` has no `.py` suffix, so give the import a loader (as test_plan_drift does).
_loader = SourceFileLoader("commit_change", str(ROOT / "scripts" / "commit-change"))
_spec = importlib.util.spec_from_file_location("commit_change", _loader.path, loader=_loader)
assert _spec is not None
cc = importlib.util.module_from_spec(_spec)
_loader.exec_module(cc)

PLAN = "intent/thing/plans/01-change.md"


# --- the pure functions ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("src/a.py", None),
        ("./src/a.py", None),
        ("/etc/passwd", "outside"),
        ("../x", "outside"),
        ("a/../../x", "outside"),
        ("src/a.pyc", "compiled"),
        ("src/__pycache__/a.py", "compiled"),
        ("build/out.txt", "ignored"),
    ],
)
def test_refused(path: str, reason: str | None) -> None:
    found = cc.refused(path, {"build/out.txt"})
    assert (found is None) if reason is None else (found is not None and reason in found)


def test_to_stage_puts_the_plan_first_and_drops_duplicates() -> None:
    assert cc.to_stage(["a.py", "./a.py", "b/c.py", PLAN], PLAN) == (PLAN, "a.py", "b/c.py")


# --- the script -----------------------------------------------------------------------


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )
    return done.stdout


def commit_change(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "commit-change"), *args],
        capture_output=True,
        text=True,
        cwd=repo,
        check=False,
    )


def write_plan(repo: Path, listed: list[str]) -> None:
    bullets = "\n".join("- `%s`" % p for p in listed)
    plan = repo / PLAN
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "# Plan: change\n\n## Files that change\n\n%s\n\n## Order of work\n\n1. R1: x\n" % bullets
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    git(work, "config", "user.email", "test@example.com")
    git(work, "config", "user.name", "Test")
    (work / ".gitignore").write_text("secret.txt\n")
    (work / "a.py").write_text("x = 1\n")
    (work / "gone.py").write_text("y = 1\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "start")
    return work


def committed(repo: Path, rev: str = "HEAD") -> list[str]:
    return git(repo, "show", "--name-only", "--format=", rev).split()


def test_commits_the_listed_files_and_the_plan_and_leaves_a_stray_alone(repo: Path) -> None:
    write_plan(repo, ["a.py", "new.py"])
    (repo / "a.py").write_text("x = 2\n")
    (repo / "new.py").write_text("z = 1\n")
    (repo / "stray.txt").write_text("not in the plan\n")
    result = commit_change(repo, PLAN, "-m", "build 01: change")
    assert result.returncode == 0, result.stderr
    assert sorted(committed(repo)) == sorted(["a.py", "new.py", PLAN])
    assert git(repo, "status", "--porcelain").strip() == "?? stray.txt"


def test_plan_only_commits_the_plan_alone(repo: Path) -> None:
    write_plan(repo, ["a.py"])
    (repo / "a.py").write_text("x = 2\n")
    result = commit_change(repo, PLAN, "-m", "plan: 01 change", "--plan-only")
    assert result.returncode == 0, result.stderr
    assert committed(repo) == [PLAN]
    assert git(repo, "status", "--porcelain").strip() == "M a.py"


def test_something_already_staged_stays_out_of_the_commit(repo: Path) -> None:
    write_plan(repo, ["a.py"])
    (repo / "a.py").write_text("x = 2\n")
    (repo / "other.py").write_text("o = 1\n")
    git(repo, "add", "other.py")
    assert commit_change(repo, PLAN, "-m", "build").returncode == 0
    assert sorted(committed(repo)) == sorted(["a.py", PLAN])


@pytest.mark.parametrize(
    "listed",
    ["src/a.pyc", "src/__pycache__/x.py", "secret.txt", "../x"],
)
def test_a_refused_path_exits_1_names_it_and_commits_nothing(repo: Path, listed: str) -> None:
    write_plan(repo, ["a.py", listed])
    (repo / "a.py").write_text("x = 2\n")
    before = git(repo, "rev-parse", "HEAD")
    if not listed.startswith(".."):
        target = repo / listed
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("junk\n")
    result = commit_change(repo, PLAN, "-m", "build")
    assert result.returncode == 1
    assert listed in result.stderr
    assert git(repo, "rev-parse", "HEAD") == before
    assert git(repo, "diff", "--cached", "--name-only").strip() == ""


def test_a_listed_directory_cannot_carry_bytecode_in(repo: Path) -> None:
    write_plan(repo, ["pkg/"])
    (repo / "pkg" / "__pycache__").mkdir(parents=True)
    (repo / "pkg" / "mod.py").write_text("x = 1\n")
    (repo / "pkg" / "__pycache__" / "mod.cpython-314.pyc").write_bytes(b"\0")
    result = commit_change(repo, PLAN, "-m", "change")
    assert result.returncode == 1 and "__pycache__" in result.stderr
    assert git(repo, "rev-list", "--count", "HEAD").strip() == "1"  # nothing committed
    assert git(repo, "diff", "--cached", "--name-only") == ""


def test_a_relative_plan_is_read_from_root_not_the_working_directory(
    repo: Path, tmp_path: Path
) -> None:
    write_plan(repo, ["a.py"])
    (repo / "a.py").write_text("x = 2\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = subprocess.run(
        [
            PYTHON,
            str(ROOT / "scripts" / "commit-change"),
            PLAN,
            "-m",
            "change",
            "--root",
            str(repo),
        ],
        capture_output=True,
        text=True,
        cwd=elsewhere,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert sorted(committed(repo)) == sorted([PLAN, "a.py"])


def test_a_listed_path_not_yet_created_is_skipped(repo: Path) -> None:
    write_plan(repo, ["a.py", "later.py"])
    (repo / "a.py").write_text("x = 2\n")
    result = commit_change(repo, PLAN, "-m", "build")
    assert result.returncode == 0, result.stderr
    assert sorted(committed(repo)) == sorted(["a.py", PLAN])


def test_a_listed_deletion_is_staged(repo: Path) -> None:
    write_plan(repo, ["gone.py"])
    (repo / "gone.py").unlink()
    result = commit_change(repo, PLAN, "-m", "build")
    assert result.returncode == 0, result.stderr
    assert "gone.py" in committed(repo)
    assert not (repo / "gone.py").exists()


def test_a_second_run_adds_a_commit_and_never_amends(repo: Path) -> None:
    write_plan(repo, ["a.py"])
    (repo / "a.py").write_text("x = 2\n")
    assert commit_change(repo, PLAN, "-m", "first").returncode == 0
    first = git(repo, "rev-parse", "HEAD").strip()
    (repo / "a.py").write_text("x = 3\n")
    assert commit_change(repo, PLAN, "-m", "second").returncode == 0
    assert git(repo, "rev-parse", "HEAD~1").strip() == first
    assert git(repo, "log", "-1", "--format=%s").strip() == "second"


def test_nothing_to_commit_exits_1(repo: Path) -> None:
    write_plan(repo, ["a.py"])
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "plan in")
    result = commit_change(repo, PLAN, "-m", "build")
    assert result.returncode == 1 and "nothing to commit" in result.stderr


def test_a_missing_plan_exits_2(repo: Path) -> None:
    result = commit_change(repo, "intent/none.md", "-m", "build")
    assert result.returncode == 2 and "does not exist" in result.stderr


def test_a_message_that_looks_like_an_option_is_only_a_message(repo: Path) -> None:
    write_plan(repo, ["a.py"])
    (repo / "a.py").write_text("x = 2\n")
    result = commit_change(repo, PLAN, "--message=--amend")
    assert result.returncode == 0, result.stderr
    assert git(repo, "log", "-1", "--format=%s").strip() == "--amend"
    assert git(repo, "rev-list", "--count", "HEAD").strip() == "2"
