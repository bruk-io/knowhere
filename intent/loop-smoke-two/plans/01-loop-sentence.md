# Plan: add the loop sentence to docs/index.md

Spec: `../spec.md`, change 01. Delivers R1, R2, R3, R4.

## Files that change

- `docs/index.md`
- `intent/loop-smoke-two/plans/01-loop-sentence.md`

## Order of work

1. Insert one sentence directly under the plugin table in `docs/index.md`, before "Quick Links": "The philosophy plugin's loop runs from an intent to a merged change; see [the self-running loop](https://github.com/bruk-io/knowhere/tree/main/intent/self-running-loop)." (R1)
2. Confirm the diff holds only `docs/index.md` and this plan, so no CODEOWNERS-gated path is touched. (R2)
3. After the PR opens, reviews and auto-merges, record each handover on #32 as fired or not fired with links; if one does not fire, record the evidence before changing any workflow. (R3, R4)

## Risks

- The sentence lands in the wrong place: it goes directly under the table, with a blank line between.
- A gated path enters the diff: step 2 checks the diff before the PR is marked ready.
- A handover fails to fire: the evidence goes on #32 and any fix becomes its own intent.

## Proof

- `git diff --name-only main` lists only `docs/index.md` and this plan.
- `grep -n "self-running-loop" docs/index.md` shows the sentence directly after the table.
- `bash .github/scripts/check.sh fast`, the repository's declared fast check, exits 0.
