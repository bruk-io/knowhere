# Intent: smoke-test the self-running loop's chaining

Author: Bruk Habtu. Status: draft.

## Problem

The self-running loop built in [intent/self-running-loop](../self-running-loop/intent.md)
has never run end to end on GitHub. Its spec's area of concern 3, chaining, is
unverified:

- Whether `intent-spec.yml` fires when an intent merges and `claude-code-action` runs
  `/philosophy:spec` from its prompt.
- Whether `claude-review.yml` reviews PRs opened by `claude[bot]`.
- Whether CODEOWNERS holds a spec PR for the owner.
- Whether a build PR with no gated path merges on its checks through auto-merge.
- Whether that merge, made with the Claude app's token, starts `intent-build.yml` again
  so `next-change` says done.

## Proposed outcome

One tiny, throwaway change goes through every handover, with the owner approving only
the intent and the spec. The change: add one sentence under the plugin table in
`docs/index.md` saying that the philosophy plugin's work loop starts from an intent,
linking to https://github.com/bruk-io/knowhere/tree/main/intent/self-running-loop. Each
handover is recorded as fired or not, with links.

## Affected users and systems

- knowhere's workflows: `intent-spec.yml`, `intent-build.yml`, `claude-review.yml`,
  `checks.yml`, `philosophy-evals.yml`.
- `docs/index.md`.
- The owner, who merges the intent and the spec.

## Constraints

- Exactly one change.
- It touches no path CODEOWNERS gates, so it merges on its checks alone.
- It is throwaway and gets reverted after the test.
- A handover that doesn't fire becomes a new intent with its evidence, not a fix made on
  the spot.

## Open questions

- [ ] Carried forward: whether each handover fires at all. Nobody can name this in
      advance; the run itself is the evidence, recorded as fired or not, with links,
      against each handover named in the Problem section above.
