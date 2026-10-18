# Spec: a work loop that runs itself from intent

Intent: [intent.md](intent.md), by Bruk Habtu, accepted in #10. Status: draft. Merging
this file into `main` approves it.

Applied: the philosophy constraints (owner mode); `authoring-kit:choosing-extension-types`
for which extension type each piece is; Anthropic's AI-native SDLC playbook for the
artefacts, the handovers and the gates.

## Requirements

Artefacts and their checks

- **R1.** An intent lives at `intent/<slug>/` as `intent.md`, `spec.md`, and one
  `plans/NN-<change>.md` per change. The plugin ships a template for each.
- **R2.** `artefact-check` is a script, standard library only, that asserts each
  artefact's shape. Intent: its sections are present, and every open question is ticked
  or says `Carried forward:` and why. Spec: the header lists what was applied,
  requirements are numbered R1 to Rn with no gaps, every intent constraint appears in
  the constraint mapping, and every area of concern names an owner. Plan: it has Files
  that change, Order of work, Risks and Proof, and cites only R-numbers its spec
  defines. It exits 0 when clean, 1 with findings and 2 when it can't read the files,
  and each finding says how to fix it.
- **R3.** `artefact-check` runs as a required check on every PR that touches
  `intent/**`, and as a `PostToolUse` hook when Claude writes an artefact, so findings
  arrive while it is being written.

The plays, as commands

- **R4.** Each play is a skill that only a person or a workflow invokes
  (`disable-model-invocation: true`): `/philosophy:intent`, `/philosophy:spec <slug>`,
  `/philosophy:build <slug>` and `/philosophy:review <pr>`. Each runs the same by hand
  and in CI.
- **R5.** `/philosophy:spec` writes `spec.md` from an accepted intent. It applies the
  policy rules and skills in force and lists them in the header, maps every intent
  constraint to requirements, and flags a conflict between policies as an area of
  concern rather than resolving it.
- **R6.** `/philosophy:build` takes the next undelivered change, the first in the
  spec's delivery order with no plan on `main`, and works on the branch
  `build/<slug>/NN`. It commits the change's plan as the branch's first commit,
  implements it, and runs the repository's fast check (declared in
  `.claude/checks.json`) until it passes. It opens a PR that names the R-numbers it
  delivers, links the plan, and holds the check's command, exit code and last lines of
  output. If the plan's files include a gated
  path (R12), it stops after the plan commit, opens the PR, and asks me there; my
  `@claude` reply continues the build on the same branch, so the plan and its code
  still merge together.
- **R7.** `/philosophy:review` reviews a PR against `REVIEW.md` when there is one, and
  otherwise runs bugs, security and compliance passes, checking the diff against the
  intent, the spec and the plan. It never approves, and it returns the number of
  Important findings as structured output.

Triggers

- **R8.** A push to `main` that adds `intent/*/intent.md` runs `/philosophy:spec` in CI,
  which opens a spec PR for me.
- **R9.** A push to `main` that adds `intent/*/spec.md` or `intent/*/plans/*.md` runs
  `/philosophy:build` for the next change, until the delivery order is done. The next
  change is always the lowest-numbered one with no plan on `main`; if its build is
  already open, nothing starts, so a later change never builds on a base without the
  earlier one. Builds for one intent also run one at a time (a concurrency group per
  slug), so two quick pushes never start the same change twice.
- **R10.** Every PR is reviewed by `/philosophy:review`. The review check fails when the
  Important count is above zero, and it is a required check on `main`.

Gates

- **R11.** A PR merges without me only when every required check is green and
  CODEOWNERS asks for no review from me. The required checks are the artefact check,
  the review check, the eval run where the repository has evals (R17), and the
  repository's full check from `.claude/checks.json`, all run by CI so the evidence is
  the toolchain's, not the session's. The review workflow lists `claude[bot]` in
  `allowed_bots`, so it reviews the PRs the loop opens. The build job turns on
  auto-merge with the Claude app's token, so a merge the loop makes is made by
  `claude[bot]` and starts the next workflow; it is never made with `GITHUB_TOKEN`.
  Turning on auto-merge is not Claude approving its own work: GitHub merges only once
  every required check passes and CODEOWNERS asks for no one, so the approval is the
  spec I approved plus checks Claude can't loosen (R12). This gate is live from change
  06; until then `main` requires a PR and nothing more.
- **R12.** CODEOWNERS assigns `@brukhabtu` what starts work, what establishes the
  architecture and what gates the work, and `main` requires code-owner review. I accept
  each intent and approve the architecture once, in the spec, so a build that
  implements an approved spec needs no review from me. The paths: `intent/*/intent.md`
  and `intent/*/spec.md`; the gates themselves, so a build can't loosen what checks it
  (`.github/`, which holds the workflows and CODEOWNERS, `REVIEW.md`,
  `.claude/settings.json`, `.claude/checks.json`, `bands.yaml`, and in knowhere the
  code that does the checking: `plugins/*/hooks/`, `plugins/*/scripts/`,
  `plugins/*/evals/` and the review play, `plugins/*/skills/review/`, which the review
  gate runs); and a repository's architecture definitions (LikeC4 models and
  boundary configuration files). GitHub doesn't let me approve my own PRs, so mine
  merge through admin bypass, as `main`'s protection allows today.

