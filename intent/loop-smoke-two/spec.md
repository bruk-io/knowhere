# Spec: prove the repository_dispatch relay carries a change through every handover

Intent: [intent.md](intent.md), by Bruk Habtu. Status: draft. Merging this file into
`main` approves it.

Applied: the philosophy constraints in force (owner mode; the loop's merge-is-approval
handovers; "the scope is the deliverable"; "treat stuck as information"); CODEOWNERS,
read to confirm `docs/index.md` is ungated while `intent/*/spec.md` and `.github/` are
gated; `intent/loop-trigger-events/spec.md`, whose relay this test exercises. No
`REVIEW.md`, rules directory or LikeC4 model exists in this repository, so none applied.

## Requirements

- **R1.** `docs/index.md` gains one sentence directly under the plugin table, saying the
  philosophy plugin's loop runs from an intent to a merged change, and linking to
  https://github.com/bruk-io/knowhere/tree/main/intent/self-running-loop.
- **R2.** The change's PR touches `docs/index.md` and its own plan file under
  `intent/loop-smoke-two/plans/` only, so no path CODEOWNERS gates is in the diff and
  the PR merges on its required checks and resolved conversations alone.
- **R3.** Each handover is recorded on #32 as fired or not fired, with a link to the
  run, PR or merge that shows it. The handovers are: the intent merge dispatching
  `intent-spec`; the spec job running under `repository_dispatch` with
  `github-actions[bot]` as actor; the spec PR opened by `claude[bot]`, reviewed and held
  for the owner; the spec merge dispatching `intent-build`; the build PR opened,
  reviewed and auto-merged on its checks; and that merge starting the next dispatch.
- **R4.** A handover that does not fire is recorded on #32 with its evidence (run logs,
  event payload, actor) before any workflow is changed to fix it.

## Design

The test is the change. No new mechanism is built: the existing `find`, `dispatch` and
action jobs in `intent-spec.yml` and `intent-build.yml` run as shipped, and the one
change in the delivery order is a docs sentence small enough that any failure is the
relay's and not the change's.

`docs/index.md` is chosen because CODEOWNERS does not gate it, so the build PR exercises
the auto-merge path (R2) rather than waiting on the owner. The spec PR is gated by
`intent/*/spec.md`, so it exercises the hold path.

Recording (R3, R4) is a comment on #32 per handover, posted as each is observed, so the
evidence is captured while the runs and logs still exist. A failure stops the test at
that handover: the evidence goes on #32, and any fix becomes its own intent (the scope
is the deliverable).

The revert is a manual `git revert` of the merged build, made outside the loop after the
test. It is not a change in the delivery order, and its merge touches only
`docs/index.md`, so the relay finds no remaining change to build.

### Delivery order

| Change | Delivers |
|---|---|
| 01 add the loop sentence to docs/index.md | R1, R2, R3, R4 |

## Constraint mapping

| Intent constraint | Met by |
|---|---|
| Exactly one change in the spec's delivery order. | The Delivery order table lists change 01 only. |
| It touches no path CODEOWNERS gates, so it merges on its checks and resolved conversations alone. | R2 |
| It is throwaway and is reverted after the test, by hand and outside the loop, so the revert isn't a change in the delivery order. | Design: the revert is a manual `git revert` and has no row in the Delivery order. |
| A handover that doesn't fire is recorded with its evidence before anything is fixed. | R4 |

## Open questions

- [x] Carried forward: whether each handover fires is what this test finds out. R3 records
      the answer per handover on #32, so nothing in the spec waits on it.

## Areas of concern

1. **The spec job's own PR can only be observed, not controlled.** If the spec relay
   fails, this spec would not have been written by CI and the failure shows as a missing
   PR rather than a run. Owner: Bruk Habtu. Proposed: treat a spec written by hand as the
   evidence for that handover (R4), record it as not fired, and open a new intent for the
   fix.
