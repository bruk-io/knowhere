---
name: size-work
description: Size a piece of work by complexity, unknowns, and risk, and decide whether to split it or spike first. Use when estimating, choosing a size label, deciding whether work is too big to commit to, when unknowns dominate, or when someone asks how long something will take.
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" *)
---

# Size work

**Size is about predictability.** Large work tends to get split not because small
pieces are faster but because they land where we expect. When unknowns dominate, spiking first usually pays for itself.
Open questions are unknowns, so they count in the size. A question that blocks the work
is usually a task of its own, a spike or a design, and what it delivers is the answer
written down.

## The scale

Sizes are 1, 2, 3, 5, and 8, set as one `size-n` label.

- The value of a size is how predictable the work is, so the spread of outcomes matters
  more than the average.
- The default for work that lands at 8 or above is to split it before committing to it.
- Work is not re-sized mid-flight to correct the estimate. What was learned goes into
  the next sizing.
- A size is not a performance metric, is not comparable across teams, and is not
  adjusted because someone wants more done.

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" size` reports labels that break the
scale.

## Splitting

Each child gets its own finish line and re-enters the loop. Record the order between
children with `--dep`, and the reason in the notes. A blocking question becomes a spike
(`type: spike`) or a design task (`philosophy:record-decision`). Large or cross-team
work gets its requirements written down first (`philosophy:write-spec`), and the split
follows them.

`references/story-points.md` is the full reasoning, from Bruk's "How We (should) Use
Story Points". Read it when someone pushes back on sizing or asks for time estimates.
