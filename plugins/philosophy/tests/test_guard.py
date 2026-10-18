"""Tests for hooks/guard.py and the guard.sh shell in front of it."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))

import artefact as a  # noqa: E402
import guard  # noqa: E402

HOOK_PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)


@pytest.mark.parametrize(
    ("command", "default_branch", "denied"),
    [
        ("git init", "", True),
        ("git init -q new-repo", "master", True),
        ("git init -b main", "", False),
        ("git -C new init --initial-branch=main", "", False),
        ("git init", "main", False),
        ("git status", "", False),
        ("cd x && git init", "", True),
    ],
)
def test_git_init_starts_on_main(command: str, default_branch: str, denied: bool) -> None:
    decision = guard.decide_bash(command, default_branch)
    assert (decision is not None and decision.verdict == "deny") is denied


def test_an_unreadable_command_is_left_alone() -> None:
    assert guard.decide_bash('git init "unterminated', "") is None


# --- plan sync and the repro guard ----------------------------------------------------

BUILD = guard.Build("thing", "01")
PLAN = a.parse(
    """# Plan: the core

Spec: [spec.md](../spec.md), change 01. Delivers R1.

## Files that change

- `intent/thing/plans/01-core.md`
- `src/core.py`
- `./tests/test_core.py`
- `.github/workflows/ci.yml`

## Order of work

1. Write the repro, then fix it (R1).

## Risks

- None.

## Proof

