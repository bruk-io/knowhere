---
name: close-work
description: How a task on the board is reviewed and closed by someone who did not do the work - judging the acceptance criteria against the evidence, filtering findings, and the close itself. Use when a person reviews a board task themselves, or when deciding whether a parent task or an intent can close.
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" *)
---

# Close work

Follows Anthropic's "AI in the PR review loop" play: the agent that wrote the code does
not approve it.

**Report everything, then filter.** Most of what a review finds is answered in the
closing notes and filed nowhere. A finding earns a task when there is a
realistic path to the failure, and it joins a queued task in the same area before it
gets one of its own; otherwise the board grows as fast as it closes.

## Who reviews

The `philosophy:reviewer` agent, or a person. If this session did the work, it hands the
task to the reviewer and says so.

## The review

1. Read the task, its intent (`backlog/intents/<name>.md`), its plan and notes, and any
   spec (`backlog/specs/<name>.md`) or decision it points to.
2. Run the full check once:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/record-check" <id> --tier full`. It puts the
   command, its exit code and its own output on the task. This is the reviewer's tier;
   the worker ran the fast one. If the check fixes or reformats files as it runs, that
   is a finding.
3. Judge each acceptance criterion against the evidence in the notes and the check
   output. A criterion with no evidence is not met. Tick each one that is met with
   `backlog task edit <id> --check-ac <n>` (an intent: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tick-intent" <name> <n>`), and leave the rest. Never reword one: a
   criterion that is wrong is a finding for whoever owns the finish line.
4. Run the review passes the repository defines. If it has a `REVIEW.md`, follow it.
   Otherwise check for bugs, for security problems, and for whether the change matches
   its plan and its intent. Rank findings by severity.
5. A change that departed from its plan is a finding to explain, not a failure on its
   own. The acceptance criteria decide whether it closes.

A finding that earns a task is filed as a draft, with the problem and its evidence in
the description and the outcome as its criteria
(`backlog task create --draft "<title>" --type bug -d "..." --ac "..."`).

## Closing

The close is a script, because by hand it comes out slightly different each time:

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/close-task" <id> --notes "<the verdict, and what happened to each finding>"
```

Its findings are facts, the same ones `board-check close <id>` reports without closing:
report them rather than re-deriving them. It refuses criteria or a `finish-moved` label
that differ from the last commit, so ticks are the only change a review can make to the
finish line. When it refuses, append the same notes with
`backlog task edit <id> --append-notes` and leave the status alone.

- A parent stays open while its children are, and an intent stays open while any task
  in the work is. When they're done, the parent closes against its own finish line, so
  the root closes on the outcome its author asked for and not on the list of things
  that got built. An intent is closed the same way, by name:
  `close-task <name> --notes "..."` sets `status: Done` in its file and puts the notes
  under `## Notes`. Tick its `## Done when` boxes as the review goes with
  `tick-intent <name> <n>...`, which ticks and changes nothing else.
- Tasks deferred on purpose move to a new intent that says what was deferred and
  why, so the work doesn't wait on tasks nobody plans to do now.
