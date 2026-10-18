# Plan: plan sync and the repro guard

Spec: [spec.md](../spec.md), change 04. Delivers R13 and R14.

## Files that change

- `intent/self-running-loop/plans/04-plan-sync.md`
- `plugins/philosophy/hooks/guard.py`
- `plugins/philosophy/hooks/guard.sh`
- `plugins/philosophy/hooks/hooks.json`
- `plugins/philosophy/tests/test_guard.py`
- `plugins/philosophy/templates/plan.md`
- `plugins/philosophy/skills/build/SKILL.md`
- `plugins/philosophy/README.md`
- `plugins/philosophy/CHANGELOG.md`

## Order of work

1. The core in `guard.py`: from the branch name, the file's path in the repository, the
   change's plan and which repro tests are committed, decide an Edit, Write or
   NotebookEdit, since R13 holds every edit and a notebook is edited too (R13, R14). On
   any branch but `build/<slug>/NN` it decides nothing.
   - The change's own plan, `intent/<slug>/plans/NN-*.md`, is always editable.
   - With no plan yet, any other edit is denied: write the plan first. This is what
     makes the plan the branch's first commit.
   - A file the plan doesn't list is denied, and the reason says to add it to Files
     that change in the same commit and say why in the PR (R13).
   - A file outside the repository is left alone.
   - A test the plan's Proof names on a line starting `Repro:` is denied once it is
     committed: the repro is written and committed first, then the code is fixed
     without touching it (R14).
2. The shell reads the branch and repository root from git, finds and reads the plan,
   and asks git whether a repro test is in `HEAD`. `hooks.json` adds `Edit`, `Write`
   and `NotebookEdit` to the guard's matcher, and `guard.sh` passes their payloads to
   Python as well as `git init`.
3. Tests for each decision, and for the hook in a throwaway repository on a build
   branch.
4. A note in the plan template's Proof on the `Repro:` line a bug fix adds, kept in a
   comment so other plans carry no placeholder, and a line in the build skill on how a
   bug fix starts.
5. README and changelog.

## Risks

- The guard now starts Python and one git call on every Edit, Write and NotebookEdit. On any branch
  but a build branch it stops after that call.
- A shell command can still write a file the plan doesn't list. The guard is a
  guardrail, not a boundary; the review's compliance pass compares the diff with the
  plan.
- Matching is on exact repository-relative paths. A plan that lists a directory doesn't
  cover the files in it; the reason says to list each file.

## Proof

- `uv run --no-project --with pytest python -m pytest -q` in `plugins/philosophy`
  passes, including tests that on `build/x/01`: an edit with no plan is denied; the
  plan itself is allowed; a listed file is allowed; an unlisted file is denied with the
  fix in the reason; a repro test is allowed before its commit and denied after; and on
  `main` nothing is decided.
- The same suite passes under Python 3.9.
- `uvx ruff check --config plugins/philosophy/ruff.toml plugins/philosophy` is clean.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0.
