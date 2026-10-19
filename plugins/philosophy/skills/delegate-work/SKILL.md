---
name: delegate-work
description: Decide whether to hand work to subagents or parallel sessions, how to keep them from colliding, and which model and effort each piece gets. Use before spawning a subagent or a parallel session, when splitting work across agents, when writing a worker's brief, and when choosing a model or effort level for a task.
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" *)
---

# Delegate work

Follows Anthropic's "Parallel sessions and subagents" play.

**Decide the order.** Let dependencies drive sequencing. Parallelism is a choice worth
making deliberately, and isolation is what that choice costs. Isolation means whatever
the work shares, not only the working tree: tests that share a lock file on the host
collide across worktrees as well.

## How

- Before starting tasks in parallel, run
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" parallel <id> <id>...`. Tasks it
  reports share files or wait on each other, so they run one after another in a single
  session.
- Each parallel task gets its own worktree. Sequential work uses the working tree.
- Start with two or three parallel sessions, and add more only while their results can
  still be reviewed properly.
- Hand a worker a task ID and let it read the task. Its report belongs in the task
  notes.
- The brief carries the task, not rules about how to run checks, what to schedule, or
  how to sign commits. Hooks, scripts and tool policy carry the worker's process
  (`philosophy:learn-from-work`).
- Set `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` in the repository's settings `env` so the
  depth of delegation is enforced rather than remembered. This plugin does not set it.
- A job handed off again and again is worth a subagent definition, checked into the
  repository.

## Model and effort

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/board-check" route <id>` gives the model and
effort for a task, from its type, its size, and whether it was split. Pass both to the
subagent. The table is in `${CLAUDE_PLUGIN_ROOT}/scripts/board.py`, so it changes in
one place.

- The reviewer's model and effort are in its own definition.
- A sweep a script can do, such as a grep or a file list, needs no model. One that has
  to read, such as an inventory, goes where `board-check route --sweep` says.
- A worker never sizes: it reports what it found and the orchestrator decides.
- Nothing ranks above the orchestrator's model, so a leaf that fails there is stuck.
