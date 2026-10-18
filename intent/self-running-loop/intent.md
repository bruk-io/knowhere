# Intent: a work loop that runs itself from intent

Author: Bruk Habtu. Status: draft.

## Problem

The philosophy plugin's work loop only runs when a model remembers to run it. Each step
is a skill the model has to discover, so steps get skipped, most of all by subagents,
which never receive the loop's table: `SessionStart` doesn't fire for them. The one
transition that holds is closing, because a hook and a script enforce it. On brig-seed
(about 12 tasks, most dispatched through Workflow scripts), `plan-change` worked every
time it was invoked, and was skipped once work went through Workflow dispatch. A task
with no acceptance criteria went through a full implement-and-review cycle before
`close-task` refused it.

The plugin also rebuilt PR review and approval inside a Backlog.md board (`close-task`,
the reviewer agent, `finish-moved`), and the board's own vocabulary (draft versus task,
`DRAFT-n` ids, bootstrapping a finish line) caused four of the six incidents in the
brig-seed report. It implemented the plays that are conversations and none of the plays
that are triggers: evals in CI, hooks as approval gates, CI/CD integration, and metric
detection. And it measures nothing, so whether it is used consistently can only be
answered by anecdote.

## Proposed outcome

Once an intent is merged, the work moves through Anthropic's AI-native SDLC plays on its
own: spec, plan, build with its feedback loop, PR review, merge. Each stage commits a
file the next stage reads, and each handover is triggered by a git event, not by a model
remembering. I am in the loop where the architecture is established (the spec) and where
it is enforced (CLAUDE.md, rules, skills, hooks, boundary checks, review policy, evals,
workflows). Work inside an approved architecture flows without me. When a metric breaches
its control band, the loop writes a new intent.

## Affected users and systems

- Me, as the originator of intents and the owner of the architecture in every
  repository I own.
- The philosophy plugin in knowhere: its skills, hooks, scripts, reviewer agent and
  rules.
- knowhere, which owns this intent and so runs it. It has no Claude workflows and no
  `CLAUDE_CODE_OAUTH_TOKEN` secret yet.
- Repositories that use the plugin, through the Claude GitHub integration
  (`claude-code-action` on the subscription token). Where it is set up today, it is the
  read-only review and `@claude` workflows.
- Subagents and CI runs, which must get the same process without a brief telling them.

## Constraints

- An intent belongs to the repository it lives in, and that repository runs it: its
  workflows, its token, its CODEOWNERS.
- No Backlog.md dependency, for now. The artefacts are files in git, and PRs.
- Process is invoked, never discovered: each play is a command that runs by hand or
  non-interactively in CI. Skills hold policy, triggered by concrete work, and a policy
  that must always hold has a hook or a check behind it.
- Validation logic is a script, never an instruction to a model. The board checks that
  still apply (plan shape, numbered requirements and their coverage, settled open
  questions) become checks on the artefact files.
- Triggers use the Claude GitHub integration on the subscription token, not an API key.
- Claude never approves its own work. Merges are the approvals, and a change to the
  architecture or its enforcement needs mine.
- One intent goes through end to end by hand before any handover is automated.
- The existing policy rules and skills (Python, code design, test layers,
  `python-idioms`) keep working.

## Open questions

- [x] Which repository runs the first intent end to end? knowhere: the intent lives
      here, so this repository runs it.
- [ ] Does CI draft the spec when an intent merges, for me to review, or do I write the
      spec in a session with Claude?
- [ ] Is `plan.md` its own PR, or the first commit of the build PR, given that I don't
      need to approve plans inside an approved spec?
- [ ] How is "touches the architecture" detected: CODEOWNERS paths with required
      code-owner review, a check that labels the PR, or both? Which paths?
- [ ] Which PRs merge without me: green checks, no Important review findings, and no
      architecture paths?
- [ ] Chaining: a PR opened by `claude[bot]` needs `allowed_bots` before the review
      workflow runs on it, and a merge made with `GITHUB_TOKEN` starts no further
      workflows. Verify both before relying on them.
- [ ] What happens to the board-based pieces (`board.py`, `close-task`, `record-check`,
      the reviewer agent, the step skills): rewritten for files, kept for repositories
      that have a board, or removed?
- [ ] Which metrics show this works? Candidates: time from intent merge to merged PR,
      share of PRs merged without me, review findings citing a policy (should fall to
      zero), spec changes after the first `plan.md` commit.
- [ ] Which eval cases come first? The brig-seed incidents are candidates.
