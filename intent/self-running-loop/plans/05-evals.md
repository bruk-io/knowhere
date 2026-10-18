# Plan: the eval suite

Spec: [spec.md](../spec.md), change 05. Delivers R17.

## Files that change

- `intent/self-running-loop/plans/05-evals.md`
- `plugins/philosophy/evals/README.md`
- `plugins/philosophy/evals/_scaffold/demo-repo.sh`
- `plugins/philosophy/evals/build/build-plans-first/prompt.md`
- `plugins/philosophy/evals/build/build-plans-first/case.yaml`
- `plugins/philosophy/evals/build/build-plans-first/scaffold.sh`
- `plugins/philosophy/evals/build/build-plans-first/graders/code-written.md`
- `plugins/philosophy/evals/build/build-plans-first/graders/plan-commit-first.md`
- `plugins/philosophy/evals/build/build-plans-first/graders/code-committed.md`
- `plugins/philosophy/evals/spec/spec-flags-policy-conflict/prompt.md`
- `plugins/philosophy/evals/spec/spec-flags-policy-conflict/case.yaml`
- `plugins/philosophy/evals/spec/spec-flags-policy-conflict/scaffold.sh`
- `plugins/philosophy/evals/spec/spec-flags-policy-conflict/graders/spec-written.md`
- `plugins/philosophy/evals/spec/spec-flags-policy-conflict/graders/conflict-flagged.md`
- `plugins/philosophy/evals/spec/spec-flags-policy-conflict/graders/not-resolved-alone.md`
- `plugins/philosophy/evals/review/review-checks-the-plan/prompt.md`
- `plugins/philosophy/evals/review/review-checks-the-plan/case.yaml`
- `plugins/philosophy/evals/review/review-checks-the-plan/scaffold.sh`
- `plugins/philosophy/evals/review/review-checks-the-plan/graders/outside-plan-flagged.md`
- `plugins/philosophy/evals/review/review-checks-the-plan/graders/holds-the-merge.md`
- `plugins/philosophy/evals/subagent/subagent-gets-constraints/prompt.md`
- `plugins/philosophy/evals/subagent/subagent-gets-constraints/graders/mode-line-quoted.md`
- `plugins/philosophy/skills/review/SKILL.md`
- `plugins/philosophy/scripts/branch-diff`
- `plugins/philosophy/tests/test_branch_diff.py`
- `plugins/philosophy/skills/build/SKILL.md`
- `plugins/philosophy/README.md`
- `plugins/philosophy/CHANGELOG.md`
- `plugins/philosophy/tests/test_plugin.py`
- `.gitignore`
- `.github/workflows/philosophy-evals.yml`
- `.github/scripts/eval-diagnostics.py`

## Order of work

1. A shared scaffold, `_scaffold/demo-repo.sh`, that makes a small git repository
   with a bare remote as `origin`, an accepted intent, and, for later stages, its spec,
   a plan and a branch, so `next-change` and `git` behave as they do for real (R17).
2. Four cases, one per behaviour the spec names (R17):
   - `build-plans-first`: `/philosophy:build demo` makes the plan its branch's first
     commit, then commits the code. From brig-seed, where implementers never planned.
   - `spec-flags-policy-conflict`: `/philosophy:spec demo` where CLAUDE.md and the
     intent pull in opposite directions; the spec flags it as an area of concern with
     an owner instead of choosing a side.
   - `review-checks-the-plan`: `/philosophy:review` on a branch whose diff touches a
     file the plan doesn't list; the review reports it as Important, so its counts
     line holds the merge. From this intent's own review findings.
   - `subagent-gets-constraints`: a subagent quotes the mode line it was given, which
     only the `SubagentStart` hook can have put there. The original brig-seed bug.
3. Let the review skill take a branch as well as a PR number, so it runs by hand and
   in evals without GitHub. It reads the branch through `scripts/branch-diff`, which
   accepts only a plain branch name and runs git's diff with no external programs; a
   grant such as `git diff main...*` would also let options like `--output` through.
4. A workflow that runs the suite on every PR touching `plugins/philosophy/`, one run
   per case, failing below a pass-rate threshold (R17). Change 06 makes it required.
5. Run the suite once locally, one run per case, and record the result.
6. README, changelog, and `evals/results/` in `.gitignore`, with Python's bytecode
   (`__pycache__/`, `*.pyc`), which the tests and evals leave beside the scripts.

## Risks

- Each run is a full Claude session on the subscription, so the CI workflow runs each
  case once rather than the default three, and only when the plugin changes.
- The ordering check (plan committed before code) reads git's own reflog,
  `.git/logs/HEAD`, rather than the model's account of its commits. That needs the
  plan commit's message to be fixed, so the build skill names it: `plan: NN <title>`.
  A first local run used an LLM grader on a printed log instead; the build ran out of
  turns before printing it, which is why this changed.
- The case checks that the plan commit comes first, not that it holds only the plan.
  A git hook recording each commit's files was tried, and hooks don't run in CI's eval
  sandbox. The guard holds Edit and Write to the plan until it is committed; a shell
  command can still put another file in that commit.
- An LLM judge asked whether a review approved failed reviews whose verdict was "hold"
  in two CI runs of four, with the same text passing elsewhere. Whether the review holds
  the merge is read from its `important=N` line instead, the line the review gate reads.
- `claude plugin eval` runs scaffolds only with `--scaffold`, and the workflow has to
  pass it, with `--trust-plugin`, since the cases are this repository's own.

## Proof

- `claude plugin eval plugins/philosophy --scaffold --trust-plugin --allow-tools Bash
  Write Edit --runs 1 --ablation none --no-publish` runs all four cases, and its
  results are in the PR.
- `uv run --no-project --with pytest python -m pytest -q` in `plugins/philosophy`
  still passes.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0.
