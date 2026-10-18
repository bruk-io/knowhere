# Intent: fire the loop's next play on a trigger the action accepts

Author: Bruk Habtu. Status: draft.

## Problem

Merging an intent or a spec doesn't start the next play. `intent-spec.yml` and
`intent-build.yml` trigger on `push` to main, and `claude-code-action` v1 refuses that
event.

Evidence: run https://github.com/bruk-io/knowhere/actions/runs/39160088692, after
`intent/loop-smoke-test` merged in #25. The find step selected `loop-smoke-test`, then
the action step failed in 0.4s with "Action failed with error: Unsupported event type:
push". At the pinned action
(`f27be6b65a4652f08a2ba3cff79114829b588967`, v1.0.252), `src/github/context.ts` accepts
a prompt only on `workflow_dispatch`, `repository_dispatch`, `schedule` and
`workflow_run`, or on an issue or PR event; anything else throws.

`intent-build.yml` has the same trigger. Its two runs so far
(https://github.com/bruk-io/knowhere/actions/runs/39159190492 and
https://github.com/bruk-io/knowhere/actions/runs/39159357041) skipped the action
because `next-change` said "taken" and then "done", so it has never reached the action
under `push` and would fail the same way.

## Proposed outcome

Merging an intent starts `/philosophy:spec`, and merging a spec or a change starts
`/philosophy:build`, on an event the action accepts. A new throwaway intent then
passes every handover the smoke test checks: the spec PR from `claude[bot]`, its
review, CODEOWNERS holding it, the build PR with its plan first and its run-check
evidence, auto-merge, and the next build starting from that merge.

## Affected users and systems

- `.github/workflows/intent-spec.yml` and `intent-build.yml`.
- Their copies in `plugins/philosophy/templates/github/` and that folder's README.
- The self-running-loop spec's design of the triggers (R10 and R11).
- The owner.

## Constraints

- Which intents and changes to run stays code (the `find` step and `next-change`), not
  a model's choice.
- A merge made with the Claude app's token must still start the next workflow, which
  `GITHUB_TOKEN` events don't.
- Workflows run PR content only on `pull_request` (self-running-loop spec R20).
- No wider token than now.
- This intent's own spec can't come from the loop until the fix lands, so the owner
  runs `/philosophy:spec` for it by hand.
- A handover the next smoke test finds broken becomes its own intent.

## Open questions

- [ ] Carried forward: which event to use. `workflow_run` chained off the
      push-triggered `find` job, `repository_dispatch` sent by the `find` job,
      `workflow_dispatch`, and `pull_request` closed with `merged: true` are all
      candidates, and each differs in which token can trigger it and what context the
      action gets. The spec settles this.
- [ ] Carried forward: whether the action's automation mode, given one of those
      events, runs the plugin's slash command from its prompt. Untested; the spec
      names how it gets verified.
