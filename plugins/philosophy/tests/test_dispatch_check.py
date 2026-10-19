"""Tests for scripts/dispatch-check, run as a subprocess against a throwaway repository
with a bare remote, so it sees real branches and history.

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


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    )
    return done.stdout


def rev(cwd: Path, ref: str) -> str:
    return git(cwd, "rev-parse", ref).strip()


def dispatch_check(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "dispatch-check"), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A `main` with one commit, a remote, and a `thing/intent.md` ready to be specced.
    `start` is `before`; call `commit_on_main` to produce the `sha` a push would carry."""
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    git(work, "config", "user.email", "test@example.com")
    git(work, "config", "user.name", "Test")
    git(work, "remote", "add", "origin", str(remote))
    (work / "README.md").write_text("start\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "start")
    git(work, "push", "-q", "origin", "main")
    return work


def add_intent(repo: Path, slug: str) -> None:
    folder = repo / "intent" / slug
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text("# Intent: %s\n" % slug)


def commit_on_main(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", message)
    git(repo, "push", "-q", "origin", "main")
    return rev(repo, "main")


# --- malformed input, before any git call --------------------------------------------


@pytest.mark.parametrize("slug", ["Thing", "thing_one", "thing/one", "", "thing\n"])
def test_refuses_a_slug_that_is_not_plain(repo: Path, slug: str) -> None:
    before = rev(repo, "main")
    result = dispatch_check("spec", slug, "--before", before, "--sha", before, cwd=repo)
    assert result.returncode == 2 and "plain slug" in result.stderr


@pytest.mark.parametrize("value", ["short", "0" * 40, "g" * 40, "1" * 39, "1" * 41])
def test_refuses_a_sha_that_is_not_a_full_commit_sha(repo: Path, value: str) -> None:
    before = rev(repo, "main")
    result = dispatch_check("spec", "thing", "--before", value, "--sha", before, cwd=repo)
    assert result.returncode == 2 and "commit sha" in result.stderr
    result = dispatch_check("spec", "thing", "--before", before, "--sha", value, cwd=repo)
    assert result.returncode == 2 and "commit sha" in result.stderr


# --- ancestry and "on main" -----------------------------------------------------------


def test_refuses_a_sha_that_is_not_on_main(repo: Path) -> None:
    before = rev(repo, "main")
    git(repo, "checkout", "-q", "-b", "side")
    add_intent(repo, "thing")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "side commit")
    sha = rev(repo, "side")
    result = dispatch_check("spec", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert result.returncode == 2 and "not a commit on main" in result.stderr


def test_refuses_a_before_that_is_not_an_ancestor_of_sha(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "side")
    add_intent(repo, "thing")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "side commit")
    side = rev(repo, "side")
    git(repo, "checkout", "-q", "main")
    add_intent(repo, "other")
    sha = commit_on_main(repo, "add other")
    result = dispatch_check("spec", "thing", "--before", side, "--sha", sha, cwd=repo)
    assert result.returncode == 2 and "not an ancestor" in result.stderr


# --- the diff must touch the slug's trigger path --------------------------------------


def test_refuses_a_range_that_does_not_touch_the_slugs_intent(repo: Path) -> None:
    before = rev(repo, "main")
    add_intent(repo, "other")
    sha = commit_on_main(repo, "add other's intent")
    result = dispatch_check("spec", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert result.returncode == 2 and "touches no trigger path" in result.stderr


def test_build_play_looks_at_spec_and_plans_not_intent(repo: Path) -> None:
    before = rev(repo, "main")
    add_intent(repo, "thing")
    sha = commit_on_main(repo, "add thing's intent")
    result = dispatch_check("build", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert result.returncode == 2 and "touches no trigger path" in result.stderr


# --- spec: due, or not -----------------------------------------------------------------


def test_spec_is_due_for_an_unspecced_intent(repo: Path) -> None:
    before = rev(repo, "main")
    add_intent(repo, "thing")
    sha = commit_on_main(repo, "add thing's intent")
    result = dispatch_check("spec", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert (result.returncode, result.stdout) == (0, "due\n")


def test_spec_is_not_due_once_main_already_has_one(repo: Path) -> None:
    before = rev(repo, "main")
    add_intent(repo, "thing")
    sha = commit_on_main(repo, "add thing's intent")
    (repo / "intent" / "thing" / "spec.md").write_text("# Spec: thing\n")
    commit_on_main(repo, "add thing's spec")
    result = dispatch_check("spec", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert (result.returncode, result.stdout) == (1, "intent/thing/spec.md is already on main\n")


def test_spec_is_not_due_while_a_spec_branch_is_open(repo: Path) -> None:
    before = rev(repo, "main")
    add_intent(repo, "thing")
    sha = commit_on_main(repo, "add thing's intent")
    git(repo, "push", "-q", "origin", "main:refs/heads/spec/thing")
    result = dispatch_check("spec", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert (result.returncode, result.stdout) == (1, "spec/thing is already on the remote\n")


def test_a_branch_merely_ending_in_spec_slug_does_not_count(repo: Path) -> None:
    before = rev(repo, "main")
    add_intent(repo, "thing")
    sha = commit_on_main(repo, "add thing's intent")
    git(repo, "push", "-q", "origin", "main:refs/heads/x/spec/thing")
    result = dispatch_check("spec", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert (result.returncode, result.stdout) == (0, "due\n")


# --- build: no due-ness check here, that's next-change's job --------------------------


def test_build_passes_once_the_range_touches_the_slugs_spec(repo: Path) -> None:
    before = rev(repo, "main")
    folder = repo / "intent" / "thing"
    folder.mkdir(parents=True)
    (folder / "spec.md").write_text("# Spec: thing\n")
    sha = commit_on_main(repo, "add thing's spec")
    result = dispatch_check("build", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert (result.returncode, result.stdout) == (0, "due\n")


def test_build_passes_for_a_plan_file_too(repo: Path) -> None:
    before = rev(repo, "main")
    folder = repo / "intent" / "thing" / "plans"
    folder.mkdir(parents=True)
    (folder / "01-core.md").write_text("# Plan: core\n")
    sha = commit_on_main(repo, "add thing's plan")
    result = dispatch_check("build", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert (result.returncode, result.stdout) == (0, "due\n")


# --- a push of several commits, the intent's change in an earlier one -----------------


def test_passes_when_the_intents_change_is_in_an_earlier_commit(repo: Path) -> None:
    before = rev(repo, "main")
    add_intent(repo, "thing")
    commit_on_main(repo, "add thing's intent")
    (repo / "README.md").write_text("more\n")
    sha = commit_on_main(repo, "unrelated follow-up")
    result = dispatch_check("spec", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert (result.returncode, result.stdout) == (0, "due\n")


def test_without_a_local_main_falls_back_to_the_remote(repo: Path) -> None:
    before = rev(repo, "main")
    add_intent(repo, "thing")
    sha = commit_on_main(repo, "add thing's intent")
    git(repo, "checkout", "-q", "--detach", "HEAD")
    git(repo, "branch", "-D", "main")
    result = dispatch_check("spec", "thing", "--before", before, "--sha", sha, cwd=repo)
    assert (result.returncode, result.stdout) == (0, "due\n")
