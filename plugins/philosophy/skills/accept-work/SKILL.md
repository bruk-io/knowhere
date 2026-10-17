---
name: accept-work
description: Decide whether a draft on the board is understood well enough to start, and promote it if so. Use when asked whether a task or draft is ready, when promoting a Backlog.md draft, and before splitting or starting work on the board.
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" *)
---

# Accept work

Follows the human approval that Anthropic's playbook puts at each gate, where a person
approves an artefact before the next stage starts.

**Accepting is a separate decision from starting.** Before work is split or begun,
someone checks that it's understood well enough. This is the cheapest review there is,
because changing course here is editing a sentence.

## Check, then judge

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" ready <id>` asserts the mechanical
part, and each finding says how to fix it. Fix or report each one.

What the check can't judge is decided here:

- Each criterion can be judged from evidence by someone who didn't do the work.
- Each carried question can wait, for the reason its note gives.
- The size holds up (`philosophy:size-work`), and large or cross-team work has its spec
  (`philosophy:write-spec`).

A follow-up filed from a review is accepted like anything else. Its finish line names
the outcome rather than the mechanism the reviewer suggested, and it is sized when
someone has looked, not when it is filed.

When something is missing, say exactly what, and leave it as a draft.

## Who accepts

The size picks who, the same way it picks model and effort: the person doing the work
when it's small, a lead when the risk is higher. When that person is not Claude, say
what is ready and what is not, name who should decide, and stop.

## Promoting

`backlog draft promote <id>`. The commit is the record of who accepted it and when.
