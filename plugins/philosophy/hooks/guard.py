#!/usr/bin/env python3
"""Hold the close to the work loop. PreToolUse on Bash, Edit and Write.

- Setting a task to Done by hand, with `backlog task edit ... -s Done` or an edit that
  leaves a task file at `status: Done`, is denied. The reason names close-task, which
  checks the criteria and the children before it changes anything.
- Running close-task anywhere but in the reviewer agent asks the person first, because
  whether a task closes is decided by someone who did not do the work.
- In the reviewer agent, the usual ways a shell command changes files or git history
  are denied, and so is any `backlog` command beyond reading the board, ticking
  criteria, appending notes and filing drafts. The reviewer's own calls (this plugin's
  scripts, the repository's declared checks through `record-check --tier`, and those
  `backlog` commands) are allowed without a prompt, read strictly so that anything the
  parser can't see into is left to the usual permissions.
- `git init` without `-b main` is denied unless git already defaults to `main`.

guard.sh runs first and skips Python for payloads that cannot matter. This is a
guardrail for the work loop, not a security boundary: it fails open, so a command it
cannot read, or any error, lets the call through. Written for Python 3.9.
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

REVIEWER = "philosophy:reviewer"
WRITERS = frozenset(
    {"rm", "mv", "cp", "tee", "touch", "mkdir", "rmdir", "chmod", "truncate", "dd", "patch"}
    | {"ln", "unlink", "install"}
)
GIT_WRITES = frozenset(
    {"add", "am", "apply", "checkout", "cherry-pick", "clean", "commit", "init", "merge", "mv"}
    | {"pull", "push", "rebase", "reset", "restore", "revert", "rm", "switch"}
)
REDIRECTS = frozenset({">", ">>", ">|", "&>", "&>>"})
TASK_FILE = re.compile(r"/backlog/(?:tasks|drafts|completed|intents)/[^/]+\.md$")
STATUS = re.compile(r"\A\ufeff?---\n.*?^status:[ \t]*(.*?)[ \t]*$", re.M | re.S)
DONE_COMMAND = re.compile(r"\bbacklog\s+tasks?\s+edit\b.*(?:-s|--status)[\s=]+['\"]?done\b", re.I)
# `backlog task edit` options that take a value, so the value is never read as an option.
VALUE_OPTIONS = frozenset(
    {"-t", "--title", "-d", "--description", "--desc", "-a", "--assignee", "-l", "--labels"}
    | {"--priority", "--ac", "--remove-ac", "--check-ac", "--uncheck-ac", "--plan"}
    | {"--notes", "--append-notes", "--final-summary", "--append-final-summary", "--dep"}
    | {"--ref", "--doc", "--modified-file", "-p", "--parent", "--type", "--ordinal"}
    | {"--add-label", "--remove-label", "--milestone", "--project"}
)
REVIEWER_EDITS = frozenset({"--check-ac", "--uncheck-ac", "--append-notes", "--plain"})
SCRIPTS = frozenset({"board-check", "close-task", "record-check", "tick-intent"})
UNREADABLE = re.compile(r"[$`#]|<<|<\(|>\(")


class Decision(NamedTuple):
    verdict: str  # "deny", "ask" or "allow"
    reason: str


# --- the logic: plain data in, plain data out ---------------------------------------


def options(args: list[str]) -> list[tuple[str, Optional[str]]]:
    """Pair each option of a `backlog` command with its value, if it takes one."""
    out: list[tuple[str, Optional[str]]] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--") and "=" in arg:
            name, value = arg.split("=", 1)
            out.append((name, value))
        elif arg in VALUE_OPTIONS or arg in ("-s", "--status"):
            out.append((arg, args[i + 1] if i + 1 < len(args) else None))
            i += 1
        elif re.fullmatch(r"-s\S+", arg):
            out.append(("-s", arg[2:]))
        elif arg.startswith("-"):
            out.append((arg, None))
        i += 1
    return out


def is_task_edit(name: str, args: list[str]) -> bool:
    return name == "backlog" and args[:1] in (["task"], ["tasks"]) and args[1:2] == ["edit"]


def sets_done(name: str, args: list[str]) -> bool:
    return is_task_edit(name, args) and any(
        option in ("-s", "--status") and (value or "").strip().lower() == "done"
        for option, value in options(args[2:])
    )


def reviewer_may_run_backlog(args: list[str]) -> bool:
    """Read the board, tick or untick criteria, append notes, and file drafts. Nothing else."""
    noun, verb = (args + ["", ""])[:2]
    if noun.startswith("-") or noun in ("board", "search", "overview"):
        return True
    if verb in ("view", "list", "get", "--plain"):
        return True
    if noun in ("task", "tasks") and re.fullmatch(r"[\w-]*\d[\w.]*", verb):
        return True  # `backlog task 5` views it
    if noun in ("task", "tasks") and verb == "edit":
        return all(option in REVIEWER_EDITS for option, _ in options(args[3:]))
    if noun in ("task", "tasks") and verb == "create":
        return "--draft" in args
    return noun == "draft" and verb == "create"


def git_command(args: list[str]) -> list[str]:
    """A git call's subcommand and its arguments, past git's own options such as `-C dir`."""
    rest = list(args)
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] in ("-C", "-c", "--git-dir", "--work-tree") else rest[1:]
    return rest


def git_subcommand(args: list[str]) -> str:
    return (git_command(args) or [""])[0]


def git_writes(args: list[str]) -> bool:
    rest = git_command(args)
    if not rest:
        return False
    sub, more = rest[0], rest[1:]
    flags = {a for a in more if a.startswith("-")}
    plain = [a for a in more if not a.startswith("-")]
    if sub in GIT_WRITES:
        return True
    if sub == "stash":
        return not plain or plain[0] not in ("list", "show")
    if sub == "branch":
        return bool(plain) or bool(flags & {"-d", "-D", "-m", "-M", "-c", "-C", "--delete"})
    if sub == "tag":
        return bool(plain) and not flags & {"-l", "--list"}
    if sub == "worktree":
        return bool(plain) and plain[0] in ("add", "remove", "move", "prune", "repair")
    return False


def writes(name: str, args: list[str]) -> bool:
    """Whether a program call plainly changes files or git history."""
    if name in WRITERS:
        return True
    if name == "sed" and any(a == "--in-place" or re.fullmatch(r"-[nEr]*i\S*", a) for a in args):
        return True
    if name in ("perl", "ruby") and any(re.fullmatch(r"-[pnlaw0]*i\S*", a) for a in args):
        return True
    if name == "find" and ("-delete" in args or "-exec" in args and "rm" in args):
        return True
    if name == "git" and git_writes(args):
        return True
    return any(
        arg in REDIRECTS and (i + 1 >= len(args) or args[i + 1] != "/dev/null")
        for i, arg in enumerate(args)
    )


def starts_main(args: list[str]) -> bool:
    """Whether `git init` is given `main` as its first branch."""
    for i, arg in enumerate(args):
        if arg in ("-b", "--initial-branch") and args[i + 1 : i + 2] == ["main"]:
            return True
        if arg in ("-bmain", "--initial-branch=main"):
            return True
    return False


def own_call(words: list[str], root: str) -> bool:
    """Whether one simple command is a call the reviewer makes without a prompt.

    That is `cd`, a `backlog` command the reviewer may run, or `python3` running one of
    this plugin's scripts by its absolute path in this plugin, but never `record-check`
    with an open command after `--`. Read strictly: no assignments, wrappers, redirects
    or comments.
    """
    if any("<" in word or ">" in word for word in words):
        return False
    if words[0] == "cd":
        return len(words) <= 2
    if words[0] == "backlog":
        return reviewer_may_run_backlog(words[1:])
    if words[0] not in ("python3", "python") or len(words) < 2 or not os.path.isabs(words[1]):
        return False
    script = os.path.basename(words[1])
    at_home = os.path.realpath(words[1]) == os.path.realpath(os.path.join(root, "scripts", script))
    return script in SCRIPTS and at_home and not (script == "record-check" and "--" in words)


def reviewer_may_skip_prompt(command: str, root: str) -> bool:
    """Whether every part of the command is one of the reviewer's own calls.

    This grants a permission, so it fails closed: any `$`, backtick or process
    substitution, which the parser can't see into, means no.
    """
    if UNREADABLE.search(command):
        return False
    parts = shellwords.simple_commands(command, keep_assignments=True)
    return bool(parts) and all(own_call(words, root) for words in parts)


def status_of(text: str) -> str:
    found = STATUS.match(text)
    if not found:
        return ""
    value = re.sub(r"\s+#.*$", "", found.group(1)).strip()
    return value.strip("'\"").strip().lower()


def after_edit(tool: str, tool_input: dict, existing: str) -> Optional[str]:
    """The task file's text once this Edit or Write lands, or None if it can't be known."""
    if tool == "Write":
        return str(tool_input.get("content") or "")
    old = str(tool_input.get("old_string") or "")
    new = str(tool_input.get("new_string") or "")
    if not old or old not in existing:
        return None
    return existing.replace(old, new, -1 if tool_input.get("replace_all") else 1)


def decide(
    tool: str,
    tool_input: dict,
    agent_type: str,
    existing: str,
    root: str,
    default_branch: str = "",
) -> Optional[Decision]:
    """Say whether this tool call is denied, needs the person, is allowed, or (None) is left
    to the usual permissions.

    `existing` is the current text of the task file an Edit or Write changes, or "".
    `default_branch` is git's `init.defaultBranch`, read only for a `git init`.
    """
    reviewer = agent_type == REVIEWER
    close_task = 'python3 "%s/scripts/close-task" <id> --notes "<closing notes>"' % root
    by_script = Decision(
        "deny",
        "A task is set to Done only by close-task, which refuses unless every criterion is met "
        "and every child is done: %s. %s"
        % (
            close_task,
            "Run it once the review says the task closes."
            if reviewer
            else "Whether it closes is decided by someone who did not do the work, so hand the "
            "task to the philosophy:reviewer agent, which runs it.",
        ),
    )
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        found = shellwords.programs(command)
        if found is None:
            return by_script if DONE_COMMAND.search(command) else None
        if any(sets_done(ran.name, ran.args) for ran in found):
            return by_script
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
        if not reviewer:
            if any(ran.name == "close-task" for ran in found):
                return Decision(
                    "ask",
                    "close-task is closing a task outside the philosophy:reviewer agent. Approve "
                    "only if you reviewed the work yourself and did not do it; otherwise decline "
                    "and hand the task to the reviewer.",
                )
            return None
        if any(ran.name == "backlog" and not reviewer_may_run_backlog(ran.args) for ran in found):
            return Decision(
                "deny",
                "The reviewer reads the board, ticks criteria with --check-ac, appends notes, and "
                "files drafts. Changing a task's criteria, labels, plan or status changes the "
                "work under review: report it as a finding instead.",
            )
        if any(writes(ran.name, ran.args) for ran in found):
            return Decision(
                "deny",
                "The reviewer does not change the work it reviews: report what should change as "
                "a finding instead. Reading, running the checks without fixing, board-check, "
                "record-check, close-task, and backlog notes and drafts are allowed.",
            )
        if reviewer_may_skip_prompt(command, root):
            return Decision(
                "allow",
                "The reviewer's own calls: this plugin's scripts, including the repository's "
                "declared checks through record-check --tier, and backlog commands that read "
                "the board, tick criteria, append notes, or file drafts.",
            )
    elif tool in ("Edit", "Write"):
        path = str(tool_input.get("file_path") or "").replace("\\", "/")
        if TASK_FILE.search(path):
            # An Edit whose old_string isn't in the file fails on its own, so None goes ahead.
            after = after_edit(tool, tool_input, existing)
            if after is not None and status_of(after) == "done" and status_of(existing) != "done":
                return by_script
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
        existing = ""
        path = str(tool_input.get("file_path") or "")
        if tool in ("Edit", "Write") and TASK_FILE.search(path.replace("\\", "/")):
            target = Path(path)
            existing = target.read_text(encoding="utf-8") if target.is_file() else ""
        root = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parent.parent)
        default_branch = ""
        if tool == "Bash" and "init" in str(tool_input.get("command") or ""):
            default_branch = git_default_branch(str(payload.get("cwd") or os.getcwd()))
        agent = str(payload.get("agent_type") or "")
        decision = decide(tool, tool_input, agent, existing, root, default_branch)
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
