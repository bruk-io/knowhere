# Spec: fire the loop's next play on a trigger the action accepts

Intent: [intent.md](intent.md), by Bruk Habtu. Status: draft. Merging this file into
`main` approves it.

Applied: the philosophy constraints in force (owner mode; "mechanise the scaffolding,
never the core act": which intent or change runs stays in the `find` step and
`next-change`, never a model's call); `intent/self-running-loop/spec.md` R8, R9, R11,
R12 and R20, which this change amends or must keep holding; CODEOWNERS, which already
gates every path this touches; the pinned `claude-code-action`'s own source
(`src/github/context.ts`, `src/modes/detector.ts`, `src/modes/agent/index.ts`,
`src/github/validation/actor.ts` at `f27be6b65a4652f08a2ba3cff79114829b588967`), read
directly rather than guessed, to settle which event the action accepts and what it
checks once it does; GitHub's "Permissions required for GitHub Apps" table for the
dispatch endpoint's permission; and GitHub's "Triggering a workflow" page, which says
`workflow_dispatch` and `repository_dispatch` events always create workflow runs, the
exception to `GITHUB_TOKEN`-caused events creating none.

## Requirements

- **R1.** `intent-spec.yml` and `intent-build.yml`, and their copies in
  `plugins/philosophy/templates/github/`, each run as three jobs under one `on:` that
  lists both `push` (unchanged paths filter) and `repository_dispatch` (one
  `event_type` per workflow: `intent-spec`, `intent-build`). The `find` job
  (`if: github.event_name == 'push'`) keeps its existing diff logic unchanged. When it
  finds slugs, a `dispatch` job (`needs: find`) fires the matching
  `repository_dispatch`, sending the same compact JSON array string `find` already
  produces (`jq -Rcs`) as `client_payload.slugs`, a string field rather than a nested
  array, and the push `find` diffed as `client_payload.before` and
  `client_payload.sha` (`github.event.before` and `github.sha`), so the job that
  invokes `claude-code-action` (`if: github.event_name == 'repository_dispatch'`)
  can read its matrix with `fromJSON(github.event.client_payload.slugs)`, the same
  call shape `needs.find.outputs.slugs` already used. Every run of the action now
  has `repository_dispatch` as its triggering event, which `context.ts` accepts,
  instead of `push`, which it doesn't. The action job keeps the concurrency group per
  slug that today's job carries (`intent-${{ matrix.slug }}` and
  `build-${{ matrix.slug }}`), so two quick pushes, now two dispatches, still can't run
  the same intent's play twice at once (self-running-loop R9).
  `plugins/philosophy/templates/github/README.md`'s table row for each workflow is
  updated to say it runs in two hops (`find` on the merge, the action on `find`'s
  dispatch), so a repository that copies these templates doesn't read the old
  single-hop description as current.
- **R2.** The `dispatch` job has `contents: write`, which GitHub's permissions table
  lists as what installation tokens, the `GITHUB_TOKEN` among them, need for
  `POST /repos/{owner}/{repo}/dispatches`, and runs nothing but that call. `find`
  keeps `contents: read`, so the step that reads the diff can't write. No job gains a
  new secret, a PAT, or a permission wider than the action job in the same workflow
  already carries: `contents: write`, `pull-requests: write` and `id-token: write`, in
  both `intent-spec.yml` and `intent-build.yml`.
- **R3.** The job that invokes `claude-code-action` sets
  `allowed_bots: "github-actions[bot]"`. `prepareAgentMode` always calls
  `checkHumanActor` before running a prompt, and that check rejects any actor whose
  account type isn't `User` unless it's on `allowed_bots`. A `repository_dispatch`
  fired by a job's own `GITHUB_TOKEN` carries that token's actor, not the actor of
  whatever push caused the `find` job to run, so this is the identity to allow, not
  the Claude app's.
