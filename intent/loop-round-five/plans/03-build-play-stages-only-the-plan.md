# Plan: build play stages only the plan

Spec: `../spec.md`, change 03. Delivers R7, R8.

## Files that change

- `plugins/philosophy/scripts/commit-change`
- `plugins/philosophy/tests/test_commit_change.py`
- `plugins/philosophy/skills/build/SKILL.md`

## Order of work

1. R7: write `scripts/commit-change <plan> -m <message> [--plan-only] [--root DIR]`. Pure parts first: `refused(path, ignored)` returns the reason a path may not be staged, or None: it is absolute or escapes the repository after normalisation, ends in `.pyc`, has a `__pycache__` component, or is in the set of gitignored paths; `to_stage(listed, plan_path)` returns the normalised, de-duplicated paths to stage, the plan first. The edges: read the listed paths with `artefact.listed_paths` (the plan must parse, else exit 2); ask `git check-ignore -z --stdin` which of them are ignored; skip a listed path that does not exist on disk and is not tracked (a file the change has not created yet), since there is nothing to stage; if any path is refused, print each with its reason and exit 1 before staging anything; otherwise `git add -A -- <paths>` and `git commit -m <message>`. `--plan-only` stages the plan alone, for the plan-first commit. The script has no amend option and passes no flag that could amend. Exit 0 committed, 1 refused or nothing to commit, 2 it could not tell (plan unreadable, git failed), with the reason on stderr.
2. R7: write `tests/test_commit_change.py`: unit tests for `refused` and `to_stage`; subprocess tests against a throwaway repository in the style of `test_branch_diff.py`: a change to listed files plus the plan commits exactly those and leaves a stray file unstaged and uncommitted; `--plan-only` commits the plan alone; a listed `.pyc`, a listed `__pycache__/x.py` and a listed gitignored file each exit 1, name the path, and make no commit; a listed path not yet created is skipped; a listed deletion is staged; a second run adds a new commit and leaves the first in place (never amends); a path such as `../x` is refused.
3. R7, R8: in `skills/build/SKILL.md`, change `allowed-tools`: drop `Bash(git add *)` and `Bash(git commit *)`, add `Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/commit-change" *)` and `Bash(git fetch origin main)`; keep `Bash(git checkout -b build/*)`, which already admits a start point. Step 2 reads: run `git fetch origin main`, then `git checkout -b build/$slug/NN origin/main`, so the build never starts from wherever HEAD is. Steps 3, 5 and 7 commit with `commit-change` (the plan with `--plan-only`), and say why: it stages only what the plan lists and never amends.
4. R8: confirm `next-change` is untouched and the existing `taken` behaviour still holds by running its tests.

## Risks

- `allowed-tools` patterns are prefix globs and cannot restrict arguments, so the script is the restriction: it takes a plan and a message, and stages only from the plan. A message is data to `git commit -m`, never parsed as an option, because it follows `-m` as one argument.
- A change that needs a file the plan does not list can no longer commit it by hand. That path already requires editing the plan in the same commit (build step 5), and `commit-change` stages what the edited plan lists (spec, Areas of concern 3).
- A plan that lists a directory stages every file under it, including untracked strays. Plans list one path per bullet by template, and `plan-drift` fails loud on a directory, so this is caught in CI.
- The script, `skills/build` and the tests sit under paths CODEOWNERS gates only for `scripts/`; the build play is not gated, but `scripts/` is, so this build pauses on the owner's `@claude continue`.
- `commit-change` does not import `branch-diff` or `plan-drift` (hyphenated scripts are not importable); it needs neither.

## Proof

- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/run-check" fast` exits 0, with the new tests passing.
- In a scratch repository, a stray untracked file next to a listed change stays out of the commit made by `commit-change`.
- `python3 plugins/philosophy/scripts/plan-drift build/loop-round-five/03` exits 0 on this branch.
- The `plan-drift` job passes on this PR.
