"""Read a shell command the way the hooks need to: which programs it runs, with what.

Shared by context.py and guard.py. Best effort by design: it understands the shapes a
model writes (`&&` chains, several lines, heredocs, `sh -c`, `env` and `python3`
prefixes), not the whole shell grammar. Written for Python 3.9.
"""

from __future__ import annotations

import os
import re
import shlex
from typing import NamedTuple, Optional

SEPARATORS = frozenset(";&|()\n")
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=.*")
HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\1")
# Words that run the command after them rather than being the program themselves.
KEYWORDS = frozenset({"{", "}", "!", "if", "then", "elif", "else", "do", "while", "until"})
WRAPPERS = frozenset({"time", "command", "exec", "nohup", "env", "npx", "bunx", "pnpx"})
PYTHON = re.compile(r"python(?:3(?:\.\d+)?)?")
PYTHON_VALUE_OPTIONS = frozenset({"-W", "-X", "-m", "-c"})
SHELLS = frozenset({"sh", "bash", "zsh", "dash"})
# Commands that run the command after their `--`, such as this plugin's record-check.
RUNNERS = frozenset({"record-check"})


class Program(NamedTuple):
    """One program a command runs: its name, its arguments, and the word that named it."""

    name: str
    args: list[str]
    path: str


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies, which are data for a program and not commands."""
    lines = command.split("\n")
    out = []
    ending: list[str] = []
    for line in lines:
        if ending:
            if line.strip() == ending[0]:
                ending.pop(0)
            continue
        out.append(line)
        ending = [match.group(2) for match in HEREDOC.finditer(line)]
    return "\n".join(out)


def simple_commands(command: str, keep_assignments: bool = False) -> Optional[list[list[str]]]:
    """Split a command into the words of each simple command, or None if it can't be read.

    Leading `VAR=value` assignments are dropped unless `keep_assignments`. Newlines
    separate commands, as `;` does, and a backslash at the end of a line continues it.
    """
    text = strip_heredocs(command.replace("\\\n", " "))
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars="();<>|&\n")
        lexer.commenters = ""  # shlex ends a word at `#`, the shell doesn't
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    parts: list[list[str]] = [[]]
    for token in tokens:
        if token and set(token) <= SEPARATORS:
            parts.append([])
        elif keep_assignments or parts[-1] or not ASSIGNMENT.fullmatch(token):
            parts[-1].append(token)
    return [part for part in parts if part]


def program(words: list[str]) -> Program:
    """The program a simple command runs and its arguments.

    Looks through shell keywords, wrappers such as `env` and `npx`, `uv run`, and
    `python3 [options] script`, so `env python3 -u x/close-task 5` runs `close-task`.
    """
    rest = list(words)
    while rest:
        name = os.path.basename(rest[0]).split("@", 1)[0]
        if name in KEYWORDS or ASSIGNMENT.fullmatch(rest[0]):
            rest = rest[1:]
        elif name in WRAPPERS:
            rest = rest[1:]
            while rest and (rest[0].startswith("-") or ASSIGNMENT.fullmatch(rest[0])):
                rest = rest[1:]
        elif name == "uv" and rest[1:2] == ["run"]:
            rest = rest[2:]
            while rest and rest[0].startswith("-"):
                rest = rest[2:] if rest[0] in ("--with", "--python", "-p") else rest[1:]
        elif PYTHON.fullmatch(name) and len(rest) > 1:
            args = rest[1:]
            while args and args[0].startswith("-") and args[0] != "-":
                if args[0] in ("-m", "-c"):
                    return Program(name, args, rest[0])
                args = args[2:] if args[0] in PYTHON_VALUE_OPTIONS else args[1:]
            if not args or args[0] == "-":
                return Program(name, args, rest[0])
            rest = args
        else:
            return Program("backlog" if name == "backlog.md" else name, rest[1:], rest[0])
    return Program("", [], "")


def programs(command: str) -> Optional[list[Program]]:
    """Every program the command runs, or None if it can't be read.

    That includes the command inside `sh -c '...'` and after a runner's `--`.
    """
    parts = simple_commands(command)
    if parts is None:
        return None
    found: list[Program] = []
    for words in parts:
        ran = program(words)
        if not ran.name:
            continue
        found.append(ran)
        inner = None
        if ran.name in SHELLS and "-c" in ran.args[:-1]:
            inner = ran.args[ran.args.index("-c") + 1]
        elif ran.name in RUNNERS and "--" in ran.args[:-1]:
            after = ran.args[ran.args.index("--") + 1 :]
            inner = after[0] if len(after) == 1 else shlex.join(after)
        if inner is not None:
            nested = programs(inner)
            if nested is None:
                return None
            found += nested
    return found
