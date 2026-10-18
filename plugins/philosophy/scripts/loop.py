"""The build's mechanical decisions, so no model makes them twice the same way.

Which change in a spec's delivery order is next, which of a plan's files CODEOWNERS
gates, and how a check's output is written down as evidence. The core takes text and
returns values; the shell at the bottom reads files, asks git, and runs the check, and
`next-change`, `gated-paths` and `run-check` are thin commands over both. Written for
Python 3.9 and the standard library, like the hooks.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional

import artefact as a

CHANGE = re.compile(r"^(\d{2})\s+(.*)$")
BUILD_BRANCH = re.compile(r"refs/heads/build/[^/]+/(\d{2})$")
CODEOWNERS_HOMES = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
TIERS = ("fast", "full")
TIMED_OUT = 124  # the exit code `timeout` uses, for a check that ran too long
GIT_TIMEOUT = 60


class Change(NamedTuple):
    number: str
    title: str
    delivers: tuple[int, ...]


class Step(Enum):
    BUILD = "build"
    TAKEN = "taken"
    DONE = "done"


class Next(NamedTuple):
    step: Step
    change: Optional[Change]


class Rule(NamedTuple):
    pattern: str
    owners: tuple[str, ...]


class LoopError(ValueError):
    """Something the build needs that is missing or unreadable."""


# --- the logic: plain data in, plain data out ---------------------------------------


def delivery_order(spec: a.Doc) -> tuple[Change, ...]:
    """The changes in a spec's delivery-order table, in order. A row's first cell is
    `NN <title>` and its second names the R-numbers it delivers."""
    design = a.section(spec, "Design") or ""
    _, found, rest = design.partition("### Delivery order")
    body = rest.split("\n### ", 1)[0] if found else design
    out = []
    for row in a.table_rows(body):
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        change = CHANGE.match(cells[0]) if cells else None
        if change and len(cells) > 1:
            delivers = tuple(sorted(a.cited(cells[1])))
            out.append(Change(change.group(1), change.group(2).strip(), delivers))
    return tuple(out)


def next_change(order: tuple[Change, ...], planned: frozenset[str], taken: frozenset[str]) -> Next:
    """The first change with no plan yet. If its build is already in flight, nothing
    starts: builds for one intent run one at a time, in order."""
    for change in order:
        if change.number in planned:
            continue
        return Next(Step.TAKEN if change.number in taken else Step.BUILD, change)
    return Next(Step.DONE, None)


def parse_codeowners(text: str) -> tuple[Rule, ...]:
    rules = []
    for line in text.splitlines():
        words = line.split("#", 1)[0].split()
        if words:
            rules.append(Rule(words[0], tuple(words[1:])))
    return tuple(rules)


def pattern_regex(pattern: str) -> str:
    """Translate a CODEOWNERS pattern into a regex over a repository-relative path.

    A pattern with a slash before its end is anchored at the root; one without matches
    at any depth. A pattern that ends in `/`, or whose last segment has no wildcard,
    also covers everything under what it names. One whose last segment is a wildcard,
    such as `docs/*`, covers only what is directly there, as GitHub reads it.
    """
    anchored = "/" in pattern.rstrip("/")
    glob = pattern.strip("/")
    last = glob.rsplit("/", 1)[-1]
    covers_below = pattern.endswith("/") or not any(c in last for c in "*?")
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
    below = "(?:/.*)?" if covers_below else ""
    return "^%s%s%s$" % ("" if anchored else "(?:.*/)?", "".join(out), below)


def owners_of(path: str, rules: tuple[Rule, ...]) -> tuple[str, ...]:
    """Who owns a path: the owners on the last rule that matches it, as GitHub reads
    CODEOWNERS. A matching rule with no owners leaves the path unowned."""
    owners: tuple[str, ...] = ()
    for rule in rules:
        if re.match(pattern_regex(rule.pattern), path.lstrip("/")):
            owners = rule.owners
    return owners


def gated(paths: tuple[str, ...], rules: tuple[Rule, ...]) -> tuple[str, ...]:
    """The paths that have an owner. Any owner gates: GitHub asks that owner for a review
    before the merge, so a catch-all `* @team` line gates every path, as it should."""
    return tuple(path for path in paths if owners_of(path, rules))


def exit_code(returncode: int) -> int:
    """The exit code a shell would report: a check killed by signal N exits 128 + N."""
    return 128 - returncode if returncode < 0 else returncode


def declared(text: str, tier: str) -> Optional[str]:
    """The command a `.claude/checks.json` declares for a tier, or None.

    Raises:
        LoopError: the file is not a JSON object.
        ValueError: the file is not JSON.
    """
    data = json.loads(text)
    if not isinstance(data, dict):
        raise LoopError('.claude/checks.json must be a JSON object: {"fast": "...", "full": "..."}')
    value = data.get(tier)
    return value if isinstance(value, str) and value.strip() else None


def evidence(command: str, code: int, output: str, lines: int) -> str:
    """A check's run as a block to paste into a PR: the command, its output's last lines,
    and its exit code, all as the tool printed them. The fence is longer than any run of
    backticks in the output, so the output can't close it early."""
    tail = output.rstrip("\n").splitlines()[-lines:] if lines > 0 else []
    longest = max((len(run) for run in re.findall(r"`+", "\n".join(tail))), default=0)
    fence = "`" * max(3, longest + 1)
    return "\n".join([fence, "$ " + command, *tail, "exit=%d" % code, fence])


