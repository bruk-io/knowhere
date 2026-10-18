#!/usr/bin/env python3
"""Hold the loop's guardrails. PreToolUse on Bash, Edit and Write.

- `git init` without `-b main` is denied unless git already defaults to `main`.
- On a `build/<slug>/NN` branch, an Edit or Write is held to the change's plan,
  `intent/<slug>/plans/NN-*.md`. Until the plan is committed, only the plan can be
  written. After that, a file the plan's Files that change doesn't list is denied, and
  so is a repro test the plan's Proof names, once it is committed.

guard.sh runs first and skips Python for payloads that cannot matter. This is a
guardrail, not a security boundary: it fails open, so a command it cannot read, a shell
command that writes a file, or any error, lets the call through. Written for Python 3.9.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Optional

import shellwords

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import artefact as a  # noqa: E402

BUILD_BRANCH = re.compile(r"^build/([^/]+)/(\d{2})$")
REPRO = re.compile(r"^[-*]\s+Repro:", re.I)
BACKTICKED = re.compile(r"`([^`]+)`")


class Decision(NamedTuple):
    verdict: str  # "deny", "ask" or "allow"
    reason: str


class Build(NamedTuple):
    """The change a build branch is for."""

    slug: str
    number: str


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


def decide_bash(command: str, default_branch: str) -> Optional[Decision]:
    found = shellwords.programs(command)
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


def build_of(branch: str) -> Optional[Build]:
    found = BUILD_BRANCH.match(branch)
    return Build(found.group(1), found.group(2)) if found else None


def plan_dir(build: Build) -> str:
    return "intent/%s/plans/" % build.slug


def is_own_plan(path: str, build: Build) -> bool:
    """Whether a path is this change's plan: directly in the plans folder, named
    `NN-<change>.md`."""
    found = Path(path)
    return (
        found.parent.as_posix() + "/" == plan_dir(build)
        and found.name.startswith(build.number + "-")
        and found.suffix == ".md"
    )


def repro_tests(plan: a.Doc) -> frozenset[str]:
    """The tests a plan's Proof names on a line starting `Repro:`."""
    proof = a.section(plan, "Proof") or ""
    return frozenset(
        path.strip().removeprefix("./")
        for line in proof.splitlines()
        if REPRO.match(line.strip())
        for path in BACKTICKED.findall(line)
    )


def decide_edit(
    path: Optional[str],
    build: Optional[Build],
    plans: tuple[str, ...],
    plan: Optional[a.Doc],
    plan_committed: bool,
    committed: frozenset[str],
) -> Optional[Decision]:
    """Hold an Edit or Write on a build branch to the change's plan.

    `path` is the file's path in the repository, or None when it is outside it.
    `plans` are the paths of this change's plans; `plan` is the one plan, read from the
    working tree so an edit can add a file to it, or None if there is none.
    `plan_committed` says whether that plan is in HEAD. `committed` is the plan's repro
    tests that are already in HEAD.
    """
    if build is None or path is None or is_own_plan(path, build):
        return None
    if len(plans) > 1:
        return Decision(
            "deny",
            "Change %s of %s has more than one plan (%s). Keep one, then build from it."
            % (build.number, build.slug, ", ".join(plans)),
        )
    if plan is not None and not plan_committed:
        return Decision(
            "deny",
            "Commit the plan, %s, alone as the branch's first commit before changing "
            "anything else: the plan comes first in the history, not only on disk." % plan.path,
        )
    if plan is None:
        return Decision(
            "deny",
            "This is the build branch for change %s of %s, and its plan comes first: write "
            "%s%s-<change>.md from the plan template and commit it alone, then build from it."
            % (build.number, build.slug, plan_dir(build), build.number),
        )
    if path in committed:
        return Decision(
            "deny",
            "%s is the committed repro test for this change. Fix the code, not the test: "
            "a fix that edits its own repro proves nothing. If the test itself is wrong, "
            "stop and say so in the PR." % path,
        )
    listed = frozenset(p.removeprefix("./") for p in a.listed_paths(plan))
    if path not in listed:
        return Decision(
            "deny",
            "%s is not in the plan's Files that change (%s). If this change needs it, add "
            "it there, one backticked path per bullet, in the same commit as the edit, and "
            "say why in the PR. A bigger drift is a reason to stop, not to push on."
            % (path, plan.path),
        )
    return None


# --- the shell ----------------------------------------------------------------------


def git(cwd: str, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def git_default_branch(cwd: str) -> str:
    return git(cwd, "config", "--get", "init.defaultBranch") or ""


def existing_dir(path: Path) -> Path:
    while not path.is_dir() and path != path.parent:
        path = path.parent
    return path


def edit_decision(file_path: str) -> Optional[Decision]:
    """Read what `decide_edit` needs for one file, and decide."""
    target = Path(file_path)
    found = git(
        str(existing_dir(target.parent)), "rev-parse", "--show-toplevel", "--abbrev-ref", "HEAD"
    )
    if found is None or "\n" not in found:
        return None
    root, branch = found.split("\n", 1)
    build = build_of(branch.strip())
    if build is None:
        return None
    try:
        path: Optional[str] = target.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        path = None
    found = sorted(Path(root, plan_dir(build)).glob("%s-*.md" % build.number))
    plans = tuple(p.relative_to(root).as_posix() for p in found)
    plan = a.read(found[0]) if len(found) == 1 else None
    plan_committed = bool(plans) and git(root, "cat-file", "-e", "HEAD:%s" % plans[0]) is not None
    committed = frozenset(
        test
        for test in (repro_tests(plan) if plan else frozenset())
        if git(root, "cat-file", "-e", "HEAD:%s" % test) is not None
    )
    return decide_edit(path, build, plans, plan, plan_committed, committed)


def decide(tool: str, tool_input: dict, cwd: str) -> Optional[Decision]:
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        default = git_default_branch(cwd) if "init" in command else ""
        return decide_bash(command, default)
    if tool in ("Edit", "Write") and tool_input.get("file_path"):
        return edit_decision(str(tool_input["file_path"]))
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        decision = decide(
            str(payload.get("tool_name") or ""),
            payload.get("tool_input") or {},
            str(payload.get("cwd") or os.getcwd()),
        )
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
