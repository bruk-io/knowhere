---
name: learn-from-work
description: Turn what a piece of work taught into something that lasts - a follow-up task, a CLAUDE.md line, a rule, a skill, a hook or script, or an eval - rather than a chat message. Use when a task closes, when Claude or a worker repeats a mistake, when a review finds the same problem twice, and after an incident.
---

# Learn from work

Follows Anthropic's plays on the CLAUDE.md, skills as institutional knowledge,
continuous evals in CI, and closing the loop on metrics.

**Let learning outlive the task.** Discoveries are more useful as tests, rules, or docs
than as chat, and they go on the board as follow-ups rather than into the current change.

## Where each lesson goes

| What happened | Where it goes |
|---|---|
| Something worth doing turned up outside the task | A draft on the board, not a change now. Review findings follow the filter in `philosophy:close-work` |
| An unknown surfaced | A note on the task, so the next sizing is better |
| Claude made the same mistake twice | A line in the repository's CLAUDE.md, or a path-scoped rule if it only applies to some files |
| A worker broke a rule in its brief (run checks in the foreground, schedule nothing, size nothing, the commit trailer) | A hook, a script, or tool policy. A rule a worker has broken once moves out of the brief |
| A policy is applied inconsistently | A skill, signed off by the policy owner. A skill is advisory, so a policy that must always hold also needs a hook or a check |
| A check could have caught it | A lint rule, a hook, or a test, not prose |
| An incident or a regression | An eval case that stays in the suite |
| The finish line moved after the task was accepted | The `finish-moved` label and a note saying what changed and why, since nobody reads the diff. `board-check moved` lists the ones missed |

This says where a lesson goes. How to build that rule, skill, or hook well is the
`authoring-kit` plugin's job.
