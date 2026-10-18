# Intent: answer round five's review findings on the self-running loop

Author: Bruk Habtu. Status: draft.

## Problem

The fifth round of Claude review on the self-running-loop stack (PRs #14 to #18),
posted 2026-10-18 after GitHub restacked the branches, left findings that shipped
unanswered. Its two Important findings were real: committed `.pyc` files (fixed before
merge) and the one below on the subagent eval. By area:

- Evals: the subagent-gets-constraints case can pass without the `SubagentStart` hook
  firing at all, because an LLM grades a reply the subagent writes and the prompt hands
  it the literal `"[philosophy]"` prefix
  (https://github.com/bruk-io/knowhere/pull/18#discussion_r4308383986). The
  review-checks-the-plan case failed in CI on #21
  (https://github.com/bruk-io/knowhere/actions/runs/39158282444) because the review
  rated "logger.py is outside the plan" as a Nit: the review play never says whether a
  file outside the plan is Important, so the model's grade varies, and
  outside-plan-flagged is itself an LLM judge. With `--runs 1` and `--threshold 1.0`,
  one flaky LLM grade fails the required evals check (#18 review).
- The build play: `git add *` and `git commit *` let a build stage stray files and
  amend the plan-first commit (round four committed `.pyc` files exactly this way); the
  build branches from wherever HEAD happens to be rather than from `origin/main` (#15
  review).
- gated-paths: CODEOWNERS escapes (`\#`, `\ `) are read as comments or separators, so a
  rule written with one reads as ungated, failing open for a gate (#15 review).
- artefact-check: the templates' `<...>` placeholders pass the check everywhere except
  in open questions (Author, Applied, Owner, R1), and some tests depend on the live
  `intent/self-running-loop` files rather than fixtures (#14 review).
- The guard: its deny reason promises "first commit" though it only checks that the
  plan is committed somewhere; plan paths aren't normalised before comparison; a
  `**Repro:**` bullet is silently ignored (#17 review).
- Smaller: branch-diff's `$` anchor accepts a trailing newline; `eval-diagnostics.py`
  can raise `KeyError` and leaves a file handle open; the evals workflow's
  `chmod -R a+rX /tmp` is broader than the eval run needs (#18 review).

## Proposed outcome

Each finding above is fixed or rejected, with its reason written down, one change per
area. The evals check becomes deterministic enough to be a required check: no case
fails on the strength of a single LLM grade.

## Affected users and systems

- `plugins/philosophy`: `skills/build`, `skills/review`, its scripts, `hooks/guard.py`,
  and its evals.
- `.github/workflows/philosophy-evals.yml` and `.github/scripts/eval-diagnostics.py`.
- Anyone whose plugin PR in this repository waits on the evals check to merge.

## Constraints

- Validation logic is a script, never an instruction to a model.
- A check is never weakened to make it pass.
- The review play stays gated by CODEOWNERS.

## Open questions

- [ ] Carried forward: this is a design choice for the spec, not a fact this intent
      can settle. Is "a file outside the plan is always Important" the right rule for
      the review play, or should a plan-drift check outside the model (a script in
      CI) hold that line instead?
