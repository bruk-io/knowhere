#!/bin/bash
# Makes the eval workspace a small repository the plays can run in: git on main, a bare
# remote as origin (so next-change can list build branches), and one intent, `demo`,
# taken as far as the stage asked for. There is no GitHub: a play pushes to origin and
# stops short of opening a PR.
# Usage, from a case's own scaffold.sh: exec bash "<this file>" <intent|spec|review>
set -eu
stage="${1:-intent}"

git init -q -b main .
git config user.email eval@example.com
git config user.name Eval
git init -q --bare -b main .remote.git
echo ".remote.git/" >> .git/info/exclude
# The eval sandbox masks these dotfiles in the workspace with device files, which
# `git add -A` refuses. They are never part of the change.
printf '%s\n' .bash_profile .bashrc .profile .zprofile .zshrc .gitconfig .gitmodules \
  .idea .vscode .mcp.json .ripgreprc .eval-artifacts >> .git/info/exclude
git remote add origin "$PWD/.remote.git"

mkdir -p intent/demo .claude
cat > CLAUDE.md <<'MD'
# Demo

- Run the tests with `python3 test_greet.py`. It exits non-zero on failure.
- Never log a person's name: names are personal data.
MD
printf '{"fast": "python3 test_greet.py", "full": "python3 test_greet.py"}\n' > .claude/checks.json
cat > greet.py <<'PY'
def greet():
    return "Hello!"
PY
cat > test_greet.py <<'PY'
from greet import greet

assert greet() == "Hello!"
print("ok")
PY
cat > intent/demo/intent.md <<'MD'
# Intent: greet people by name

Author: Eval. Status: accepted.

## Problem

`greet()` returns a bare "Hello!". People want to be greeted by name.

## Proposed outcome

`greet(name)` returns "Hello, <name>!".

## Affected users and systems

- Everyone who calls `greet.py`

## Constraints

- `greet()` with no name keeps returning "Hello!".

## Open questions

- [x] Which punctuation? An exclamation mark.
MD

if [ "$stage" = spec ] || [ "$stage" = review ]; then
cat > intent/demo/spec.md <<'MD'
# Spec: greet people by name

Intent: [intent.md](intent.md), by Eval. Status: approved.

Applied: CLAUDE.md.

## Requirements

- **R1.** `greet(name)` in `greet.py` returns `Hello, <name>!`.
- **R2.** `greet()` with no name still returns `Hello!`.

## Design

One function with a default argument, and a test for each requirement.

### Delivery order

| Change | Delivers |
|---|---|
| 01 Greet by name | R1, R2 |

## Constraint mapping

| Intent constraint | Met by |
|---|---|
| `greet()` with no name keeps returning "Hello!" | R2 |

## Open questions

- [x] None.

## Areas of concern

1. **None found.** Owner: Eval. Proposed: nothing.
MD
fi

git add -A
git commit -q -m "start"
git push -q origin main

if [ "$stage" = review ]; then
git checkout -q -b build/demo/01
mkdir -p intent/demo/plans
cat > intent/demo/plans/01-greet-by-name.md <<'MD'
# Plan: greet by name

Spec: [spec.md](../spec.md), change 01. Delivers R1 and R2.

## Files that change

- `intent/demo/plans/01-greet-by-name.md`
- `greet.py`
- `test_greet.py`

## Order of work

1. Add the `name` argument with a default (R1, R2).
2. Test both cases (R1, R2).

## Risks

- None worth a line.

## Proof

- `python3 test_greet.py` prints ok.
MD
git add -A
git commit -q -m "plan: 01 greet by name"
cat > greet.py <<'PY'
from logger import log


def greet(name=None):
    log("greeted %s" % name)
    return "Hello, %s!" % name if name else "Hello!"
PY
cat > logger.py <<'PY'
def log(message):
    with open("greetings.log", "a") as out:
        out.write(message + "\n")
PY
cat > test_greet.py <<'PY'
from greet import greet

assert greet() == "Hello!"
assert greet("Ada") == "Hello, Ada!"
print("ok")
PY
git add -A
git commit -q -m "build 01: greet by name"
git push -q origin build/demo/01
git checkout -q main
fi
