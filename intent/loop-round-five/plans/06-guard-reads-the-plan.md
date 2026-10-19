# Plan: guard reads the plan as it is

Spec: `../spec.md`, change 06. Delivers R12, R13, R14.

## Files that change

- `plugins/philosophy/hooks/guard.py`
- `plugins/philosophy/tests/test_guard.py`

## Order of work

1. R12, R13, R14: write the tests first, each failing on `main` for the stated reason, in `test_guard.py`:
   - R12: a throwaway repository whose plan is committed as the second commit on the build branch (a code commit comes first) is denied, and the reason says the plan must be the branch's first commit since `origin/main`. With the plan in the first commit, the same edit goes ahead. Today the plan counts as committed once it is anywhere in HEAD.
   - R13: a plan that lists `./src//core.py` and `src/pkg/../util.py` permits edits to `src/core.py` and `src/util.py`; a `Repro:` bullet naming `./tests//test_core.py` freezes `tests/test_core.py`.
   - R14: `- **Repro:** \`tests/test_core.py\`` (and `**Repro**:`) is read by `repro_tests` as a repro bullet; `- Reproduce \`x.py\`` is not.
2. R13: add `normal(path)` (`posixpath.normpath` on the stripped path) and use it for the listed paths in `decide_edit` and for the repro paths in `repro_tests`, in place of `removeprefix("./")`.
3. R14: widen `REPRO` to accept `Repro:`, `**Repro:**` and `**Repro**:` after the bullet marker.
4. R12: in `edit_decision`, replace "the plan is in HEAD" with "the plan is in the first commit since the base". A new `first_commit_has(root, plan)` lists `git log --reverse --format=%H <base>..HEAD`, takes the first hash, and asks `git show --name-only --format= <hash>` whether the plan's path is among its files. `<base>` is `origin/main`, else `main`; with neither, it falls back to the old HEAD check, because a guardrail fails open. Rename `plan_committed` to `plan_first` in `decide_edit` and reword the deny reason to say what is checked: the plan must be in the branch's first commit since `origin/main`, and why (the plan comes first in the history, not only on disk). The frozen repro tests still come from the plan as it is in HEAD.

## Risks

- A repository with no `origin/main` and no `main` has no base to measure from. The check falls back to HEAD, so the guard is never stricter than it can justify; the fallback has a test.
- A build whose plan commit is later rebased or squashed away from the first position is denied until it is put back. That is the point of R12.
- `hooks/` sits under CODEOWNERS gates, so this build pauses on the owner's `@claude continue`.
- Rejected for this change: normalising symlinks. `edit_decision` already resolves the edited path; plan paths are repository-relative text, so `normpath` is enough.

## Proof

- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/run-check" fast` exits 0, with the new guard tests passing.
- The new R12, R13 and R14 tests fail on `main` and pass on this branch.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0.
- `python3 plugins/philosophy/scripts/plan-drift build/loop-round-five/06` exits 0.
