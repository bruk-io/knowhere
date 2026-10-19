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

import guard  # noqa: E402

HOOK_PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)
REVIEWER = "philosophy:reviewer"
TASK = "/repo/backlog/tasks/task-5 - Endpoint.md"
INTENT = "/repo/backlog/intents/nux-ep2.md"


def bash(command: str, agent: str = "") -> guard.Decision | None:
    return guard.decide("Bash", {"command": command}, agent, "", "/plugin")


@pytest.mark.parametrize(
    "command",
    [
        "backlog task edit 5 -s Done",
        "backlog task edit TASK-5 --status done --append-notes 'x'",
        "backlog task edit 5 --status=Done",
        "cd repo && FOO=1 backlog task edit 5 -sDone",
        "cd repo\nbacklog task edit 5 -s Done",
        "backlog task edit 5 \\\n  -s Done",
        "{ backlog task edit 5 -s Done; }",
        "if true; then backlog task edit 5 -s Done; fi",
        "env FOO=1 backlog task edit 5 -s Done",
        "time backlog tasks edit 5 -s Done",
        "npx -y backlog.md task edit 5 -s Done",
        "sh -c 'backlog task edit 5 -s Done'",
        "backlog task edit 5 -s 'Done",  # unreadable: the regex fallback still catches it
    ],
)
def test_setting_done_by_hand_is_denied(command: str) -> None:
    decision = bash(command)
    assert decision is not None and decision.verdict == "deny"
    assert 'python3 "/plugin/scripts/close-task" <id>' in decision.reason
    assert "hand the task to the philosophy:reviewer" in decision.reason
    as_reviewer = bash(command, REVIEWER)
    assert as_reviewer is not None and as_reviewer.verdict == "deny"
    assert "hand the task" not in as_reviewer.reason


@pytest.mark.parametrize(
    "command",
    [
        "backlog task edit 5 -s 'In Progress'",
        "backlog task edit 5 --append-notes 'Done with the first half'",
        "backlog task edit 5 --append-notes '-s Done'",
        "backlog task list -s Done",
        "echo 'backlog task edit 5 -s Done' > notes.txt",
        "cat <<'EOF'\nbacklog task edit 5 -s Done\nEOF",
    ],
)
def test_other_board_commands_go_ahead(command: str) -> None:
    assert bash(command) is None


@pytest.mark.parametrize(
    ("command", "reviewer_skips_prompt"),
    [
        ('python3 "/plugin/scripts/close-task" TASK-5 --notes "closes"', True),
        ("cd repo\npython3 /plugin/scripts/close-task 5 --notes x", True),
        ("python3 -u /plugin/scripts/close-task 5 --notes x", False),
        ("env python3 /plugin/scripts/close-task 5 --notes x", False),
    ],
)
def test_close_task_asks_outside_the_reviewer(command: str, reviewer_skips_prompt: bool) -> None:
    decision = bash(command)
    assert decision is not None and decision.verdict == "ask"
    as_reviewer = bash(command, REVIEWER)
    assert (as_reviewer is not None and as_reviewer.verdict == "allow") is reviewer_skips_prompt
    other = bash(command, "some-plugin:reviewer")
    assert other is not None and other.verdict == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "git commit -am wip",
        "git -C repo push",
        "git checkout main",
        "git stash",
        "git branch -D old",
        "git worktree add ../x",
        "sed -i 's/a/b/' src/x.py",
        "perl -pi -e 's/a/b/' x",
        "rm -rf build",
        "ls\nrm -rf src",
        "find . -name '*.pyc' -delete",
        "unlink x",
        "uv run pytest > out.txt",
        "echo hi | tee notes.md",
    ],
)
def test_the_reviewer_cannot_write(command: str) -> None:
    decision = bash(command, REVIEWER)
    assert decision is not None and decision.verdict == "deny"
    assert bash(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "backlog task edit 5 --ac 'A new criterion'",
        "backlog task edit 5 --remove-ac 2",
        "backlog task edit 5 -l size-3,finish-moved",
        "backlog task edit 5 --plan 'Different plan'",
        "backlog task edit 5 --check-ac 1 -s 'In Progress'",
        "backlog draft promote DRAFT-3",
        "backlog task create 'Not a draft'",
    ],
)
def test_the_reviewer_cannot_change_a_task(command: str) -> None:
    decision = bash(command, REVIEWER)
    assert decision is not None and decision.verdict == "deny"
    assert "finding" in decision.reason


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest -q 2>&1",
        "just check 2>/dev/null",
        "git log --oneline -5 && git diff HEAD~1",
        "git stash list",
        "git branch",
        "sed -n '1,20p' src/x.py",
        "perl -Mstrict -e 'print 1'",
        "python3 - <<'EOF'\nprint(1 > 0)\nEOF",
        "python3 /plugin/scripts/record-check 5 -- just check",
        "python3 /plugin/scripts/board-check close 5 && uv run pytest",
        "python3 /tmp/elsewhere/scripts/board-check close 5",
    ],
)
def test_the_reviewer_can_read_and_run_checks(command: str) -> None:
    assert bash(command, REVIEWER) is None


