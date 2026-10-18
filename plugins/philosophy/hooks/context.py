#!/usr/bin/env python3
"""Put the plugin's constraints and rules in front of the model.

Claude Code does not load a plugin's CLAUDE.md or rules/, so this hook does it:

- SessionStart: prints the repository mode (owner or guest) and constraints.md. Stdout
  from a SessionStart hook becomes context.
- SubagentStart: returns the same text as additionalContext, because SessionStart does
  not fire for a subagent and the subagent never sees what it printed.
- PostToolUse: the first time a session or subagent touches a file matching a rule's
  `paths`, or runs a command named in its `commands`, returns that rule as
  additionalContext.

Written for Python 3.9, because hooks run under whatever `python3` is on PATH. A hook
must never break the session, so every failure exits 0 with the reason on stderr.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional

import shellwords

PLUGIN = "philosophy"
FILE_KEYS = ("file_path", "notebook_path")
RESET_SOURCES = ("startup", "clear", "compact")
LIST_KEYS = ("paths", "commands")


class Mode(Enum):
    OWNER = "owner"
    GUEST = "guest"


class Rule(NamedTuple):
    name: str
    paths: tuple[str, ...]
    commands: tuple[str, ...]
    owner_only: bool
    body: str


class Touch(NamedTuple):
    """What a tool call touched: a file path, or the commands a Bash call ran."""

    path: Optional[str]
    commands: tuple[str, ...]
    directory: str


class RuleError(ValueError):
    """A rule file whose frontmatter this hook cannot read."""


# --- the logic: plain data in, plain data out ---------------------------------------


def glob_to_regex(glob: str) -> str:
    """Translate a rule glob into a regex that matches a whole POSIX path.

    `**/` matches any number of directories (including none), `**` matches anything,
    `*` matches within one path segment, and `?` matches one character.
    """
    out = []
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return "".join(out)


def matches(path: str, globs: tuple[str, ...]) -> bool:
    """Say whether a path matches any glob. A relative glob may match at any depth."""
    posix = path.replace("\\", "/")
    return any(re.fullmatch("(?:.*/)?" + glob_to_regex(g), posix) for g in globs)


def parse_rule(name: str, text: str) -> Rule:
    """Read a rule file: `paths`, `commands` and `mode` from the frontmatter.

    `paths` and `commands` are YAML lists, one `- item` per line. A rule with neither
    matches nothing and is never injected.

    Raises:
        RuleError: `paths` or `commands` has an inline value instead of a list, which
            would otherwise leave the rule silently matching nothing.
    """
    lists: dict[str, list[str]] = {key: [] for key in LIST_KEYS}
    owner_only = False
    body = text
    if text.startswith("---\n") and "\n---\n" in text[4:]:
        front, body = text[4:].split("\n---\n", 1)
        current = None
        for line in front.splitlines():
            key, _, value = line.partition(":")
            if key in LIST_KEYS:
                if value.strip():
                    raise RuleError(
                        "rule %s: `%s` must be a list, one `- item` per line" % (name, key)
                    )
                current = key
            elif current and line.lstrip().startswith("- "):
                lists[current].append(line.lstrip()[2:].strip().strip("\"'"))
            else:
                current = None
                if key == "mode":
                    owner_only = value.strip() == Mode.OWNER.value
    return Rule(name, tuple(lists["paths"]), tuple(lists["commands"]), owner_only, body.strip())


def command_words(command: str) -> tuple[str, ...]:
    """Name the programs a shell command runs, such as `backlog` or `git`.

    A command the shell lexer cannot read falls back to the first word after each
    separator.
    """
    found = shellwords.programs(command)
    if found is not None:
        return tuple(ran.name for ran in found)
    words = re.findall(r"(?:^|[;&|\n(])\s*(?:[A-Za-z_]\w*=\S*\s+)*([^\s;&|()]+)", command)
    return tuple(os.path.basename(word) for word in words)


def normalise_remote(remote: str) -> str:
    """Reduce a git remote URL to `host/owner/repo` so one pattern covers SSH and HTTPS."""
    url = remote.strip().lower()
    url = re.sub(r"^[a-z+]+://", "", url)
    url = re.sub(r"^[^@/]+@", "", url)
    return url.replace(":", "/", 1) if "/" not in url.split(":", 1)[0] else url


def parse_owners(text: str) -> tuple[str, ...]:
    """Read owners.txt: one pattern per line, with `#` comments and blank lines ignored."""
    lines = (line.split("#", 1)[0].strip().lower() for line in text.splitlines())
    return tuple(line for line in lines if line)


def repo_mode(remote: Optional[str], owners: tuple[str, ...]) -> Mode:
    """Decide the mode. No remote means a local repository, which is the owner's."""
    if remote is None:
        return Mode.OWNER
    normalised = normalise_remote(remote)
    return Mode.OWNER if any(owner in normalised for owner in owners) else Mode.GUEST


def rules_for(rules: tuple[Rule, ...], touch: Touch, seen: frozenset[str]) -> tuple[Rule, ...]:
    """Pick the rules this touch matches that are not yet in context, in either mode."""
    return tuple(
        rule
        for rule in rules
        if rule.name not in seen
        and (
            (touch.path is not None and matches(touch.path, rule.paths))
            or bool(set(touch.commands) & set(rule.commands))
        )
    )


def in_mode(rules: tuple[Rule, ...], mode: Mode) -> tuple[Rule, ...]:
    """Drop the owner-only rules in a guest repository."""
    return tuple(rule for rule in rules if not (rule.owner_only and mode is Mode.GUEST))


