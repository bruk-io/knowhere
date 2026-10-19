# Plan: plan drift outside the model

Spec: `../spec.md`, change 02. Delivers R5, R6.

## Files that change

- `plugins/philosophy/skills/review/SKILL.md`
- `plugins/philosophy/scripts/plan-drift`
- `plugins/philosophy/tests/test_plan_drift.py`
- `.github/workflows/plan-drift.yml`

## Order of work

1. R5: in `skills/review/SKILL.md`, step 3, state that a file changed outside the plan's Files that change, or a plan step skipped, is Important and never a Nit, with the reason: a plan is what the owner read before the build, so a change beyond it was not read. The Compliance bullet in step 2 stays as it is.
2. R6: write `scripts/plan-drift <branch> [--root DIR]`. Pure parts first: `build_branch(name)` returns `(slug, number)` for `build/<slug>/NN` (slug letters, digits, `-`; two-digit number) or None; `normalise(path)` is `posixpath.normpath` with a leading `./` dropped; `drift(changed, listed, plan_path)` returns the changed paths, normalised, that are neither listed nor the plan itself, in diff order. The edges: find the plan as the one file matching `intent/<slug>/plans/NN-*.md` in the working tree (none or several is exit 2), read its paths with `artefact.listed_paths`, take `git diff --name-only --no-renames -z <base>...<branch>` with `base` chosen as in `branch-diff` (`main`, else `origin/main`). Print one drifted path per line, then a final line giving the reason: the plan lists what the owner read, so a file beyond it was not read. Exit 0 none, 1 some, 2 it could not tell (not a build branch, no plan, git failed), with the reason on stderr.
3. R6: write `tests/test_plan_drift.py`: unit tests for the three pure functions (including `./a`, `a//b`, `x/../a`), and subprocess tests against a throwaway repository in the style of `test_branch_diff.py`: a branch that changes only listed files plus its plan exits 0; one extra file exits 1 and names it; a non-build branch name and a missing plan exit 2; a deleted listed file does not count as drift.
4. R6: add `.github/workflows/plan-drift.yml`: on `pull_request` (opened, synchronize, reopened, ready_for_review), one job `plan-drift`, run only when the head ref starts with `build/`. It checks out the head with `fetch-depth: 0`, creates a local branch of the head ref's name with `git checkout -B`, and runs `plugins/philosophy/scripts/plan-drift` on that name, with the name passed through `env:` so no workflow expression is inlined into a `run:` block. Permissions `contents: read`. Actions pinned to the same SHAs `checks.yml` uses.

## Risks

- The job is not a required check until the owner marks `plan-drift` required in branch protection after it has run once (spec, Areas of concern 1). Until then it informs and does not hold the merge. Stated in the PR.
- A build that adds a file to its plan in a later commit passes, because the check reads the plan at the branch tip. That is the build play's rule (step 5): the plan edit is in the diff and the owner is asked.
- A plan that lists a directory, not a file, reports every file under it as drift. Plans list one path per bullet by template, so this fails loud rather than open.
- A job skipped on non-build PRs reports as skipped, which GitHub counts as passing when the check is required.
- `plan-drift` does not import `branch-diff` (a hyphenated script is not importable); it repeats the two-line base choice. Its branch rule is stricter than `branch-diff`'s and uses `fullmatch`, so the trailing-newline finding (R15, change 07) cannot apply here.

## Proof

- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/run-check" fast` exits 0, with the new tests passing.
- `python3 plugins/philosophy/scripts/plan-drift build/loop-round-five/02` run on this branch exits 0.
- Adding a stray file to this branch locally makes the same command exit 1 and name it.
- The `plan-drift` job runs and passes on this PR.
