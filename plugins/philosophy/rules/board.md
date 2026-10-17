---
paths:
  - "**/backlog/**"
commands:
  - backlog
---

# The board

Applies when reading or writing a Backlog.md board.

The board is the source. Intents, specs, tasks, plans, and decisions live as markdown in
the repository, and anything another system needs, such as a Jira ticket, is written out
from it. Backlog.md drops any frontmatter key it doesn't know on the next edit, so the
work loop adds no keys of its own. Body sections written by hand survive.

## What the keys mean here

- `type`: `intent` is the root of a piece of work, in the requester's words. `design`
  delivers a decision, `spike` delivers an answer, and `task` and `bug` deliver a change.
- `status`: `Draft` is written down but not accepted. `To Do` is accepted, `In Progress`
  is being done, and `Done` was closed by someone who did not do the work.
- `labels`: one `size-n` label, an area or two, and `finish-moved` once the acceptance
  criteria change after acceptance. Whoever
  changes them commits the change, the label, and a note saying why before the task
  goes to review.
- `assignee`: on an intent, the person with the problem. Otherwise, whoever does it.
- `dependencies`: what blocks it. The reason goes in the notes.
- `documentation`: on an intent with a spec, the spec's path.
- `references`: on a design task, the path to its decision.
- `modified_files`: the plan's files that change.

Promoting a draft changes its id from `DRAFT-n` to `TASK-n`, so nothing refers to a
draft by its id.

## Sections

- An open question is a checkbox under an intent's `## Open questions`. It is settled
  when it is ticked, or when its line says `Carried forward:` and why it can wait.
- Implementation notes hold the worker's report, the check output that
  `scripts/record-check` puts there, and approvals such as "Spec approved by @name".

## Checks

`board-check` asserts the allowed values and the section shapes, and each finding says
how to fix it. Exit 1 means findings and 2 means it could not read the board.

```sh
python3 "{plugin_root}/scripts/board-check"                # the whole board
python3 "{plugin_root}/scripts/board-check" ready TASK-1   # also: plan, spec, close
```

A task is closed with `scripts/close-task`, never by setting `Done` by hand. Real files
as the tool writes them are in `{plugin_root}/docs/board-examples.md`.
