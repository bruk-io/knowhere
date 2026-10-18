#!/usr/bin/env python3
"""Check an intent, spec or plan the moment Claude writes it.

PostToolUse on Write and Edit: when the file is `intent/<slug>/intent.md`, `spec.md` or
`plans/<name>.md`, runs the artefact checks on that intent and returns any findings as
additionalContext, so they arrive with the write that caused them. Anything else gets
no output.

Written for Python 3.9, because hooks run under whatever `python3` is on PATH. A hook
must never break the session, so every failure exits 0 with the reason on stderr.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import artefact as a  # noqa: E402

PLUGIN = "philosophy"
ARTEFACT = re.compile(r"^intent/[^/]+/(?:intent\.md|spec\.md|plans/[^/]+\.md)$")


def is_artefact(relative: str) -> bool:
    """Whether a path, relative to its repository's root, is an intent, spec or plan."""
    return bool(ARTEFACT.match(relative.replace("\\", "/")))


def repo_root(folder: Path) -> Optional[Path]:
    while not folder.is_dir() and folder != folder.parent:
        folder = folder.parent
    try:
        done = subprocess.run(
            ["git", "-C", str(folder), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(done.stdout.strip()) if done.returncode == 0 else None


def artefact_path(payload: dict) -> Optional[Path]:
    """The artefact this tool call wrote, or None if it wrote something else. The path
    must be `intent/...` from the root of the repository the file is in, so a folder
    named `intent` somewhere above the repository doesn't count."""
    raw = str((payload.get("tool_input") or {}).get("file_path") or "")
    if "intent/" not in raw.replace("\\", "/"):
        return None
    path = Path(raw)
    root = repo_root(path.parent)
    if root is None:
        return None
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    return path if is_artefact(relative) else None


def context(findings: list[a.Finding], where: Path) -> str:
    return (
        "[%s] artefact-check found %d problem%s across %s, the intent this write belongs "
        "to; some may be in its other files. Fix them before this goes to review:\n%s"
        % (PLUGIN, len(findings), "" if len(findings) == 1 else "s", where, a.render(findings))
    )


def main() -> int:
    try:
        path = artefact_path(json.load(sys.stdin))
        if path is None or not path.exists():
            return 0
        findings = a.load_findings(path)
        if findings:
            folder = path.parent.parent if path.parent.name == "plans" else path.parent
            output = {
                "hookEventName": "PostToolUse",
                "additionalContext": context(findings, folder),
            }
            print(json.dumps({"hookSpecificOutput": output}))
    except Exception as error:  # noqa: BLE001 - a hook must never break the session
        print(
            "[%s] artefact check skipped: %s: %s" % (PLUGIN, type(error).__name__, error),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
