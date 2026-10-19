---
name: plan-change
description: Write the plan for a single change before editing anything - the files that change, the order of work, the risks, and the proof - and challenge it until someone else could implement from it. Use before implementing a leaf task, when entering plan mode, or when a task has no plan.
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" *)
---

# Plan a change

Follows Anthropic's "Plan mode as the default starting point" play, for leaf tasks.

## Write it

Read the task, its intent (`backlog/intents/<name>.md`), its slice in
`backlog/plans/<name>.md`, and any spec or decision it references first. This plan is
for one change: the slices and their order are already decided in the intent's plan
(`philosophy:write-plan`), and this says how the change is made.

- The files that change go in `modified_files` (`--modified-file`).
- `--plan` holds `### Order of work`, `### Risks`, and `### Proof`. Proof names the
  checks that will show the change works (`philosophy:verify-work`).
- In a piece of work with a spec (`backlog/specs/<name>.md`), the plan names the
  requirements it delivers (R1, R2).

Plan mode is a good way to write it, because nothing can be edited until the plan is
approved. Then run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" plan <id>` and
fix what it reports.

## Challenge it

Before the plan is approved, ask what could break, which step carries the most risk,
and which alternatives were considered and rejected. Refine it until an engineer who
never saw the conversation could implement the change from the plan alone.

## When the work drifts

A plan that no longer matches the work is a signal. Note a small drift on the task with
`--append-notes` and update the plan. Stop on a large one and propose a split.
