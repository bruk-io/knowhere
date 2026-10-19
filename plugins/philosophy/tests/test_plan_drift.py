"""Tests for scripts/plan-drift: the pure functions directly, the command as a
subprocess against a throwaway repository, in the style of test_branch_diff.py.

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

# `plan-drift` has no `.py` suffix, so a plain `import` cannot find it, and
# `spec_from_file_location` cannot guess a loader from the name alone: give it one.
_loader = SourceFileLoader("plan_drift", str(ROOT / "scripts" / "plan-drift"))
_spec = importlib.util.spec_from_file_location("plan_drift", _loader.path, loader=_loader)
assert _spec is not None
pd = importlib.util.module_from_spec(_spec)
_loader.exec_module(pd)


# --- the pure functions ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "want"),
    [
        ("build/thing/01", ("thing", "01")),
        ("build/loop-round-five/02", ("loop-round-five", "02")),
        ("main", None),
        ("build/thing", None),
        ("build/thing/1", None),
        ("build/thing/001", None),
        ("build//01", None),
        ("release/thing/01", None),
    ],
)
def test_build_branch(name: str, want: tuple[str, str] | None) -> None:
    assert pd.build_branch(name) == want


@pytest.mark.parametrize(
    ("path", "want"),
    [
        ("a.py", "a.py"),
        ("./a", "a"),
        ("a//b", "a/b"),
        ("x/../a", "a"),
        ("dir/a.py", "dir/a.py"),
    ],
)
def test_normalise(path: str, want: str) -> None:
    assert pd.normalise(path) == want


def test_drift_excludes_listed_and_the_plan_itself() -> None:
    changed = ["a.py", "intent/thing/plans/01-first.md", "b.py"]
    listed = ["a.py"]
    assert pd.drift(changed, listed, "intent/thing/plans/01-first.md") == ("b.py",)


def test_drift_normalises_before_comparing() -> None:
    changed = ["./a.py", "intent/thing/plans/01-first.md"]
    listed = ["a.py"]
    assert pd.drift(changed, listed, "intent/thing/plans/01-first.md") == ()


def test_drift_keeps_diff_order() -> None:
    changed = ["z.py", "a.py"]
    assert pd.drift(changed, [], "plan.md") == ("z.py", "a.py")


# --- the command, against a throwaway repository --------------------------------------


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def plan_drift(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "plan-drift"), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_plan(repo: Path, slug: str, number: str, paths: list[str]) -> None:
    folder = repo / "intent" / slug / "plans"
    folder.mkdir(parents=True, exist_ok=True)
    bullets = "\n".join("- `%s`" % path for path in paths)
    (folder / ("%s-first.md" % number)).write_text(
        "# Plan: first\n\n## Files that change\n\n%s\n\n"
        "## Order of work\n\n1. do it.\n\n## Risks\n\nnone.\n\n## Proof\n\nnone.\n" % bullets
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
    return work


def test_changing_only_listed_files_and_the_plan_exits_0(repo: Path) -> None:
    write_plan(repo, "thing", "01", ["a.py"])
    (repo / "a.py").write_text("x = 2\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "build 01: change a and add the plan")
    result = plan_drift("build/thing/01", cwd=repo)
    assert result.returncode == 0 and result.stdout == ""


def test_an_extra_file_exits_1_and_names_it(repo: Path) -> None:
    write_plan(repo, "thing", "01", ["a.py"])
    (repo / "a.py").write_text("x = 2\n")
    (repo / "b.py").write_text("y = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "build 01: change a, add b and the plan")
    result = plan_drift("build/thing/01", cwd=repo)
    assert result.returncode == 1
    assert result.stdout.splitlines() == ["b.py", pd.REASON]


def test_a_non_build_branch_name_exits_2(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "feature/thing")
    result = plan_drift("feature/thing", cwd=repo)
    assert result.returncode == 2
    assert result.stdout == ""


def test_a_missing_plan_exits_2(repo: Path) -> None:
    (repo / "a.py").write_text("x = 2\n")
    git(repo, "commit", "-q", "-am", "build 01: change a, no plan")
    result = plan_drift("build/thing/01", cwd=repo)
    assert result.returncode == 2
    assert result.stdout == ""


def test_several_matching_plans_exits_2(repo: Path) -> None:
    write_plan(repo, "thing", "01", ["a.py"])
    folder = repo / "intent" / "thing" / "plans"
    (folder / "01-second.md").write_text("# Plan: second\n\n## Files that change\n\n- `a.py`\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "build 01: two plans")
    result = plan_drift("build/thing/01", cwd=repo)
    assert result.returncode == 2
    assert result.stdout == ""


def test_falls_back_to_origin_main_without_a_local_main(repo: Path, tmp_path: Path) -> None:
    write_plan(repo, "thing", "01", ["a.py"])
    (repo / "a.py").write_text("x = 2\n")
    (repo / "b.py").write_text("y = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "build 01: change a, add b and the plan")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")
    git(repo, "branch", "-D", "main")
    result = plan_drift("build/thing/01", cwd=repo)
    assert result.returncode == 1
    assert result.stdout.splitlines() == ["b.py", pd.REASON]


def test_a_deleted_listed_file_is_not_drift(repo: Path) -> None:
    write_plan(repo, "thing", "01", ["a.py"])
    git(repo, "rm", "-q", "a.py")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "build 01: remove a and add the plan")
    result = plan_drift("build/thing/01", cwd=repo)
    assert result.returncode == 0 and result.stdout == ""
