---
name: write-spec
description: Write the requirements spec for large or cross-team work from its accepted intent - numbered requirements, the policies applied, areas of concern, and open questions - for product to approve before the work is split. Use when an intent is sized 8 or above, spans teams or platforms, needs product sign-off on the whole, or someone asks for a spec or PRD.
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" *)
---

# Write a spec

Follows the requirements half of Anthropic's "Requirements and design" play. The play's
spec holds the design as well. Here design stays with the engineers who will build it,
as decisions (`philosophy:record-decision`).

Most work needs no spec, because its acceptance criteria are its requirements. Write one
when the intent is sized 8 or above, when it spans teams or platforms, or when product
has to approve the solution as a whole before it is split.

## Write it

Draft it from the accepted intent, and apply the organisation's policy skills where they
exist, such as security, compliance, and UX. The play asks for a spec "ready to hand to
the engineering team" that will "describe clearly any areas of concern, especially where
you cannot satisfy contradicting policies".

Write it as `backlog/specs/<name>.md`, the same `<name>` as the intent's file
`backlog/intents/<name>.md`. The matching name is the link: no `Intent:` line, no doc
type, no key on the intent. Backlog.md does not manage the folder, so edit the file by
hand. It needs only a `title` in its frontmatter.

| Section | What goes in it |
|---|---|
| `## Requirements` | Numbered (R1, R2, ...) and each checkable, so tasks can cite them |
| `## Policies applied` | Which policies shaped the requirements, and how |
| `## Areas of concern` | Where policies conflict or can't be met, for the policy owner |
| `## Open questions` | Each of the intent's, answered or carried forward with a reason |
| `## Design questions` | Each becomes a design task (`philosophy:record-decision`) |
| `## Out of scope` | What the spec deliberately leaves out |

The problem stays on the intent and is not restated. Run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" spec <name>` before asking for
approval, and fix what it reports.

## Approve it

The product owner checks that the spec solves the intent's problem and that each open
question is answered or carried forward. A tech lead joins for higher-risk work. Areas
of concern go to their policy owners before the work is split.

Record the approval under `## Notes` in the intent file: `Spec approved by @name`. The
commit is the record of who approved it and when, and `board-check` reports tasks
that exist without the note, since the split waits for the approval.

## After approval

Plan the slices (`philosophy:write-plan`), then derive the tasks from them, and have each
leaf cite the requirement numbers it delivers. `board-check spec <name> --coverage` names
any requirement no task cites. A change to an approved spec after its tasks have started
counts as a moved finish line: add `finish-moved` to the intent's `labels` with a note
under `## Notes` saying what changed and why.
