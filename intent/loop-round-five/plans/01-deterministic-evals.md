# Plan: deterministic evals

Spec: `../spec.md`, change 01. Delivers R1, R2, R3, R4.

## Files that change

- `plugins/philosophy/evals/subagent/subagent-gets-constraints/prompt.md`
- `plugins/philosophy/evals/subagent/subagent-gets-constraints/graders/mode-line-quoted.md`
- `plugins/philosophy/evals/subagent/subagent-gets-constraints/graders/agent-called.md`
- `plugins/philosophy/evals/review/review-checks-the-plan/graders/outside-plan-flagged.md`
- `plugins/philosophy/evals/spec/spec-flags-policy-conflict/graders/not-resolved-alone.md`
- `plugins/philosophy/evals/README.md`

## Order of work

1. R1: rewrite the subagent prompt so it names neither `[philosophy]` nor `Repository mode`: ask for the first line of any context the subagent was given at startup, or "none". Replace the LLM grader `mode-line-quoted.md` with a regex grader on the reply (the default target, `last_message`), pattern `\[philosophy\] Repository mode: (owner|guest)`. Only the hook's output can produce that string once the prompt no longer names it. A `tool_used` grader, `agent-called.md`, requires the Agent call, so the line has to come back through a subagent, not straight from the parent's own `SessionStart` context. The grader's regex is JavaScript: no inline flags, no `^` without multiline, so the pattern is a plain contains-match.
2. R2: replace `outside-plan-flagged.md` with a regex on `review.md` (`target: { source: file, path: review.md }`, `flags: i`) that matches `logger.py` inside an Important section or on a line labelled Important: `#+[^\n]*\bimportant\b[^\n]*\n(?:(?!#)[^\n]*\n)*?[^\n]*logger\.py|\bimportant\b[^\n]*logger\.py`. The first branch covers the usual shape, a `## Important` heading with `logger.py` on a numbered line below it, up to the next heading; the second covers `**Important:** ... logger.py` on one line. A `logger.py` that appears only under `## Nits` doesn't match. JavaScript regex: no inline flags.
3. R3: delete `not-resolved-alone.md`. `conflict-flagged.md` is already a regex requiring a numbered Area of concern naming the logging conflict and an `Owner:`, and becomes the case's failing grader alongside `spec-written`. No change to that file.
4. R4: in `evals/README.md`, add the rule: every case has a deterministic grader that can fail it, and no case fails on one LLM grade. Update the table rows to say what each case now checks (the subagent row: the reply matches the hook's line).

## Risks

- The regex graders are JavaScript `RegExp`s: inline flags such as `(?m)` aren't supported, `flags: i` is the documented flag, and `last_message` is the default target (`claude plugin eval` docs). The patterns above are written for that.
- The R2 regex's second branch could match a Nit line that mentions "important" in prose next to `logger.py`. Accepted: the review play (change 02) states the Important rule, and the case's other grader, `holds-the-merge`, requires `important=N` with N >= 1.
- R3 gives up the judged half of the policy-conflict case (spec Areas of concern 2, decided by the owner's delegate). A spec that settles the conflict and also lists it passes. Recorded, not fixed here.
- `--runs 1 --threshold 1.0` is left as it is; lowering either would weaken the check.

## Proof

- `grep -rl "type: llm" plugins/philosophy/evals` prints nothing: no grader in any case is an LLM grader.
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/artefact-check" intent/loop-round-five` exits 0.
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/run-check" fast` exits 0.
- The evals workflow passes on the PR: `subagent-gets-constraints` and `review-checks-the-plan` pass on regex graders alone.
