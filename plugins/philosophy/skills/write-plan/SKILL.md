---
name: write-plan
description: Write the plan for an accepted intent - the high-level slices in the order they land, what each depends on, and what a tester can see when each is done - then derive the child tasks from it. Use after an intent is sized and, for large work, its spec is approved, before any task is created; also when asked to sequence, slice or break down an intent.
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" *)
---

# Write the plan for an intent

The plan is the sequencing of one intent: the slices, their order, and what each depends
on. It is not the plan for a change, which is `philosophy:plan-change` and lives on a
leaf. The tasks are derived from the plan, not the other way round, so the order of the
work is decided once, in one place, before the work is cut into tasks.

## When

After the intent is accepted and sized (`philosophy:size-work`) and, for large or
cross-team work, after its spec is approved (`philosophy:write-spec`). Before any task
is created: `board-check` reports tasks that exist without a plan.

## Write it

Write `backlog/plans/<name>.md`, the same `<name>` as `backlog/intents/<name>.md`. It
needs a `title` in its frontmatter and a `## Slices` section, a numbered list in the
order the slices land:

```markdown
## Slices

1. **One claim.** A customer opens a claim and sees where it stands.
   Tester sees: the status, next step and expected date for a claim in each of its states.
   Depends on: none.
2. **All open claims.** A customer lists every open claim.
   Tester sees: three open claims, newest first.
   Depends on: slice 1.
```

- A slice is a piece that lands on its own and that a person can observe. "Build the
  API" is a layer, not a slice. Cut through the layers.
- `Tester sees:` says what a tester can observe when the slice is done. A slice nobody
  can observe can't be accepted, so `board-check` refuses one.
- `Depends on:` names earlier slices only. A dependency on a later slice means the
  order is wrong.
- Put the risky or unknown slice early, so what it teaches is in hand while the later
  slices are still cheap to change. A slice that is a question becomes a spike or a design
  task (`philosophy:record-decision`) under that slice.
- Keep it to sequencing. How one change is made belongs in that change's plan, and what
  is required belongs in the spec.

## Derive the tasks

Create one or more tasks per slice, as drafts, each carrying:

- the work's name as a label, and the slice as a `slice-n` label:
  `-l <name>,slice-1,size-3`;
- `--ref backlog/intents/<name>.md`, so a reader of the task finds the intent;
- `--dep` on the tasks of the slices it depends on, with the reason in the notes;
- the requirement numbers it delivers (R1, R2), when the work has a spec.

```sh
backlog task create --draft "<title>" --type task -l <name>,slice-1,size-3 \
  --ref backlog/intents/<name>.md --ac "<criterion> (R1)"
```

Every task in the work names its slice, and every slice has a task. Run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" plan <name>` and fix what it
reports. Each task then goes through the loop on its own: `philosophy:size-work`,
`philosophy:accept-work`.

## When the plan changes

A slice added, removed or reordered after tasks exist moves the finish line. Change the
plan, relabel the tasks, and add `finish-moved` to the intent's `labels` with a note
under `## Notes` saying what changed and why.
