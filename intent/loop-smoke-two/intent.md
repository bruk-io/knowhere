# Intent: prove the repository_dispatch relay carries a change through every handover

Author: Bruk Habtu. Status: draft.

## Problem

The loop's triggers were rebuilt to relay through `repository_dispatch` (intent
`loop-trigger-events`, #32), because claude-code-action refuses `push`. The relay's
first hop has run live, but no play has yet run from a dispatch. Unproven:

- whether the spec job's action runs under `repository_dispatch` with
  `github-actions[bot]` as the actor
- whether the spec PR from `claude[bot]` is reviewed and held for the owner
- whether a build PR auto-merges and its merge starts the next dispatch

## Proposed outcome

One tiny, throwaway change goes through every handover. The change: add one sentence
under the plugin table in `docs/index.md` saying the philosophy plugin's loop runs
from an intent to a merged change, linking to
https://github.com/bruk-io/knowhere/tree/main/intent/self-running-loop. Each handover
is recorded as fired or not, with links, on #32. The change is throwaway and is
reverted after the test.

## Affected users and systems

- knowhere's workflows: `intent-spec.yml`, `intent-build.yml`, `claude-review.yml`,
  `checks.yml`, `philosophy-evals.yml`
- `docs/index.md`
- the owner, Bruk Habtu

## Constraints

- Exactly one change.
- It touches no path CODEOWNERS gates, so it merges on its checks and resolved
  conversations alone.
- It is throwaway and is reverted after the test.
- A handover that doesn't fire is recorded with its evidence before anything is fixed.

## Open questions

- [ ] Carried forward: none named by the owner. Whether each handover fires is exactly
      what this test is run to find out.