- **R20.** Each workflow declares the minimal `permissions` its job needs. The
  `@claude` reply that continues a gated build (R6) acts only on a comment from
  `@brukhabtu`. `claude[bot]` is never a bypass actor on `main`.

Hooks

- **R13.** On a `build/<slug>/NN` branch, an edit to a file that is not in the plan's
  Files that change is denied. The reason names the fix: add the file to the plan in
  the same commit.
- **R14.** On a build branch whose plan names a repro test under Proof, an edit to that
  test is denied.
- **R15.** A subagent receives the standing constraints through `SubagentStart`, the
  same way a session does through `SessionStart`.

Removal

- **R16.** The board pieces are removed: `board.py`, `board-check`, `close-task`,
  `record-check`, `rules/board.md`, `docs/board-examples.md`, the reviewer agent, the
  step skills (`capture-intent`, `size-work`, `accept-work`, `write-spec`,
  `record-decision`, `plan-change`, `delegate-work`, `verify-work`, `close-work`,
  `learn-from-work`), the guard's close and reviewer logic, and their tests. The
  "Doing the work" section of `constraints.md` is rewritten for this loop. The policy
  rules and `python-idioms` stay as they are.

Evals and metrics

- **R17.** An eval suite for the commands lives in `plugins/philosophy/evals/` and runs
  with `claude plugin eval`. Its first cases come from the brig-seed incidents and this
  intent's own review: a build commits its plan before any code, a spec flags
  conflicting policies instead of resolving them, a review checks the diff against the
  plan, and a subagent in a build gets the constraints. It runs on every PR that
  touches `plugins/philosophy/`, and a drop in pass rate holds the merge.
- **R18.** `loop-metrics` reports, from git and PR history: the time from intent merge
  to spec PR, and from spec merge to the last build merge; the share of PRs merged
  without me; Important findings per PR and the policy each cites; and spec commits
  made after the first plan commit.
- **R19.** A scheduled workflow runs a deterministic control-band check (a rolling mean
  and σ, the Western Electric rules, thresholds in `bands.yaml`) over the CI failure
  rate and PR cycle time. At 2σ Claude diagnoses, read-only. At 3σ it opens a PR with a
  new `intent.md`.

## Design

### What each piece is

| Piece | Extension type | Why |
|---|---|---|
| intent, spec, plan | Files in git | Each stage commits a file the next stage reads |
| The four plays | Skills with model invocation off | A procedure that is invoked, never discovered |
| Python, code design, test layers | Path-scoped rules, unchanged | Constraints that must hold when those files are touched |
| `python-idioms` | Skill, unchanged | Judgement applied while writing |
| `artefact-check`, `loop-metrics`, the band check | Scripts | Validation is code, not an instruction to a model |
| Write-time artefact check, plan sync, repro guard, subagent constraints | Hooks | They must fire every time, with no judgement |
| Triggers | GitHub workflows on `claude-code-action` | A git event, not a model's memory, starts each stage |
| The gate on specs, gates and architecture definitions | CODEOWNERS plus required code-owner review | GitHub enforces it; no model decides it |

No agent is authored. The review's separation of duties comes from the workflow's tool
list and from branch protection, not from an agent definition.

### The loop

1. I describe a problem, and `/philosophy:intent` writes `intent.md` with me. I merge
   it.
2. The merge runs `/philosophy:spec` in CI. Its PR touches `intent/*/spec.md`, so it
   waits for me. I edit it and merge.
3. The merge runs `/philosophy:build` for change 01: the plan is the first commit,
   then the code, then a PR. The review runs. With green checks and no gated
   path, the PR merges on its own. With a gated path, the build stops after
   the plan and asks me in the PR; I reply with `@claude` to continue, and the PR waits
   for my review before it merges.
4. Each build merge runs the build for the next change, until the delivery order is
   done.
5. On a schedule, the band check watches the loop itself. A breach becomes a new
   intent.

Chaining: the build job turns on auto-merge with the Claude app's token, so the merge
is made by `claude[bot]` and starts the next workflow (R11). The review workflow lists
`claude[bot]` in `allowed_bots`, so it reviews the PRs the loop opens.

### Where things live

- `plugins/philosophy/skills/{intent,spec,build,review}/SKILL.md`: the plays.
- `plugins/philosophy/templates/`: the artefact templates, and workflow and CODEOWNERS
  templates for a repository to copy.
- `plugins/philosophy/scripts/`: `artefact-check`, `loop-metrics` and the band check,
  each a thin command over a pure core, as `board.py` was.
- `plugins/philosophy/hooks/`: `context.py` (adds `SubagentStart`) and `guard.py` (keeps
  `git init -b main`; adds plan sync and the repro guard). A hook finds the active plan
  from the branch name.
- knowhere's own `.github/workflows/` and `CODEOWNERS`: this repository runs this
  intent.

### Delivery order

