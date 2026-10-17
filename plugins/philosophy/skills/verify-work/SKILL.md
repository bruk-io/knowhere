---
name: verify-work
description: Check work while doing it with the repository's own checks, so the evidence comes from the toolchain and not from Claude's account of it. Use while implementing, before saying any task is done, when fixing a bug, and when a change shows up in a UI.
---

# Verify work

Follows Anthropic's "Give Claude a feedback loop" play. The person who did the work
checks it as they go; that's expected and doesn't need to be asked for.

**Checks in tiers.** The worker runs what its change touches: its packages' tests and
the static checks. The reviewer runs the full check once, and CI confirms it. A full run
by all three is the cost of not choosing.

- The repository declares one command per tier in `.claude/checks.json`:
  `{"fast": "<the change's tier>", "full": "<the single full check>"}`. If it has no
  such commands, or a tier is spread across several, say so: one command per tier that
  exits non-zero on failure is the fix, and it is a task of its own.
- Before saying a task is done, run the change's tier:
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/record-check" <id> --tier fast`. It puts the
  command, its exit code and its own output on the task, so the evidence is the tool's,
  not an account of it. A check that isn't declared runs as
  `record-check <id> -- <command>`.
- Done is measured against the task's proof and acceptance criteria, stated as things a
  check can show, such as "all tests in test_status.py pass".
- For a bug, reproduce it as a failing test first and confirm it fails for the expected
  reason. Commit it, then record it with
  `record-check <id> --repro -- <the command that runs it>`. Fix the code without
  editing that test: `close-task` refuses if it changed.
- For UI work, implement, take a screenshot, compare it with the mock, and adjust. Two or
  three rounds is typical.
- A check that is wrong is a finding on the task, not a change to make now.

Whether the task closes is not decided here. That is `philosophy:close-work`.
