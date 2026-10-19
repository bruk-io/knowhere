# Plan: deterministic evals

Spec: `../spec.md`, change 01. Delivers R1, R2, R3, R4.

## Files that change

- `plugins/philosophy/evals/subagent/subagent-gets-constraints/prompt.md`
- `plugins/philosophy/evals/subagent/subagent-gets-constraints/graders/mode-line-quoted.md`
- `plugins/philosophy/evals/review/review-checks-the-plan/graders/outside-plan-flagged.md`
- `plugins/philosophy/evals/spec/spec-flags-policy-conflict/graders/not-resolved-alone.md`
- `plugins/philosophy/evals/README.md`

## Order of work

1. R1: rewrite the subagent prompt so it names neither `[philosophy]` nor `Repository mode`: ask for the first line of any context the subagent was given at startup, or "none". Replace the LLM grader `mode-line-quoted.md` with a regex grader on the reply, `(?m)^\[philosophy\] Repository mode: (owner|guest)`. Only the hook's output can produce that string.
2. R2: replace `outside-plan-flagged.md` with a regex on `review.md` that matches a line naming `logger.py` and marked Important: `(?im)^.*\bimportant\b.*\blogger\.py\b.*$|^.*\blogger\.py\b.*\bimportant\b.*$`, excluding the closing `important=N nits=N` counts line (that line has no `logger.py`, so it cannot match).
3. R3: delete `not-resolved-alone.md`. `conflict-flagged.md` is already a regex requiring a numbered Area of concern naming the logging conflict and an `Owner:`, and becomes the case's failing grader alongside `spec-written`. No change to that file.
4. R4: in `evals/README.md`, add the rule: every case has a deterministic grader that can fail it, and no case fails on one LLM grade. Update the table rows to say what each case now checks (the subagent row: the reply matches the hook's line).

## Risks

- The regex grader on the subagent reply has no `target`. The default target for a `regex` grader without one is assumed to be the final answer, as for the `llm` graders it replaces. If the default is wrong the case fails in CI, not silently passes, because the regex needs a string only the hook produces. The CI run on this PR shows which.
- The R2 regex could match a Nit line that mentions "important" in prose. Accepted: the review play (change 02) states the Important rule, and the case's other grader, `holds-the-merge`, requires `important=N` with N >= 1.
- R3 gives up the judged half of the policy-conflict case (spec Areas of concern 2, decided by the owner's delegate). A spec that settles the conflict and also lists it passes. Recorded, not fixed here.
- `--runs 1 --threshold 1.0` is left as it is; lowering either would weaken the check.

## Proof

- `grep -rl "type: llm" plugins/philosophy/evals` prints nothing: no grader in any case is an LLM grader.
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/artefact-check" intent/loop-round-five` exits 0.
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/run-check" fast` exits 0.
- The evals workflow passes on the PR: `subagent-gets-constraints` and `review-checks-the-plan` pass on regex graders alone.
