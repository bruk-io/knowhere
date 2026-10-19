---
paths:
  - "**/backlog/**"
commands:
  - backlog
---

# The board

Applies when reading or writing a Backlog.md board.

The board is the source. Intents, specs, plans, tasks and decisions live as markdown in
the repository, and anything another system needs, such as a Jira ticket, is written out
from it. Backlog.md drops any frontmatter key it doesn't know on the next edit, so the
work loop adds no keys of its own to the files it manages. Body sections written by hand
survive.

## The layout

One piece of work has a name, such as `nux-ep2`: lowercase words joined by hyphens, not
starting like an id (`task-5`) or a `size-` or `slice-` label. The name pairs everything
that belongs to it.

```text
backlog/
  intents/<name>.md    the problem and when it is done
  specs/<name>.md      the requirements, numbered (large or cross-team work only)
  plans/<name>.md      the slices, in the order they land
  tasks/ drafts/ completed/ decisions/ ...   as Backlog.md keeps them
```

- `intents/`, `specs/` and `plans/` are plain markdown that Backlog.md does not manage:
  no ids, no `backlog` CLI, and it never rewrites them. Edit them by hand.
- The same file name in each folder is the pairing. There is no `Intent:` line in a
  spec and no `documentation:` key on anything.
- An intent has no task. Its frontmatter holds `title`, `status` (`Draft`, `To Do`,
  `In Progress` or `Done`), `assignee` (the person with the problem) and `labels` (the
  `size-n` label). Its body holds `## Problem`, `## Affected users and systems`,
  `## Done when` (checkboxes), `## Open questions` and, once reviewed, `## Notes`.
- Every task in the work carries the work's name as a label, and
  `references: backlog/intents/<name>.md` as a link for readers. Labels and references
  are keys Backlog.md keeps. A task created under another task with `-p` is in the work
  through its parent.
- The plan sequences the work and the tasks are derived from it. Each task also carries
  a `slice-n` label for the slice it comes from. A leaf's own `## Implementation Plan`
  stays on the leaf and says how that one change is made.

## What the keys mean here

- `type`: on a task, `design` delivers a decision, `spike` delivers an answer, and
  `task` and `bug` deliver a change. An intent is a file and has no type.
- `status`: `Draft` is written down but not accepted. `To Do` is accepted, `In Progress`
  is being done, and `Done` was closed by someone who did not do the work.
- `labels`: one `size-n` label, the work's name, a `slice-n` label, an area or two, and
  `finish-moved` once the acceptance criteria change after acceptance. Whoever
  changes them commits the change, the label, and a note saying why before the task
  goes to review.
- `assignee`: on an intent, the person with the problem. Otherwise, whoever does it.
- `dependencies`: what blocks it. The reason goes in the notes.
- `references`: on a design task, the path to its decision.
- `modified_files`: the plan's files that change.

Promoting a draft task changes its id from `DRAFT-n` to `TASK-n`, so nothing refers to a
draft by its id. An intent is accepted by changing its `status` from `Draft` to `To Do`
and committing it.

## Sections

- An open question is a checkbox under an intent's `## Open questions`. It is settled
  when it is ticked, or when its line says `Carried forward:` and why it can wait.
- A plan's `## Slices` is a numbered list, in the order the slices land. Each slice says
  `Tester sees:` what a person can observe once it is done, and may say `Depends on:`
  an earlier slice.
- Implementation notes hold the worker's report, the check output that
  `scripts/record-check` puts there, and approvals such as "Spec approved by @name". On
  an intent the same notes go under `## Notes`.

## Checks

`board-check` asserts the allowed values and the section shapes, and each finding says
how to fix it. Exit 1 means findings and 2 means it could not read the board. An intent,
spec or plan takes its name where a task takes an id.

```sh
python3 "{plugin_root}/scripts/board-check"                  # the whole board
python3 "{plugin_root}/scripts/board-check" ready nux-ep2    # also: plan, spec, close
```

A task or intent is closed with `scripts/close-task`, never by setting `Done` by hand.
Work on the old layout (an intent task, a spec doc linked by `Intent:` and
`documentation:`) still checks, and `scripts/migrate-layout` moves it. Real files as the
tools write them are in `{plugin_root}/docs/board-examples.md`.
