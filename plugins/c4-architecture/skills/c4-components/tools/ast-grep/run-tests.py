#!/usr/bin/env python3
"""Review gate for ast-grep rules. A rule is NOT "reviewed" until:
  (1) its test cases pass       — valid samples don't match, invalid ones do
  (2) it has been scanned against a real codebase and the matches inspected

Usage:
  python3 run-tests.py                 # (1) run the rule test suite
  python3 run-tests.py <codebase-dir>  # (1) + (2) scan a real codebase, tally by C4 kind

Rule id convention: "<c4-kind>__<framework>__<language>" (e.g.
controller__spring__java). The scanner maps ruleId.split('__') ->
[kind, framework, language]; this summary tallies by kind (split[0]).

Python 3.9+, stdlib only. Requires the ast-grep CLI (npm i -g @ast-grep/cli).
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AG = "ast-grep" if shutil.which("ast-grep") else "npx --yes @ast-grep/cli"


def main() -> int:
    print("== rule tests (valid/invalid gate) ==")
    # --skip-snapshot-tests: check ONLY that valid samples don't match and
    # invalid ones do (the correctness gate). Optional stricter range-regression:
    # generate committed snapshots with `ast-grep test -c sgconfig.yml
    # --update-all`, then drop this flag to also diff exact match ranges.
    gate = subprocess.run(
        f'{AG} test -c "{os.path.join(HERE, "sgconfig.yml")}" --skip-snapshot-tests',
        shell=True, cwd=HERE,
    )
    if gate.returncode != 0:
        print("GATE FAILED: fix rules before marking reviewed")
        return 1

    if len(sys.argv) > 1:
        codebase = sys.argv[1]
        print(f"\n== scan against {codebase} (inspect before trusting) ==")
        proc = subprocess.run(
            f'{AG} scan -c "{os.path.join(HERE, "sgconfig.yml")}" --json "{codebase}"',
            shell=True, capture_output=True, text=True,
        )
        try:
            matches = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            matches = []
        by_kind: dict = {}
        for m in matches:
            kind = str(m.get("ruleId", "")).split("__")[0]
            by_kind.setdefault(kind, []).append(m.get("text", ""))
        for kind in sorted(by_kind):
            names = list(dict.fromkeys(by_kind[kind]))  # ordered de-dupe
            print(f"  {kind:<11} {len(by_kind[kind])} -> {', '.join(names)}")
        print(f"  total: {len(matches)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