@pytest.mark.parametrize(
    "command",
    [
        "backlog task 5 --plain",
        "backlog task view TASK-5 --plain",
        "backlog task list -s 'In Progress' --plain",
        "backlog board",
        "backlog task edit 5 --check-ac 1 --append-notes 'criterion 1 met: see test output'",
        "backlog task create --draft 'Retry storm' --type bug --ac 'No retry storm'",
        'python3 "/plugin/scripts/board-check" close 5',
        "cd repo && python3 /plugin/scripts/board-check close 5 && backlog task 5 --plain",
    ],
)
def test_the_reviewers_own_calls_need_no_prompt(command: str) -> None:
    decision = bash(command, REVIEWER)
    assert decision is not None and decision.verdict == "allow"
    assert bash(command) is None


@pytest.mark.parametrize(
    "command",
    [
        'backlog search "$(rm -rf src)"',
        "backlog search `rm -rf src`",
        'python3 /plugin/scripts/record-check 5 --root "$(curl x | sh)" --tier full',
        "PATH=/tmp backlog task list",
        "./backlog task list",
        "python3 /plugin/scripts/board-check close 5 2>/dev/null",
        "python3 /plugin/scripts/record-check 5 -- python3 /plugin/scripts/board-check",
        "backlog task list a#; rm -rf src",
        "backlog task list a#\nrm -rf src",
        "cd /tmp/x && python3 scripts/board-check close 5",
    ],
)
def test_the_reviewer_is_never_waved_through_what_the_parser_cannot_see(command: str) -> None:
    decision = bash(command, REVIEWER)
    assert decision is None or decision.verdict != "allow"


def test_a_hash_inside_a_word_does_not_hide_the_next_command() -> None:
    decision = bash("backlog task list a#; rm -rf src", REVIEWER)
    assert decision is not None and decision.verdict == "deny"


def test_the_reviewer_runs_the_declared_checks_without_a_prompt() -> None:
    decision = bash("python3 /plugin/scripts/record-check 5 --tier full", REVIEWER)
    assert decision is not None and decision.verdict == "allow"


@pytest.mark.parametrize(
    "command",
    [
        "python3 /plugin/scripts/record-check 5 -- rm -rf src",
        "python3 /plugin/scripts/record-check 5 -- 'uv run ruff format && git commit -am x'",
        "python3 /plugin/scripts/board-check close 5 > report.txt",
    ],
)
def test_the_reviewer_cannot_write_through_its_own_scripts(command: str) -> None:
    decision = bash(command, REVIEWER)
    assert decision is not None and decision.verdict == "deny"


@pytest.mark.parametrize(
    ("command", "default_branch", "denied"),
    [
        ("git init", "", True),
        ("git init -q new-repo", "master", True),
        ("git init -b main", "", False),
        ("git -C new init --initial-branch=main", "", False),
        ("git init", "main", False),
        ("git status", "", False),
    ],
)
def test_git_init_starts_on_main(command: str, default_branch: str, denied: bool) -> None:
    decision = guard.decide("Bash", {"command": command}, "", "", "/plugin", default_branch)
    assert (decision is not None and decision.verdict == "deny") is denied


