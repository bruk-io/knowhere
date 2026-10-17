#!/usr/bin/env python3
"""PostToolUse hook handler for the likec4-diagrams skill.

Fires after Write/Edit while the skill is active; lints the touched .c4
file's project directory with c4lint and reports violations back to Claude
(exit 2 -> stderr is surfaced as feedback; the edit itself has already landed).

Reads the tool-event JSON on stdin. Python 3.9+, stdlib only.
"""

import json
import os
import subprocess
import sys


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # unparseable event — never block on hook plumbing

    file_path = (event.get("tool_input") or {}).get("file_path") or ""
    if not file_path.endswith(".c4"):
        return 0  # not a LikeC4 file — nothing to do

    project_dir = os.path.dirname(file_path)
    self_dir = os.path.dirname(os.path.abspath(__file__))
    c4lint = os.path.join(self_dir, "c4lint.py")

    proc = subprocess.run(
        [sys.executable or "python3", c4lint, project_dir],
        capture_output=True, text=True,
    )

    if proc.returncode == 1:
        print(
            f"c4lint: orthodox-C4 violations in {project_dir} after editing {file_path} — fix before proceeding:",
            file=sys.stderr,
        )
        print((proc.stdout or "") + (proc.stderr or ""), file=sys.stderr)
        return 2

    if proc.returncode == 2:
        # Didn't export (parse error or half-scaffolded project). Don't block —
        # `npx likec4 validate` in the skill workflow is the gate for parse errors.
        print(
            f"c4lint: skipped ({project_dir} does not export cleanly yet — likely mid-scaffold; run 'npx likec4 validate' when all files are written)",
            file=sys.stderr,
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
