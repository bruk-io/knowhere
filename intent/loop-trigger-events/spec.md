# Spec: fire the loop's next play on a trigger the action accepts

Intent: [intent.md](intent.md), by Bruk Habtu. Status: draft. Merging this file into
`main` approves it.

Applied: the philosophy constraints in force (owner mode; "mechanise the scaffolding,
never the core act" — which intent or change runs stays in the `find` step and
`next-change`, never a model's call); `intent/self-running-loop/spec.md` R8, R9, R11,
R12 and R20, which this change amends or must keep holding; CODEOWNERS, which already
gates every path this touches; the pinned `claude-code-action`'s own source
(`src/github/context.ts`, `src/modes/detector.ts`, `src/modes/agent/index.ts`,
`src/github/validation/actor.ts` at `f27be6b65a4652f08a2ba3cff79114829b588967`), read
directly rather than guessed, to settle which event the action accepts and what it
checks once it does.

## Requirements

- **R1.** `intent-spec.yml` and `intent-build.yml`, and their copies in
  `plugins/philosophy/templates/github/`, each split into two jobs under one `on:`
  that lists both `push` (unchanged paths filter) and `repository_dispatch` (one
  `event_type` per workflow: `intent-spec`, `intent-build`). The `find` job
  (`if: github.event_name == 'push'`) keeps its existing diff logic unchanged and,
  when it finds slugs, fires the matching `repository_dispatch`, sending the same
  compact JSON array string `find` already produces (`jq -Rcs`) as
  `client_payload.slugs` — a string field, not a nested array — so the job that
  invokes `claude-code-action` (`if: github.event_name == 'repository_dispatch'`)
  can read its matrix with `fromJSON(github.event.client_payload.slugs)`, the same
  call shape `needs.find.outputs.slugs` already used. Every run of the action now
  has `repository_dispatch` as its triggering event, which `context.ts` accepts,
  instead of `push`, which it doesn't.
  `plugins/philosophy/templates/github/README.md`'s table row for each workflow is
  updated to say it runs in two hops (`find` on the merge, the action on `find`'s
  dispatch), so a repository that copies these templates doesn't read the old
  single-hop description as current.
- **R2.** The `find` job's permissions grow from `contents: read` to `contents:
  write`. No workflow gains a new secret, a PAT, or a wider permission than some job
  in these two files already carries today. (Whether `contents: write` alone is
  enough for `POST /repos/{owner}/{repo}/dispatches`, or whether `actions: write` is
  also needed, isn't settled by GitHub's own docs — see Areas of concern.)
- **R3.** The job that invokes `claude-code-action` sets
  `allowed_bots: "github-actions[bot]"`. `prepareAgentMode` always calls
  `checkHumanActor` before running a prompt, and that check rejects any actor whose
  account type isn't `User` unless it's on `allowed_bots`; a `repository_dispatch`
  fired by a job's own `GITHUB_TOKEN` carries that token's own actor, not the actor of
  whatever push caused the `find` job to run, so this is the identity to allow — not
  the Claude app's.
- **R4.** `intent/self-running-loop/spec.md` is reworded in three places to describe
  the two-hop relay instead of a single push-triggered run: R8 and R9 (each now reads
  "a push to main... fires the matching `repository_dispatch`, which runs
  `/philosophy:spec` (or `/philosophy:build`) in CI"), and R11's chaining sentence
  (the merge still starts `find` on `push`; `find`, not the merge, is what starts the
  action).

## Design

### Why the action failed, precisely

`claude-code-action` v1 parses `github.context.eventName` in `parseGitHubContext`
(`src/github/context.ts`) and throws `Unsupported event type` for anything outside
two lists: the entity events (`issues`, `issue_comment`, `pull_request`,
`pull_request_review`, `pull_request_review_comment`) and the automation events
(`workflow_dispatch`, `repository_dispatch`, `schedule`, `workflow_run`). `push` is in
neither, so the step fails before it reads `prompt` at all — the find job's own
diffing logic was never the problem.

`build-continue.yml` (`issue_comment`), `claude-review.yml` (`pull_request`) and
`loop-bands.yml` (`schedule`, `workflow_dispatch`) already trigger on accepted events
and are unaffected. Only `intent-spec.yml` and `intent-build.yml` — and their template
copies — use `push` to run the action step itself, so they're the only files this
change touches.

### Choosing the event: a relay, not a swap

The intent named four candidates. `workflow_run` and a straight swap to
`pull_request` (`types: [closed]`, filtered on `merged: true`) both run the action in
a job whose triggering-event actor is whoever performed the merge — the identity the
Claude app's OAuth token merges as, which this repository has never had to name
precisely before (the only place that identity is allow-listed today,
`claude-review.yml`'s `"claude[bot],claude"`, covers PRs the bot *opens*, not merges
it completes). `workflow_run` additionally pulls `checkWritePermissions` into the
same gate (`prepare.ts` runs it for `isWorkflowRunEvent` as well as entity contexts),
one more unknown for no benefit, and it has no built-in channel for the slug list
`find` already computed — recovering it means re-deriving it or shipping an artifact.

`workflow_dispatch`, dispatched with one API call per slug, works but needs the
caller to name the workflow file and pass inputs one at a time; `repository_dispatch`
takes one JSON `client_payload` per call, so the whole slug array that `find` already
produces carries over unchanged, in the same shape the matrix already consumes
(`fromJSON(...)`). That is the smallest diff from the current design, and it's one of
the intent's own candidates, so this spec picks it.

The decisive advantage of relaying through a second, code-fired event rather than
switching the whole workflow's trigger to an entity event (`pull_request` closed)
is that it decouples the action's human-actor check from the merge actor entirely.
`find`'s `GITHUB_TOKEN` fires the dispatch, so the dispatch's actor is GitHub
Actions' own — the same regardless of who or what merged the PR that started `find`.
One allow-list entry (R3) covers every future merge, whether it's made by hand or by
the Claude app's token completing auto-merge, with nothing to learn about the Claude
app's own bot identity.

### What stays code, what the action now sees

`find` is untouched except for the new dispatch step: it still computes `slugs` from
the same `git diff --diff-filter` logic, under the same `push` trigger, with the same
paths filter. Nothing about *which* intent or change runs moves into the action's
judgment — `next-change` still picks the one change `/philosophy:build` builds, same
as today. The dispatch step is a transport hop, not a decision.

Once the second job runs under `repository_dispatch`, `src/modes/detector.ts`
resolves `agent` mode unconditionally for it: `repository_dispatch` isn't an entity
event, so none of `detectMode`'s entity-only branches apply, and the function's final
line is an unconditional `return "agent"`. `prepare.ts`'s trigger check for agent mode
is just `!!context.inputs?.prompt`, which the workflow always sets
(`/philosophy:spec ${{ matrix.slug }}` or `/philosophy:build ...`). So the one
remaining gate before Claude runs is `checkHumanActor` (R3), and nothing in
`parseGitHubContext`, `detectMode` or `prepare.ts` reads the triggering push's
original actor at all once the event is `repository_dispatch` — confirmed by reading
the source, not inferred.

### Delivery order

| Change | Delivers |
|---|---|
| 01 Relay `intent-spec.yml` and `intent-build.yml` (and their `plugins/philosophy/templates/github/` copies, README included) through `repository_dispatch`; reword `self-running-loop/spec.md`'s trigger wording to match | R1, R2, R3, R4 |

One change: the workflow fix and the spec wording it makes true are the same edit in
practice, both land under CODEOWNERS review regardless of whether they're one PR or
two, and splitting them would only add a second plan and a second build cycle with no
risk this intent's constraints ask to isolate.

This change's own plan touches `.github/` and `intent/self-running-loop/spec.md`,
both CODEOWNERS paths. Under `self-running-loop/spec.md` R6, the build stops after
committing the plan, opens the PR, and waits for the owner's `@claude continue`
there — the same gated-path stop every build on a gated path takes, not a symptom of
the bug this intent fixes.

## Constraint mapping

| Intent constraint | Met by |
|---|---|
| Which intents and changes to run stays code (`find`, `next-change`), not a model's choice | R1 — `find`'s diff logic and `next-change` are unchanged; the dispatch step only relays what `find` already decided |
| A merge made with the Claude app's token must still start the next workflow, which `GITHUB_TOKEN` events don't | Unchanged by this spec — R1 keeps `push` as `find`'s trigger. This already holds by construction (`self-running-loop/spec.md` R11): the Claude app's token is its own OAuth/installation token, not the job's `GITHUB_TOKEN`, so GitHub's recursion guard, which only suppresses `GITHUB_TOKEN`-caused events, doesn't apply to it. Run 39160088692 shows `push` firing `find` for a human merge (PR #25, merged by `brukhabtu`); it isn't evidence for the bot-merge case, which this repository hasn't yet exercised live |
| Workflows run PR content only on `pull_request` (self-running-loop spec R20) | Not affected — R1 introduces no `pull_request_target` use anywhere |
| No wider token than now | R2 — same `GITHUB_TOKEN`, no new secret, no PAT; the added `contents: write` (exact sufficiency unconfirmed, see Areas of concern) is no wider than what `intent-build.yml`'s existing job already carries |
| This intent's own spec can't come from the loop until the fix lands, so the owner runs `/philosophy:spec` for it by hand | Met by this run itself |
| A handover the next smoke test finds broken becomes its own intent | Procedural — the verification step below follows this; a broken handover it finds is scoped as its own intent, not folded into change 01's build |

## Open questions

- [x] Which event to use. Settled above: `repository_dispatch`, fired by the `find`
      job once it has computed slugs, carrying them as `client_payload`.
- [ ] Carried forward: whether the action's automation mode, given this event, runs
      the plugin's slash command from its prompt. Reading the source settles the
      mechanical half — `detectMode` resolves `agent` mode unconditionally for
      `repository_dispatch`, and agent mode's trigger check only requires a non-empty
      `prompt`, which these workflows always set — so the command does run. What
      can't be settled by reading code is whether `checkHumanActor`'s actor match
      (R3) and the rest of the live run hold up in practice. Change 01's build should
      verify this with a throwaway smoke-test intent, the same way `loop-smoke-test`
      verified the handovers before it: push the intent, watch `find` dispatch, and
      confirm the second job's action step reaches Claude's run rather than failing
      at `Unsupported event type` or at `checkHumanActor`. A failure at
      `checkHumanActor` is informative, not a design error — it will name the actual
      actor, and fixing R3's `allowed_bots` value is a one-line change.

## Areas of concern

1. **The intent cites R10 and R11 of `self-running-loop/spec.md` as "the design of
   the triggers"; the push-trigger wording this change actually makes stale is R8
   and R9, with R11 holding only the auto-merge chaining sentence.** R10 (every PR
   reviewed by `/philosophy:review`) doesn't mention `push` at all and needs no
   change. R4 rewords R8, R9 and R11's chaining sentence instead of R10. Owner: Bruk
   Habtu — confirm this is what was meant before the build changes R8/R9 rather than
   R10.
2. **Two values in this spec rest on community convention rather than a quoted
   GitHub doc, and both fail loudly and recoverably if wrong.** R3's `allowed_bots`
   value, `github-actions[bot]`, is the identity GitHub Actions' own documentation
   and near-universal community convention name for a `GITHUB_TOKEN`-authenticated
   API call, not a value read off this repository's own Actions logs — no run here
   has yet fired a `repository_dispatch` to check it. R2's `contents: write` for the
   `find` job came the same way: GitHub's REST reference for
   `POST /repos/{owner}/{repo}/dispatches` names the classic `repo` OAuth scope, not
   a fine-grained or `GITHUB_TOKEN` job permission, so `contents: write` is read off
   common practice, not a quoted doc line; `actions: write` is the fallback if it's
   403'd. Either way the first live run names the actual actor or the actual missing
   permission in its own error, and the fix is a one-line edit to `allowed_bots` or
   to `permissions:`. Owner: Bruk Habtu — flagging so either failure mode on the
   first live run reads as expected, not as a new bug.
