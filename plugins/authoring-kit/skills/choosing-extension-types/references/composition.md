# Composing the extension types - higher-order features

The features built *from* the five extension types: **orchestration** (run several
agents at once), **autonomous run-on** (the session continues on its own), and
**connectivity** (external events reach a live session). The selector
([SKILL.md](../SKILL.md)) cites this when the task is about *composing* extension types
rather than choosing one. This page holds only the choice between them; each
feature's docs page owns where it lives, how it is invoked, its syntax, what it
costs, its limits and its availability, and those change often.

## Quick reference

| Feature | Use it when | Not when | Built from |
|---|---|---|---|
| [Parallel subagents](https://code.claude.com/docs/en/agents) | the work splits into independent chunks that needn't talk and you want them done at once | workers must coordinate (→ agent teams), or the orchestration should be a repeatable script (→ workflows) | the subagent extension type, backgrounded and tracked through the tasks system |
| [Dynamic workflows](https://code.claude.com/docs/en/workflows) | scope outgrows a handful of subagents, or findings should be verified against each other (codebase-wide audit, large migration, cross-checked research) | one or two isolated investigations suffice (→ parallel subagents), workers need to talk (→ agent teams), or the run needs user input midway | subagents + a JS orchestration script |
| [Agent teams](https://code.claude.com/docs/en/agent-teams) | the work splits into independent tracks that still need to share discoveries and converge | tasks are sequential, single-file, or independent enough that subagents suffice | peer sessions + a shared task list + a mailbox + a lead |
| [/goal](https://code.claude.com/docs/en/goal) | substantial work has a verifiable end state and you don't want to press enter each turn | the end state isn't observable in the transcript (the evaluator runs no tools and reads no files), or the objective is compound (split it into sequential goals) | a prompt-based Stop hook + the small fast model as evaluator |
| [/loop](https://code.claude.com/docs/en/scheduled-tasks) | quick in-session polling or babysitting while you work on something else | the work must survive a closed session (→ the durable options on the same docs page), or should react to a pushed event (→ channels) | a bundled skill + the cron tools |
| [Channels](https://code.claude.com/docs/en/channels) | a session should react to the outside world, or be driven remotely | you want to poll on a timer (→ `/loop`) | a local MCP server + permission relay, packaged as a plugin |

The first three are orchestration and separate on two questions: **who holds the
plan, and do the workers talk?** `/goal` and `/loop` differ in **what fires the
next turn** - a condition or a clock. Channels are about **external signals
reaching a live session**.

## Orchestration - who holds the plan, do the workers talk

All three build on subagents and session workers (see
Skill(authoring-kit:authoring-agents)); they differ only in coordination.

| Model | Worker | Who holds the plan | Peers talk? | Shared state in |
|---|---|---|---|---|
| Parallel subagents | a delegated subagent | Claude, turn by turn | No - each reports to the conversation that spawned it | the spawning context |
| Dynamic workflows | a subagent | a script | No - cross-checked by the script | script variables |
| Agent teams | a full peer session | a lead session | **Yes** - mailbox + task list | the shared task list |

Where workers do not talk, partition the files they touch or isolate them in
worktrees so they don't collide. Agent teams are the only model where workers
talk, and teammates are not worktree-isolated, so partition there too. An
agent definition used as a teammate keeps its tools and body but not its
`skills` preload, so a role built on a preloaded skill belongs in a subagent
or a workflow.

## Channels - who can act through one

A channel whose server relays permission prompts lets anyone on its sender
allowlist approve or deny tool use in the session. Allowlist only senders you
would trust at the keyboard.