def session_text(mode: Mode, remote: Optional[str], constraints: str, root: str) -> str:
    """Build what SessionStart prints: the mode line, then the constraints."""
    if mode is Mode.OWNER:
        line = "Repository mode: owner. The full standard applies here."
    else:
        line = (
            "Repository mode: guest (origin: %s). The local style governs, and the "
            "plugin's code rules are not loaded." % normalise_remote(remote or "")
        )
    return "[%s] %s\n\n%s" % (PLUGIN, line, constraints.replace("{plugin_root}", root).strip())


def rule_text(rules: tuple[Rule, ...], root: str) -> str:
    """Build the additionalContext for the rules being injected."""
    return "\n\n".join(
        "[%s] rule %s\n\n%s" % (PLUGIN, r.name, r.body.replace("{plugin_root}", root))
        for r in rules
    )


# --- the shell: the only code that touches git, the filesystem, or stdio -------------


def plugin_root() -> Path:
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)


def origin(directory: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git", "-C", directory, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def session_dir(payload: dict) -> Path:
    session = re.sub(r"[^\w.-]", "_", str(payload.get("session_id") or "unknown"))
    return Path(tempfile.gettempdir()) / ("claude-%s-plugin" % PLUGIN) / session


def marker_dir(payload: dict) -> Path:
    return session_dir(payload) / str(payload.get("agent_id") or "main")


def load_rules(root: Path) -> tuple[Rule, ...]:
    rules = []
    for path in sorted((root / "rules").glob("*.md")):
        try:
            rules.append(parse_rule(path.stem, path.read_text()))
        except RuleError as error:
            print("[%s] %s" % (PLUGIN, error), file=sys.stderr)
    return tuple(rules)


def owners(root: Path) -> tuple[str, ...]:
    owners_file = root / "owners.txt"
    return parse_owners(owners_file.read_text()) if owners_file.exists() else ()


def existing_directory(path: Path) -> Path:
    """The nearest directory that exists, so git can run in it before a Write creates it."""
    for candidate in (path, *path.parents):
        if candidate.is_dir():
            return candidate
    return Path.cwd()


def mode_for(root: Path, payload: dict, directory: str) -> Mode:
    """The mode of the repository holding `directory`, asked of git once per session."""
    cache = session_dir(payload) / ("mode-%s" % hashlib.sha1(directory.encode()).hexdigest()[:16])
    try:
        return Mode(cache.read_text().strip())
    except (OSError, ValueError):
        pass
    mode = repo_mode(origin(directory), owners(root))
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(mode.value)
    except OSError:
        pass
    return mode


def touched(payload: dict) -> Optional[Touch]:
    tool_input = payload.get("tool_input") or {}
    cwd = str(payload.get("cwd") or os.getcwd())
    path = next((tool_input[k] for k in FILE_KEYS if tool_input.get(k)), None)
    if path:
        full = Path(cwd, str(path))
        return Touch(str(path), (), str(existing_directory(full.parent)))
    if tool_input.get("command"):
        return Touch(None, command_words(str(tool_input["command"])), cwd)
    return None


def on_session_start(payload: dict, root: Path) -> None:
    cwd = str(payload.get("cwd") or os.getcwd())
    remote = origin(cwd)
    constraints = (root / "constraints.md").read_text()
    print(session_text(repo_mode(remote, owners(root)), remote, constraints, str(root)))
    sys.stdout.flush()
    if payload.get("source") in RESET_SOURCES:
        # The rules injected earlier are no longer in context, so let them load again.
        for marker in session_dir(payload).glob("*/*.seen"):
            marker.unlink()


def on_subagent_start(payload: dict, root: Path) -> None:
    cwd = str(payload.get("cwd") or os.getcwd())
    remote = origin(cwd)
    constraints = (root / "constraints.md").read_text()
    text = session_text(repo_mode(remote, owners(root)), remote, constraints, str(root))
    output = {"hookEventName": "SubagentStart", "additionalContext": text}
    print(json.dumps({"hookSpecificOutput": output}))
    sys.stdout.flush()


def on_tool_use(payload: dict, root: Path) -> None:
    touch = touched(payload)
    if touch is None:
        return
    markers = marker_dir(payload)
    seen = frozenset(p.stem for p in markers.glob("*.seen")) if markers.exists() else frozenset()
    chosen = rules_for(load_rules(root), touch, seen)
    if any(rule.owner_only for rule in chosen):
        chosen = in_mode(chosen, mode_for(root, payload, touch.directory))
    if not chosen:
        return
    output = {"hookEventName": "PostToolUse", "additionalContext": rule_text(chosen, str(root))}
    print(json.dumps({"hookSpecificOutput": output}))
    sys.stdout.flush()
    # Delivered first, recorded second: a rule that arrives twice beats one that never does.
    try:
        markers.mkdir(parents=True, exist_ok=True)
        for rule in chosen:
            (markers / (rule.name + ".seen")).touch()
    except OSError as error:
        print("[%s] could not record delivery: %s" % (PLUGIN, error), file=sys.stderr)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        root = plugin_root()
        if payload.get("hook_event_name") == "SessionStart":
            on_session_start(payload, root)
        elif payload.get("hook_event_name") == "SubagentStart":
            on_subagent_start(payload, root)
        elif payload.get("hook_event_name") == "PostToolUse":
            on_tool_use(payload, root)
    except Exception as error:  # noqa: BLE001 - a hook must never break the session
        print("[%s] hook skipped: %s: %s" % (PLUGIN, type(error).__name__, error), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