- Repro: `tests/test_core.py` fails before the fix.
- `make test` passes.
""",
    "intent/thing/plans/01-core.md",
)
NONE: frozenset[str] = frozenset()
ONE_PLAN = ("intent/thing/plans/01-core.md",)


def edit(path, plan=PLAN, plans=ONE_PLAN, plan_committed=True, repros=NONE, build=BUILD):
    """Ask the guard about an edit, by default with one committed plan."""
    return guard.decide_edit(path, build, plans if plan else (), plan, plan_committed, repros)


def verdict(decision: guard.Decision | None) -> str:
    return decision.verdict if decision else "none"


def test_build_branch_is_read_from_its_name() -> None:
    assert guard.build_of("build/thing/01") == BUILD
    assert guard.build_of("main") is None
    assert guard.build_of("build/thing/1") is None


def test_nothing_is_held_off_a_build_branch() -> None:
    assert edit("src/other.py", build=None) is None


def test_before_the_plan_only_the_plan_can_be_written() -> None:
    denied = edit("src/core.py", plan=None)
    assert verdict(denied) == "deny" and "intent/thing/plans/01-<change>.md" in denied.reason
    assert edit("intent/thing/plans/01-core.md", plan=None) is None


def test_an_uncommitted_plan_does_not_unlock_code() -> None:
    denied = edit("src/core.py", plan_committed=False)
    assert verdict(denied) == "deny" and "first commit" in denied.reason
    assert edit("intent/thing/plans/01-core.md", plan_committed=False) is None


def test_only_the_plan_itself_counts_as_the_plan() -> None:
    for path in ("intent/thing/plans/x/01-anything.py", "intent/thing/plans/01-core.py"):
        assert verdict(edit(path, plan=None)) == "deny", path


def test_two_plans_for_one_change_is_an_error() -> None:
    plans = ONE_PLAN + ("intent/thing/plans/01-again.md",)
    assert verdict(edit("src/core.py", plans=plans)) == "deny"


def test_another_changes_plan_is_held_like_any_file() -> None:
    assert verdict(edit("intent/thing/plans/02-next.md")) == "deny"


def test_listed_files_go_ahead() -> None:
    for path in ("src/core.py", "tests/test_core.py", ".github/workflows/ci.yml"):
        assert edit(path) is None, path


def test_an_unlisted_file_is_denied_with_the_fix() -> None:
    denied = edit("src/other.py")
    assert verdict(denied) == "deny"
    assert "Files that change" in denied.reason and "same commit" in denied.reason


def test_a_file_outside_the_repository_is_left_alone() -> None:
    assert edit(None) is None


def test_the_repro_is_read_from_the_proof() -> None:
    assert guard.repro_tests(PLAN) == frozenset({"tests/test_core.py"})


def test_a_repro_bullet_that_wraps_still_names_its_test() -> None:
    wrapped = a.parse(
        "# Plan: x\n\n## Proof\n\n- Repro: the test that fails first,\n  `tests/test_wrapped.py`.\n",
        "plan.md",
    )
    assert guard.repro_tests(wrapped) == frozenset({"tests/test_wrapped.py"})


def test_a_committed_repro_is_frozen() -> None:
    committed = frozenset({"tests/test_core.py"})
    denied = edit("tests/test_core.py", repros=committed)
    assert verdict(denied) == "deny" and "Fix the code" in denied.reason


# --- the hook as Claude Code runs it ---------------------------------------------------


def run(tmp_path: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    """Run guard.sh with `python3` on PATH meaning HOOK_PYTHON."""
    shims = tmp_path / "shims"
    shims.mkdir(exist_ok=True)
    (shims / "python3").write_text('#!/bin/sh\nexec "%s" "$@"\n' % HOOK_PYTHON)
    (shims / "python3").chmod(0o755)
    environment = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT))
    environment["PATH"] = "%s:%s" % (shims, os.environ["PATH"])
    return subprocess.run(
        ["sh", str(ROOT / "hooks" / "guard.sh")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=environment,
        timeout=20,
    )


def payload(command: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def test_hook_denies_with_json(tmp_path: Path) -> None:
    result = run(tmp_path, payload("git -c init.defaultBranch=master init -q x"))
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)["hookSpecificOutput"] if result.stdout else {}
    default = subprocess.run(
        ["git", "config", "--get", "init.defaultBranch"], capture_output=True, text=True
    ).stdout.strip()
    if default == "main":
        assert output == {}
    else:
        assert output["hookEventName"] == "PreToolUse"
        assert output["permissionDecision"] == "deny"
        assert "git init -b main" in output["permissionDecisionReason"]


def test_hook_skips_python_for_unrelated_calls(tmp_path: Path) -> None:
    broken = tmp_path / "bin"
    broken.mkdir()
    (broken / "python3").write_text("#!/bin/sh\necho python started >&2\nexit 3\n")
    (broken / "python3").chmod(0o755)
    path = "%s:%s" % (broken, os.environ["PATH"])
    for command in ("uv run pytest", "git status"):
        result = subprocess.run(
            ["sh", str(ROOT / "hooks" / "guard.sh")],
            input=json.dumps(payload(command)),
            capture_output=True,
            text=True,
            env=dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT), PATH=path),
        )
        assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_hook_fails_open_on_bad_input() -> None:
    result = subprocess.run(
        ["sh", str(ROOT / "hooks" / "guard.sh")],
        input="git init but not json",
        capture_output=True,
        text=True,
        env=dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT)),
    )
    assert result.returncode == 0 and result.stdout == ""
    assert "guard skipped" in result.stderr


# --- plan sync as the hook runs it, in a throwaway repository on a build branch -------


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def build_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("x\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "start")
    git(repo, "checkout", "-q", "-b", "build/thing/01")
    return repo


def edit_payload(repo: Path, file: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(repo / file), "old_string": "a", "new_string": "b"},
        "cwd": str(repo),
    }


def hook_verdict(tmp_path: Path, payload: dict) -> str:
    result = run(tmp_path, payload)
    assert result.returncode == 0, result.stderr
    return (
        json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
        if result.stdout
        else "none"
    )


def write_plan(repo: Path) -> None:
    plans = repo / "intent" / "thing" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    (plans / "01-core.md").write_text(
        "# Plan: x\n\n## Files that change\n\n- `src/core.py`\n- `tests/test_core.py`\n\n"
        "## Proof\n\n- Repro: `tests/test_core.py` fails first.\n"
    )


def test_hook_holds_code_until_the_plan_exists(tmp_path: Path, build_repo: Path) -> None:
    assert hook_verdict(tmp_path, edit_payload(build_repo, "src/core.py")) == "deny"
    assert (
        hook_verdict(tmp_path, edit_payload(build_repo, "intent/thing/plans/01-core.md")) == "none"
    )


def test_hook_holds_edits_to_the_plan(tmp_path: Path, build_repo: Path) -> None:
    write_plan(build_repo)
    assert hook_verdict(tmp_path, edit_payload(build_repo, "src/core.py")) == "deny"
    git(build_repo, "add", ".")
    git(build_repo, "commit", "-q", "-m", "plan: 01 x")
    assert hook_verdict(tmp_path, edit_payload(build_repo, "src/core.py")) == "none"
    assert hook_verdict(tmp_path, edit_payload(build_repo, "src/other.py")) == "deny"


def test_hook_freezes_the_repro_once_committed(tmp_path: Path, build_repo: Path) -> None:
    write_plan(build_repo)
    git(build_repo, "add", ".")
    git(build_repo, "commit", "-q", "-m", "plan: 01 x")
    test = build_repo / "tests" / "test_core.py"
    test.parent.mkdir()
    test.write_text("def test_x(): assert False\n")
    assert hook_verdict(tmp_path, edit_payload(build_repo, "tests/test_core.py")) == "none"
    git(build_repo, "add", ".")
    git(build_repo, "commit", "-q", "-m", "repro")
    assert hook_verdict(tmp_path, edit_payload(build_repo, "tests/test_core.py")) == "deny"


def test_hook_keeps_the_repro_frozen_when_the_plan_drops_it(
    tmp_path: Path, build_repo: Path
) -> None:
    write_plan(build_repo)
    test = build_repo / "tests" / "test_core.py"
    test.parent.mkdir()
    test.write_text("def test_x(): assert False\n")
    git(build_repo, "add", ".")
    git(build_repo, "commit", "-q", "-m", "plan and repro")
    plan = build_repo / "intent" / "thing" / "plans" / "01-core.md"
    plan.write_text(plan.read_text().replace("- Repro: `tests/test_core.py` fails first.\n", ""))
    assert hook_verdict(tmp_path, edit_payload(build_repo, "tests/test_core.py")) == "deny"


def test_hook_holds_notebook_edits_too(tmp_path: Path, build_repo: Path) -> None:
    payload = edit_payload(build_repo, "x")
    payload["tool_name"] = "NotebookEdit"
    payload["tool_input"] = {"notebook_path": str(build_repo / "analysis.ipynb")}
    assert hook_verdict(tmp_path, payload) == "deny"


def test_hook_resolves_a_relative_path_against_the_payload_cwd(
    tmp_path: Path, build_repo: Path
) -> None:
    payload = edit_payload(build_repo, "x")
    payload["tool_input"]["file_path"] = "src/core.py"
    assert hook_verdict(tmp_path, payload) == "deny"


def test_hook_leaves_main_alone(tmp_path: Path, build_repo: Path) -> None:
    git(build_repo, "checkout", "-q", "main")
    assert hook_verdict(tmp_path, edit_payload(build_repo, "src/core.py")) == "none"


def test_hook_leaves_files_outside_the_repository_alone(tmp_path: Path, build_repo: Path) -> None:
    payload = edit_payload(build_repo, "x")
    payload["tool_input"]["file_path"] = str(tmp_path / "elsewhere" / "notes.md")
    assert hook_verdict(tmp_path, payload) == "none"