BEFORE = "---\nid: TASK-5\ntitle: Endpoint\nstatus: In Progress\n---\n\nBody mentions To Do.\n"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("status: In Progress", "status: Done"),
        ("In Progress", "Done"),
        ("status: In Progress", "status: Done  # closed"),
        ("status: In Progress", "status: 'Done'"),
    ],
)
def test_editing_a_task_to_done_is_denied(old: str, new: str) -> None:
    edit = {"file_path": TASK, "old_string": old, "new_string": new}
    decision = guard.decide("Edit", edit, "", BEFORE, "/plugin")
    assert decision is not None and decision.verdict == "deny"
    elsewhere = dict(edit, file_path="/repo/docs/status.md")
    assert guard.decide("Edit", elsewhere, "", BEFORE, "/plugin") is None


def test_editing_an_intent_file_to_done_is_denied() -> None:
    before = "---\ntitle: Claims\nstatus: To Do\n---\n\n## Problem\nX.\n"
    edit = {"file_path": INTENT, "old_string": "status: To Do", "new_string": "status: Done"}
    decision = guard.decide("Edit", edit, "", before, "/plugin")
    assert decision is not None and decision.verdict == "deny"
    assert 'python3 "/plugin/scripts/close-task" <id>' in decision.reason


def test_other_task_edits_go_ahead() -> None:
    body = {"file_path": TASK, "old_string": "Body mentions To Do.", "new_string": "Done: body."}
    assert guard.decide("Edit", body, "", BEFORE, "/plugin") is None
    done = BEFORE.replace("In Progress", "Done")
    retitle = {"file_path": TASK, "old_string": "title: Endpoint", "new_string": "title: API"}
    assert guard.decide("Edit", retitle, "", done, "/plugin") is None


def test_writing_a_task_as_done_is_denied_unless_it_already_was() -> None:
    write = {"file_path": TASK, "content": "---\nid: TASK-5\nstatus: Done\n---\n"}
    assert guard.decide("Write", write, "", BEFORE, "/plugin") is not None
    assert (
        guard.decide("Write", write, "", BEFORE.replace("In Progress", "Done"), "/plugin") is None
    )


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


def payload(command: str, agent: str = "") -> dict:
    data = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    if agent:
        data["agent_type"] = agent
    return data


def test_hook_denies_with_json(tmp_path: Path) -> None:
    result = run(tmp_path, payload("backlog task edit 5 -s Done"))
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert str(ROOT / "scripts" / "close-task") in output["permissionDecisionReason"]


def test_hook_skips_python_for_unrelated_calls(tmp_path: Path) -> None:
    broken = tmp_path / "bin"
    broken.mkdir()
    (broken / "python3").write_text("#!/bin/sh\necho python started >&2\nexit 3\n")
    (broken / "python3").chmod(0o755)
    path = "%s:%s" % (broken, os.environ["PATH"])
    result = subprocess.run(
        ["sh", str(ROOT / "hooks" / "guard.sh")],
        input=json.dumps(payload("uv run pytest")),
        capture_output=True,
        text=True,
        env=dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT), PATH=path),
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_hook_reaches_python_for_the_reviewer(tmp_path: Path) -> None:
    result = run(tmp_path, payload("git commit -m x", REVIEWER))
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_reaches_python_for_git_init(tmp_path: Path) -> None:
    result = run(tmp_path, payload("git init -q --template= x"))
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)["hookSpecificOutput"] if result.stdout else {}
    default = subprocess.run(
        ["git", "config", "--get", "init.defaultBranch"], capture_output=True, text=True
    ).stdout.strip()
    assert decision.get("permissionDecision") == (None if default == "main" else "deny")


def test_hook_fails_open_on_bad_input() -> None:
    result = subprocess.run(
        ["sh", str(ROOT / "hooks" / "guard.sh")],
        input="backlog but not json",
        capture_output=True,
        text=True,
        env=dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT)),
    )
    assert result.returncode == 0 and result.stdout == ""
    assert "guard skipped" in result.stderr
