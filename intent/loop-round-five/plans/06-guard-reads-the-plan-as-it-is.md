# Plan: guard reads the plan as it is

Spec: `../spec.md`, change 06. Delivers R12, R13, R14.

## Files that change

- `plugins/philosophy/hooks/guard.py`
- `plugins/philosophy/tests/test_guard.py`

## Order of work

1. R12: write tests that fail before the change. In the throwaway-repository tests, a plan committed as the second commit on the build branch (a code commit first) still denies an edit to a listed file; a plan in the branch's first commit allows it. The deny reason for the first case names the first commit since `origin/main`, not "alone".
2. R12: in `guard.py`, add a shell function `plan_in_first_commit(root, plan_path)`. It resolves the base (`origin/main`, else `main`; if neither resolves, it falls back to the old test, the plan present in HEAD, so a repository with no main is not locked out), takes the oldest commit of `git log --reverse --format=%H <base>..HEAD`, and asks whether `git show --name-only --format= <sha>` lists the plan. `edit_decision` passes that result as `plan_committed`. The frozen repro tests still come from `git show HEAD:<plan>`, so dropping a `Repro:` line from the plan does not unfreeze its test. The deny reason in `decide_edit` now reads that the plan must be in the first commit on the branch since `origin/main`, and why: the plan comes first in the history, not only on disk.
3. R13: write tests that fail before the change: a plan listing `src//core.py`, `src/x/../core.py` or `./src/core.py` allows an edit to `src/core.py`; the same spellings of a repro test freeze it. In `guard.py`, add a pure `normal(path)` (`posixpath.normpath` after stripping whitespace) and apply it to the listed paths and the repro paths, replacing both `removeprefix("./")` calls. The edited path reaches `decide_edit` already resolved, so it is compared as given.
4. R14: write the test that fails before the change: `- **Repro:** \`tests/test_core.py\`` names its test. In `guard.py`, `REPRO` accepts a bold label, `**Repro:**` or `**Repro**:`, as well as the plain one. The plan template's comment keeps saying `Repro:`; a bold label is read the same.

## Risks

- A build whose plan commit is not first (the plan added to a branch that already has commits) is now denied. That is the point of R12, and the deny reason says how: move the plan to the branch's first commit. `commit-change --plan-only` and the build play already produce that shape.
- `origin/main` is absent in a CI checkout that fetched only the PR branch. The fallback to `main`, then to HEAD presence, keeps the guard from failing closed; it is a guardrail and fails open by design.
- A normalised plan path that climbs out of the repository (`../x`) matches no edited path, so it permits nothing. That is the safe outcome.
- `hooks/` is gated by CODEOWNERS, so this build pauses on the owner's `@claude continue`.
- Rejected for this change: requiring the first commit to contain only the plan. `commit-change --plan-only` makes it so already, and R12 asks only that the plan's commit be first.

## Proof

- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/run-check" fast` exits 0 with the new tests passing.
- The new R12, R13 and R14 tests fail on `main` and pass on this branch.
- `python3 plugins/philosophy/scripts/artefact-check intent/loop-round-five` exits 0.
- `python3 plugins/philosophy/scripts/plan-drift build/loop-round-five/06` exits 0.
