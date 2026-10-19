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

Create it as a Backlog.md document of type `specification` under `specs/`, then link it
from the intent with `--doc`:

```sh
backlog doc create "Spec: <intent title>" -t specification -p specs
backlog doc update <doc-id> --content "<the spec>"
backlog task edit <intent-id> --doc "<path to the spec>"
```

| Section | What goes in it |
|---|---|
| `Intent:` line | The intent's id. The problem stays on the intent and is not restated |
| `## Requirements` | Numbered (R1, R2, ...) and each checkable, so tasks can cite them |
| `## Policies applied` | Which policies shaped the requirements, and how |
| `## Areas of concern` | Where policies conflict or can't be met, for the policy owner |
| `## Open questions` | Each of the intent's, answered or carried forward with a reason |
| `## Design questions` | Each becomes a design task (`philosophy:record-decision`) |
| `## Out of scope` | What the spec deliberately leaves out |

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" spec <doc-id>` before asking for
approval, and fix what it reports.

## Approve it

The product owner checks that the spec solves the intent's problem and that each open
question is answered or carried forward. A tech lead joins for higher-risk work. Areas
of concern go to their policy owners before the work is split.

Record the approval as a note on the intent: `--append-notes "Spec approved by @name"`.
The commit is the record of who approved it and when.

## After approval

Split the work from the requirements, and have each leaf cite the requirement numbers
it delivers. `board-check spec <doc-id> --coverage` names any requirement no task cites.
A change to an approved spec after its children have started counts as a moved finish
line: add `finish-moved` to the intent with a note saying what changed and why.
