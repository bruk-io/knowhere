#!/usr/bin/env python3
"""Pin GitHub Actions to commit SHAs, with the exact release as a comment.

    pin-actions.py [--check] [--bump] FILE...

A tag such as `v4` moves when its owner pushes to it, so a workflow that holds a secret
should name the commit it runs. Each `uses: owner/repo@tag` becomes
`uses: owner/repo@<40-hex sha> # <release>`, where the release is the most specific tag
(`v4.2.2`) on the commit the tag points at. Local (`./`) and `docker://` actions are left
alone. Tags are read with `git ls-remote`, so no token is needed.

--check  change nothing; list each unpinned action and exit 1 if there is one
--bump   re-resolve pinned actions from their major tag (`# v4.2.2` follows `v4`)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

USES = re.compile(
    r"^(?P<pre>\s*-?\s*uses:\s*)"
    r"(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?P<path>/[^@\s]*)?"
    r"@(?P<ref>[^\s#]+)(?P<comment>\s*#\s*(?P<tag>\S+))?\s*$"
)
SHA = re.compile(r"^[0-9a-f]{40}$")
SEMVER = re.compile(r"^v?\d+(?:\.\d+)*$")

Resolve = Callable[[str, str], Optional[tuple[str, str]]]


def tags_by_commit(ls_remote: str) -> dict[str, str]:
    """Each tag's commit, from `git ls-remote --tags` output. An annotated tag's own
    object is replaced by the commit it points at (its `^{}` line)."""
    out: dict[str, str] = {}
    for line in ls_remote.splitlines():
        sha, _, ref = line.partition("\t")
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/") :]
        if name.endswith("^{}"):
            out[name[:-3]] = sha
        else:
            out.setdefault(name, sha)
    return out


def release_for(tags: dict[str, str], tag: str) -> Optional[tuple[str, str]]:
    """The commit a tag points at, and the most specific semver tag on that commit."""
    sha = tags.get(tag)
    if sha is None:
        return None
    same = [name for name, commit in tags.items() if commit == sha and SEMVER.match(name)]
    exact = max(same, key=lambda name: (name.count("."), name), default=tag)
    return sha, exact


def major(tag: str) -> str:
    """`v4` for `v4.2.2`: the moving tag a release belongs to."""
    return tag.split(".", 1)[0]


def pin_line(line: str, resolve: Resolve, bump: bool) -> tuple[str, Optional[str]]:
    """The line with its action pinned, and the action it couldn't resolve, if any."""
    found = USES.match(line)
    if not found or found.group("repo").startswith("."):
        return line, None
    ref, tag = found.group("ref"), found.group("tag")
    if SHA.match(ref) and not (bump and tag):
        return line, None
    wanted = major(tag) if SHA.match(ref) and tag else ref
    resolved = resolve(found.group("repo"), wanted)
    if resolved is None:
        return line, "%s@%s" % (found.group("repo"), wanted)
    sha, exact = resolved
    pinned = "%s%s%s@%s # %s" % (
        found.group("pre"),
        found.group("repo"),
        found.group("path") or "",
        sha,
        exact,
    )
    return pinned, None


def unpinned(line: str) -> bool:
    found = USES.match(line)
    return (
        bool(found)
        and not found.group("repo").startswith(".")
        and not SHA.match(found.group("ref"))
    )


# --- the shell ----------------------------------------------------------------------


def remote_resolver() -> Resolve:
    cache: dict[str, dict[str, str]] = {}

    def resolve(repo: str, tag: str) -> Optional[tuple[str, str]]:
        if repo not in cache:
            done = subprocess.run(
                ["git", "ls-remote", "--tags", "https://github.com/%s" % repo],
                capture_output=True,
                text=True,
                timeout=60,
            )
            cache[repo] = tags_by_commit(done.stdout) if done.returncode == 0 else {}
        return release_for(cache[repo], tag)

    return resolve


def main(argv: Optional[list[str]] = None) -> int:
    top = argparse.ArgumentParser(prog="pin-actions", description=__doc__.splitlines()[0])
    top.add_argument("files", nargs="+", type=Path)
    top.add_argument("--check", action="store_true", help="report unpinned actions only")
    top.add_argument("--bump", action="store_true", help="re-resolve pinned actions")
    args = top.parse_args(argv)
    if args.check:
        found = [
            "%s:%d: %s" % (path, number, line.strip())
            for path in args.files
            for number, line in enumerate(path.read_text().splitlines(), 1)
            if unpinned(line)
        ]
        print("\n".join(found) if found else "every action is pinned")
        return 1 if found else 0
    resolve = remote_resolver()
    failed: list[str] = []
    for path in args.files:
        text = path.read_text()
        lines = []
        for line in text.splitlines(keepends=True):
            body = line.rstrip("\n")
            pinned, missing = pin_line(body, resolve, args.bump)
            lines.append(pinned + line[len(body) :])
            if missing:
                failed.append("%s: no tag %s" % (path, missing))
        new = "".join(lines)
        if new != text:
            path.write_text(new)
            print("pinned %s" % path)
    for problem in failed:
        print(problem, file=sys.stderr)
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