- **R4.** `intent/self-running-loop/spec.md` is reworded in three places to describe
  the two-hop relay instead of a single push-triggered run: R8 and R9 (each now reads
  "a push to main... fires the matching `repository_dispatch`, which runs
  `/philosophy:spec` (or `/philosophy:build`) in CI"), and R11's chaining sentence
  (the merge still starts `find` on `push`; `find`, not the merge, is what starts the
  action).
- **R5.** The job that invokes `claude-code-action` runs only what a merge to `main`
  started, because anyone with a write-scoped token can send `repository_dispatch` by
  hand, with no merge and no review, and the job runs Claude with
  `CLAUDE_CODE_OAUTH_TOKEN`. The job checks out `main` with its full history
  (`fetch-depth: 0`), and before the action step, a step fails the run unless the
  first three of these hold, and skips the action step, with the run staying green,
  unless the fourth does:
  - `client_payload.sha` is a commit on `main`, and `client_payload.before` is one of
    its ancestors;
  - the diff over that range, `git diff --name-only before sha` with the same filter
    `find` uses, touches each slug's trigger path: `intent/<slug>/intent.md` for
    `intent-spec`, and `intent/<slug>/spec.md` or a file under `intent/<slug>/plans/`
    for `intent-build`. It's the range `find` diffed, so a push of several commits,
    from a rebase merge or with the intent's change in an earlier commit, passes as it
    does in `find`;
  - each slug matches `^[a-z0-9][a-z0-9-]*$`;
  - `main` still calls for the play: for `intent-spec`, the intent has no `spec.md` on
    `main` and no `spec/<slug>` branch on the remote, so a replayed dispatch or a
    second push can't open a duplicate spec PR; for `intent-build`, `next-change` says
    `build`, which already treats a `build/<slug>/NN` branch as taken. A play that
    isn't due is the routine case, as `intent-build.yml` treats `next-change`'s exit 1
    today (`[ $code -le 1 ]`), so it's a skip, not a failure: a red run here would
    count against the CI failure rate the control bands watch (self-running-loop
    R19).

  The slugs and the sha reach shell steps through `env:`, never as an inline `${{ }}`
  in `run:`, in both workflows and their template copies. A dispatch that names no
  merge, or a merge that didn't touch the intent, fails; one for an intent whose next
  play is done or already taken starts nothing and passes. What it can't rule out is in Areas of concern 3.

## Design

### Why the action failed, precisely

`claude-code-action` v1 parses `github.context.eventName` in `parseGitHubContext`
(`src/github/context.ts`) and throws `Unsupported event type` for anything outside
two lists: the entity events (`issues`, `issue_comment`, `pull_request`,
`pull_request_review`, `pull_request_review_comment`) and the automation events
(`workflow_dispatch`, `repository_dispatch`, `schedule`, `workflow_run`). `push` is in
neither, so the step fails before it reads `prompt` at all; the find job's own diffing
logic was never the problem.

`build-continue.yml` (`issue_comment`), `claude-review.yml` (`pull_request`) and
`loop-bands.yml` (`schedule`, `workflow_dispatch`) already trigger on accepted events
and are unaffected. Only `intent-spec.yml` and `intent-build.yml`, with their template
copies, use `push` to run the action step itself, so they're the only workflows this
change touches.

### Choosing the event: a relay, not a swap

The intent named four candidates. `workflow_run` and a straight swap to
`pull_request` (`types: [closed]`, filtered on `merged: true`) both run the action in
a job whose triggering-event actor is whoever performed the merge: the identity the
Claude app's OAuth token merges as, which this repository has never had to name
precisely before (the only place that identity is allow-listed today,
`claude-review.yml`'s `"claude[bot],claude"`, covers PRs the bot *opens*, not merges
it completes). `workflow_run` also pulls `checkWritePermissions` into the same gate
(`prepare.ts` runs it for `isWorkflowRunEvent` as well as entity contexts), one more
unknown for no benefit, and it has no built-in channel for the slug list `find`
already computed: recovering it means re-deriving it or shipping an artifact.

`workflow_dispatch`, sent with one API call per slug, works but needs the caller to
name the workflow file and pass inputs one at a time. `repository_dispatch` takes one
JSON `client_payload` per call, so the whole slug array that `find` already produces
carries over unchanged, in the same shape the matrix already consumes
(`fromJSON(...)`). That is the smallest diff from the current design, and it's one of
the intent's own candidates, so this spec picks it.

The decisive advantage of relaying through a second, code-fired event, rather than
switching the whole workflow's trigger to an entity event (`pull_request` closed), is
that it decouples the action's human-actor check from the merge actor entirely.
The `dispatch` job's `GITHUB_TOKEN` fires it, so the dispatch's actor is GitHub
Actions' own, the same whoever or whatever merged the PR that started `find`. One
allow-list entry (R3) covers every future merge, by hand or by the Claude app's token
completing auto-merge, with nothing to learn about the Claude app's own bot identity.

The cost of the relay is a second way in. `repository_dispatch` doesn't come only from
`find`: any token with write access to the repository can send one, with whatever
payload it likes, and today's workflows write `matrix.slug` into `run:` scripts and
the prompt. So `find`'s dispatch carries the merge it saw, and the dispatched job
re-checks, from `main`, that the push is real, that it touched the intent, and that
the play is still due (R5), over the same range `find` diffed so the two never
disagree. The check is code, like the rest of the decision about
what runs, and it re-derives that decision rather than trusting the payload.

### What stays code, what the action now sees

`find` is untouched except for the new dispatch step: it still computes `slugs` from
the same `git diff --diff-filter` logic, under the same `push` trigger, with the same
paths filter. Nothing about *which* intent or change runs moves into the action's
judgement: `next-change` still picks the one change `/philosophy:build` builds, as
today. The dispatch is a transport hop, not a decision, and R5 ties each hop to the
merge that caused it.

Once the second job runs under `repository_dispatch`, `src/modes/detector.ts`
resolves `agent` mode unconditionally for it: `repository_dispatch` isn't an entity
event, so none of `detectMode`'s entity-only branches apply, and the function's final
line is an unconditional `return "agent"`. `prepare.ts`'s trigger check for agent mode
is just `!!context.inputs?.prompt`, which the workflow always sets
(`/philosophy:spec ${{ matrix.slug }}` or `/philosophy:build ...`). So the one gate
the action itself applies before Claude runs is `checkHumanActor` (R3), and nothing in
`parseGitHubContext`, `detectMode` or `prepare.ts` reads the triggering push's
original actor once the event is `repository_dispatch`. That is from reading the
source, not inferred.

### Delivery order

| Change | Delivers |
|---|---|
| 01 Relay `intent-spec.yml` and `intent-build.yml` (and their `plugins/philosophy/templates/github/` copies, README included) through `repository_dispatch`, with the dispatched job checking each run against the merge that caused it; reword `self-running-loop/spec.md`'s trigger wording to match | R1, R2, R3, R4, R5 |

One change: the workflow fix, the slug check that makes the new event safe, and the
spec wording they make true are the same edit in practice. All of it lands under
CODEOWNERS review whether it's one PR or two, and splitting it would only add a
second plan and a second build cycle, with no risk this intent's constraints ask to
isolate.

Change 01 can't be started by the loop either. Merging this spec pushes to `main`,
which fires `intent-build.yml` on `push`, the trigger this intent fixes, so its action
step fails with `Unsupported event type: push`. The owner runs
`/philosophy:build loop-trigger-events` by hand, as this spec was written by hand. Its
plan touches `.github/` and `intent/self-running-loop/spec.md`, both CODEOWNERS paths,
so under `self-running-loop/spec.md` R6 the build stops after committing the plan and
waits for the owner's `@claude continue` on its PR. That continuation does work today:
`build-continue.yml` runs on `issue_comment`, which the action accepts.

## Constraint mapping

| Intent constraint | Met by |
|---|---|
| Which intents and changes to run stays code (`find`, `next-change`), not a model's choice | R1 and R5: `find`'s diff logic and `next-change` are unchanged, the dispatch only relays what `find` decided, and the dispatched job re-checks it against the merge and `main` before anything runs |
| A merge made with the Claude app's token must still start the next workflow, which `GITHUB_TOKEN` events don't | Unchanged by this spec: R1 keeps `push` as `find`'s trigger. This already holds by construction (`self-running-loop/spec.md` R11): the Claude app's token is its own installation token, not the job's `GITHUB_TOKEN`, so GitHub's recursion guard, which only suppresses `GITHUB_TOKEN`-caused events, doesn't apply to it. `repository_dispatch` is one of the events a `GITHUB_TOKEN` may still trigger, so `find`'s dispatch starts the second job. Run 39160088692 shows `push` firing `find` for a human merge (PR #25, merged by `brukhabtu`); it isn't evidence for the bot-merge case, which this repository hasn't yet exercised live |
| Workflows run PR content only on `pull_request` (self-running-loop spec R20) | Not affected: R1 introduces no `pull_request_target` use anywhere |
| No wider token than now | R2: the same `GITHUB_TOKEN`, no new secret, no PAT; `find` stays read-only, and the `dispatch` job's `contents: write` is no wider than the action job's in both workflows. R5 binds every run of the action to a merge on `main`; what remains is Areas of concern 3 |
| This intent's own spec can't come from the loop until the fix lands, so the owner runs `/philosophy:spec` for it by hand | Met by this run itself; change 01's build is run by hand the same way (Delivery order) |
| A handover the next smoke test finds broken becomes its own intent | Procedural: the verification step below follows this; a broken handover it finds is scoped as its own intent, not folded into change 01's build |

## Open questions

- [x] Which event to use. Settled above: `repository_dispatch`, fired by a
      `dispatch` job once `find` has computed slugs, carrying them and the merge's sha
      as `client_payload`, and checked against `main` by the job it starts.
- [ ] Carried forward: whether the action's automation mode, given this event, runs
      the plugin's slash command from its prompt. Reading the source settles the
      mechanical half: `detectMode` resolves `agent` mode unconditionally for
      `repository_dispatch`, and agent mode's trigger check only requires a non-empty
      `prompt`, which these workflows always set, so the command does run. What
      can't be settled by reading code is whether `checkHumanActor`'s actor match
      (R3) and the rest of the live run hold up in practice. Change 01's build should
      verify this with a throwaway smoke-test intent, the same way `loop-smoke-test`
      verified the handovers before it: push the intent, watch `find` and `dispatch` run, and
      confirm the second job's action step reaches Claude's run rather than failing
      at `Unsupported event type` or at `checkHumanActor`. A failure at
      `checkHumanActor` is informative, not a design error: it will name the actual
      actor, and fixing R3's `allowed_bots` value is a one-line change.

## Areas of concern

1. **The intent cites R10 and R11 of `self-running-loop/spec.md` as "the design of
   the triggers"; the push-trigger wording this change actually makes stale is R8
   and R9, with R11 holding only the auto-merge chaining sentence.** R10 (every PR
   reviewed by `/philosophy:review`) doesn't mention `push` at all and needs no
   change. R4 rewords R8, R9 and R11's chaining sentence instead of R10. Owner: Bruk
   Habtu, to confirm this is what was meant before the build changes R8 and R9 rather
   than R10.
2. **R3's `allowed_bots` value rests on convention, not on this repository's logs.**
   `github-actions[bot]` is the identity GitHub Actions' documentation and common
   practice give a `GITHUB_TOKEN`-authenticated API call, but no run here has yet sent
   a `repository_dispatch` to show it. If it's wrong, the first live run fails at
   `checkHumanActor` naming the actual actor, and the fix is a one-line edit to
   `allowed_bots`. Owner: Bruk Habtu, flagged so that failure reads as expected on the
   first live run, not as a new bug.
3. **A dispatch can replay a real merge.** R5 rules out a dispatch with no merge
   behind it, but anyone with a write-scoped token can send one naming a genuine past
   merge, and if `main` still calls for that play, it runs without a fresh merge. The
   work is what the loop would do anyway (the spec an unspecced intent is due, or the
   change `next-change` names), and it runs under the same review and gates. Ruling
   this out too would need a secret the dispatch carries, or a protected environment
   that asks for an approval, which brings back a human step the loop removes.
   Owner: Bruk Habtu, to accept this or ask for one of those.
