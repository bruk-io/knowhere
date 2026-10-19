#!/usr/bin/env python3
"""inline-expressions.py: forbid "${{ }}" inside a run: block of the intent workflows.

    inline-expressions.py [--root DIR]

Checks `.github/workflows/intent-*.yml` and
`plugins/philosophy/templates/github/intent-*.yml`. These workflows carry a push's
slugs and shas from `find` to a `dispatch` job and on to a `repository_dispatch`-
triggered job that re-checks them (loop-trigger-events/spec.md R5); every one of those
values must reach a shell step through `env:`, never inlined into `run:`, so GitHub's
expression syntax never becomes part of the shell command it runs. Prints
`<path>:<line>: <line's text>` for each `${{` found inside a `run:` block, and exits 1
if any was found, 0 otherwise. Written for Python 3.9 and the standard library, like
the rest of the loop's scripts, with no YAML parser: a `run:` key's own indentation is
read straight off the text, the same way the workflow files are.
"""

from __future__ import annotations

import argparse
import glob
import re
from pathlib import Path

RUN_KEY = re.compile(r"^(?P<indent>\s*)run:\s*(?P<rest>.*?)\s*$")
BLOCK_SCALAR = re.compile(r"^[|>][+-]?\d*$")
PATTERNS = (
    ".github/workflows/intent-*.yml",
    "plugins/philosophy/templates/github/intent-*.yml",
)


def offenses(text: str) -> list[tuple[int, str]]:
    """Each (1-based line number, line) in `text` where "${{" sits inside a run: block.

    A `run: |` (or `>`, with any chomping indicator) opens a block scalar: every line
    indented more than the `run:` key, until one that isn't, is its content. A `run:`
    followed by anything else is a single-line command, and that line is the content.
    """
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        match = RUN_KEY.match(lines[i])
        if match is None:
            i += 1
            continue
        indent = len(match.group("indent"))
        rest = match.group("rest")
        if BLOCK_SCALAR.match(rest):
            i += 1
            while i < len(lines):
                line = lines[i]
                if line.strip() and len(line) - len(line.lstrip(" ")) <= indent:
                    break
                if "${{" in line:
                    found.append((i + 1, line))
                i += 1
        else:
            if "${{" in rest:
                found.append((i + 1, lines[i]))
            i += 1
    return found


def main(argv: list[str] | None = None) -> int:
    top = argparse.ArgumentParser(
        prog="inline-expressions.py", description=__doc__.splitlines()[0]
    )
    top.add_argument("--root", type=Path, default=Path.cwd())
    args = top.parse_args(argv)

    hits = 0
    for pattern in PATTERNS:
        matched = sorted(glob.glob(str(args.root / pattern)))
        if not matched:
            print("inline-expressions.py: %s matched no file" % pattern)
            hits += 1
            continue
        for found_path in matched:
            path = Path(found_path)
            rel = path.relative_to(args.root)
            for line_no, line in offenses(path.read_text(encoding="utf-8")):
                print("%s:%d: %s" % (rel, line_no, line.strip()))
                hits += 1
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