# --- the shell ----------------------------------------------------------------------


def repo_root(start: Path) -> Path:
    done = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    return Path(done.stdout.strip()) if done.returncode == 0 else start


def remote_build_numbers(root: Path, slug: str, remote: str) -> frozenset[str]:
    """The change numbers with a `build/<slug>/NN` branch on the remote.

    Raises:
        LoopError: git could not list the remote's branches.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "ls-remote", "--heads", remote, "build/%s/*" % slug],
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as error:
        raise LoopError("listing %s's branches took over %ds" % (remote, GIT_TIMEOUT)) from error
    if done.returncode != 0:
        raise LoopError("could not list %s's branches: %s" % (remote, done.stderr.strip()))
    return frozenset(
        found.group(1)
        for line in done.stdout.splitlines()
        for found in [BUILD_BRANCH.search(line)]
        if found
    )


def find_next(folder: Path, remote: Optional[str]) -> Next:
    """The next change for the intent in `folder`, with the remote's build branches
    counted as taken unless `remote` is None.

    Raises:
        LoopError: the intent has no readable spec, or the remote could not be read.
        artefact.ArtefactError: an artefact could not be read.
    """
    spec = a.read(folder / "spec.md")
    if spec is None:
        raise LoopError("%s has no spec.md" % folder)
    order = delivery_order(spec)
    if not order:
        raise LoopError("%s has no delivery order" % spec.path)
    planned = frozenset(path.name[:2] for path in (folder / "plans").glob("[0-9][0-9]-*.md"))
    taken = remote_build_numbers(repo_root(folder), folder.name, remote) if remote else frozenset()
    return next_change(order, planned, taken)


def load_rules(root: Path) -> tuple[Rule, ...]:
    for home in CODEOWNERS_HOMES:
        path = root / home
        if path.is_file():
            return parse_codeowners(path.read_text(encoding="utf-8"))
    return ()


def run_declared(root: Path, tier: str, lines: int, timeout: int) -> tuple[int, str]:
    """Run the repository's declared check for a tier, from the repository root. A check
    that runs past `timeout` seconds is stopped and reported with exit code 124.

    Raises:
        LoopError: the repository declares no command for the tier.
    """
    path = root / ".claude" / "checks.json"
    command = declared(path.read_text(encoding="utf-8"), tier) if path.is_file() else None
    if command is None:
        raise LoopError(
            'no %s check declared: add {"fast": "<the change\'s check>", "full": "<the '
            'whole check>"} to %s, one command per tier that exits non-zero on failure'
            % (tier, path)
        )
    # The check runs in its own process group, so a timeout stops everything it started,
    # not only bash: a child still holding the pipe would otherwise keep run-check waiting.
    child = subprocess.Popen(
        ["bash", "-c", command],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        output, _ = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        output, _ = child.communicate()
        output = (output or "") + "\nrun-check: stopped after %ds" % timeout
        return TIMED_OUT, evidence(command, TIMED_OUT, output, lines)
    code = exit_code(child.returncode)
    return code, evidence(command, code, output, lines)
