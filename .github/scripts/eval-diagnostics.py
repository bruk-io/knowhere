#!/usr/bin/env python3
"""Print why each failed eval case failed: its graders' verdicts, then what its tools did.

    eval-diagnostics.py <results.json>

Reads the JSON `claude plugin eval --json` writes, and each failed run's trace from the
path recorded there (kept with --keep-temp). CI runs it when the eval step fails, so a
failure can be read from the log instead of guessed at.
"""

from __future__ import annotations

import json
import os
import sys


def blocks(event: dict) -> list:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, list) else []


def show_trace(path: str) -> None:
    if not os.path.exists(path):
        print("  (no trace at %s)" % path)
        return
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        for block in blocks(event):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                print("  tool:", block.get("name"), json.dumps(block.get("input", {}))[:200])
            elif block.get("type") == "tool_result" and block.get("is_error"):
                content = block.get("content")
                text = content if isinstance(content, str) else json.dumps(content)
                print("  ERROR:", text[:400].replace("\n", " "))
            elif block.get("type") == "text" and event.get("type") == "assistant":
                print("  said:", block.get("text", "")[:400].replace("\n", " "))


def main() -> int:
    try:
        with open(sys.argv[1], encoding="utf-8") as handle:
            results = json.load(handle)
    except (OSError, ValueError) as error:
        # The eval step died before writing its results: its own log above says why.
        print("no eval results to read (%s); see the eval step's output" % error)
        return 0
    for case in results.get("cases", []):
        for run in case.get("arms", {}).get("with", []):
            if run.get("passed"):
                continue
            print("== %s: score %s %s" % (case["name"], run.get("score"), run.get("error") or ""))
            for grader in run.get("graders", []):
                verdict = "pass" if grader.get("passed") else "FAIL"
                print(
                    "  grader %s %s: %s"
                    % (verdict, grader.get("name"), (grader.get("explanation") or "")[:300])
                )
                if not grader.get("passed") and grader.get("evidence"):
                    print("    judged:", str(grader["evidence"])[:300].replace("\n", " "))
            show_trace(run.get("tracePath") or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