This intent is the one that goes through by hand: each change below is built in a
session and lands as its own PR. The automation it delivers runs future intents.

| Change | Delivers |
|---|---|
| 01 Templates and `artefact-check`, with its PR check and write hook; confirm a plugin command runs from the action's `prompt` (concern 4) | R1, R2, R3 |
| 02 The four plays as commands | R4, R5, R6, R7 |
| 03 Remove the board pieces; rewrite "Doing the work"; subagents get the constraints | R15, R16 |
| 04 Plan sync and the repro guard | R13, R14 |
| 05 The eval suite | R17 |
| 06 CODEOWNERS, required checks, the review gate, workflow permissions | R10, R11, R12, R20 |
| 07 Triggers for spec and build | R8, R9 |
| 08 Metrics and control bands | R18, R19 |

The plays land before the board pieces go, so no change is built without a play to
build it. Evals come before the gates and the triggers, as the playbook's dependency
graph puts them before PR review and CI/CD. Most of this intent's changes touch gated
paths, because it builds the gates, so most of them wait for me; later intents mostly
won't.

## Constraint mapping

| Intent constraint | Met by |
|---|---|
| An intent belongs to its repository, which runs it | R8, R9, R12; workflows and CODEOWNERS live in the repository |
| No Backlog.md dependency | R1, R16 |
| Process is invoked, never discovered; a policy that must hold has a hook or check | R4, R13, R14, R15 |
| Validation logic is a script | R2, R3, R18, R19 |
| Triggers use the Claude GitHub integration on the subscription token | R8, R9, R10 |
| Claude never approves its own work; a merge without me needs green checks, no open Important finding, no gated path | R7, R10, R11, R12, R20 |
| One intent goes through by hand before automation | Delivery order: this intent is built by hand, and the triggers land last |
| The existing policy rules and skills keep working | R16 keeps them; R17 holds the merge if a change breaks them |

## Open questions

- [x] Who drafts a spec? CI, on the intent merge, and I review the PR (R8). This first
      spec was written by hand.
- [x] Is `plan.md` its own PR? No: it is the first commit of the build PR (R6).
- [x] How is a change to the architecture detected? CODEOWNERS (R12).
- [x] Which checks hold a merge without me, and how does an Important finding hold it?
      The artefact check, the review check failing on any Important finding, and the
      repository's own checks (R3, R10, R11).
- [x] What happens to the board pieces? They are removed (R16).
- [x] Which metrics? R18.
- [x] Which eval cases first? R17.
- [ ] Chaining. Carried forward: designed in "The loop", and verified as area of
      concern 3 before anything depends on it.

## Areas of concern

1. **A build can change policy without me.** Rules, skills and CLAUDE.md are not
   gated, so a build that implements an approved spec can change them. The checking
   code is gated (R12), so a build can't weaken what catches it, and a build that goes
   beyond its spec is caught by the plan-sync hook (R13), the review's compliance pass
   (R7, R10) and the evals (R17). Owner: Bruk. Proposed: accept it; if a review ever
   finds a policy change outside its spec, add that path to CODEOWNERS.
2. **CODEOWNERS works on whole files.** Boundary configuration inside `pyproject.toml`
   (such as `[tool.pypeeker]`) can't be singled out, and listing the whole file also
   gates dependency bumps. Owner: Bruk. Proposed: where a tool allows it, keep its
   boundary configuration in its own file; otherwise list `pyproject.toml` and accept
   the extra reviews.
3. **The chaining traps are unverified.** A PR that `claude[bot]` opens may not be
   reviewed until `allowed_bots` is set, and a merge made with `GITHUB_TOKEN` starts
   nothing. Owner: Bruk. Proposed: once changes 06 and 07 are on `main`, and before a
   real intent relies on the loop, run one throwaway intent through and watch each
   handover. Neither trap can be checked from a branch.
4. **Plugin commands in CI are unverified.** It isn't confirmed that
   `claude-code-action`'s `prompt` runs `/philosophy:spec <slug>` the same way typing it
   does, and R8 and R9 depend on it. Owner: Bruk. Proposed: change 01 checked the
   mechanism locally, with `claude -p` running a plugin command that has model
   invocation off; the first real trigger confirms it in CI. If it doesn't hold there,
   the prompt tells Claude to run the command by name.
5. **One subscription carries every CI run.** A long build chain can hit the
   subscription's limits partway through an intent. Owner: Bruk. Proposed: builds run
   one change at a time, as designed, and `loop-metrics` reports usage per intent.
6. **Removing `learn-from-work` drops its routing table**, which said where each kind
   of lesson goes. Owner: Bruk. Proposed: the playbook's two main routes cover it, a
   mistake made twice becomes a CLAUDE.md line and an incident becomes an eval case,
   with one line in `constraints.md` pointing at both.
7. **Without the board there is no cross-intent view.** Owner: Bruk. Proposed: nothing
   for now; `intent/` and the open PRs are the view. Revisit if two intents collide.
8. **The plugin can't install workflows into a repository.** Owner: Bruk. Proposed:
   ship them as templates; a command that sets a repository up is a follow-up intent.
