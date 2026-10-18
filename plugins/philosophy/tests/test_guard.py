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
    decision = guard.decide("Bash", {"command": command}, default_branch)
    assert (decision is not None and decision.verdict == "deny") is denied


def test_edits_are_left_alone() -> None:
    assert guard.decide("Edit", {"file_path": "/repo/a.py"}) is None


def test_an_unreadable_command_is_left_alone() -> None:
    assert guard.decide("Bash", {"command": 'git init "unterminated'}) is None


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
    for command in ("uv run pytest", "backlog task edit 5 -s Done"):
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
