#!/usr/bin/env python3
"""Hold the loop's guardrails. PreToolUse on Bash.

- `git init` without `-b main` is denied unless git already defaults to `main`.

guard.sh runs first and skips Python for payloads that cannot matter. This is a
guardrail, not a security boundary: it fails open, so a command it cannot read, or any
error, lets the call through. Written for Python 3.9.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import NamedTuple, Optional

import shellwords


class Decision(NamedTuple):
    verdict: str  # "deny", "ask" or "allow"
    reason: str


# --- the logic: plain data in, plain data out ---------------------------------------


def git_command(args: list[str]) -> list[str]:
    """A git call's subcommand and its arguments, past git's own options such as `-C dir`."""
    rest = list(args)
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] in ("-C", "-c", "--git-dir", "--work-tree") else rest[1:]
    return rest


def git_subcommand(args: list[str]) -> str:
    return (git_command(args) or [""])[0]


def starts_main(args: list[str]) -> bool:
    """Whether `git init` is given `main` as its first branch."""
    for i, arg in enumerate(args):
        if arg in ("-b", "--initial-branch") and args[i + 1 : i + 2] == ["main"]:
            return True
        if arg in ("-bmain", "--initial-branch=main"):
            return True
    return False


def decide(tool: str, tool_input: dict, default_branch: str = "") -> Optional[Decision]:
    """Say whether this tool call is denied, or (None) left to the usual permissions.

    `default_branch` is git's `init.defaultBranch`, read only for a `git init`.
    """
    if tool != "Bash":
        return None
    found = shellwords.programs(str(tool_input.get("command") or ""))
    if found is None:
        return None
    if any(
        ran.name == "git"
        and git_subcommand(ran.args) == "init"
        and not starts_main(git_command(ran.args)[1:])
        and default_branch != "main"
        for ran in found
    ):
        return Decision(
            "deny",
            "The default branch is main: run `git init -b main`, or set it once for every "
            "repository with `git config --global init.defaultBranch main`.",
        )
    return None


# --- the shell ----------------------------------------------------------------------


def git_default_branch(cwd: str) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", cwd, "config", "--get", "init.defaultBranch"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input") or {}
        default_branch = ""
        if tool == "Bash" and "init" in str(tool_input.get("command") or ""):
            default_branch = git_default_branch(str(payload.get("cwd") or os.getcwd()))
        decision = decide(tool, tool_input, default_branch)
        if decision is not None:
            output = {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision.verdict,
                "permissionDecisionReason": decision.reason,
            }
            print(json.dumps({"hookSpecificOutput": output}))
    except Exception as error:  # noqa: BLE001 - a guardrail fails open
        print("[philosophy] guard skipped: %s: %s" % (type(error).__name__, error), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
