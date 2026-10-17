---
name: authoring-agents
description: 'Use when creating, improving or debugging a Claude Code subagent - a reviewer, a worker, a background task - or one with the wrong tools, permissions or model, never delegated to, or delegating when it should not. Agent frontmatter has traps Claude gets wrong from memory (descriptions never delegated to, tool lists wider than the role, an agent that stops to ask mid-task, which setting wins), so load this before creating, reviewing, debugging or advising on any subagent, even a small one.'
---

# Subagent authoring reference

Before adding fields, invoke Skill(authoring-kit:choosing-extension-types): it gates whether the model should do this at all and confirms an agent is warranted.

The body below the frontmatter is the system prompt. A subagent gets that
prompt, basic environment details, the delegation message, the CLAUDE.md
hierarchy and a git status snapshot - none of the conversation, and not
the full Claude Code system prompt. Every authored agent should justify
itself through open-ended dispatch, boundary policy, preloaded context, or
parallelism.

The field reference is a table, not this page: run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" fields agent` for the type,
default and effect of every field, and its notes for which tools a subagent
never gets, which setting wins and how deep agents nest. The linter reports
mistakes, each with its reason, after every write. What follows is only the
judgement.

## Delegation

- **`description`** - The delegation trigger: write it like a dispatch
  rule. "Use proactively after code changes" style phrasing raises
  auto-delegation, but that is still the model's call: the description
  matches intent, and dispatch that must happen on an event is a hook's job.
- **`color`** - Set it on any agent used in parallel teams; costs nothing.

## Tool policy (the boundary)

This is the field pair that makes an agent an agent: policy here binds to
everything the agent is ever asked to do, including skills firing inside it.

- **`tools`** - Least privilege by role: reviewers read-only (`Read, Grep,
  Glob`); researchers add `WebFetch, WebSearch`; writers add `Write, Edit,
  Bash`.
- **`disallowedTools`** - Prefer a small denylist (`Write, Edit`) over a
  long allowlist when the agent needs almost everything.
- Both are tool-level, so a `Bash(...)` specifier narrows nothing (the
  linter flags it). To narrow one tool, use a settings deny rule or a
  `PreToolUse` hook; to pre-approve one command, a `permissions.allow`
  rule - which holds for the whole session, not only this agent.
- **`Agent`** - Subagents can spawn subagents, so leave `Agent` out, or
  disallow it, for a role that must not delegate - a reviewer that has to
  stay read-only, for one.
- Design agents to never need to ask the user mid-task. User-input forks
  belong in the main loop (a skill calling **AskUserQuestion** before
  dispatch), not the worker.
- **`permissionMode`** - `dontAsk` for an unattended agent that must not
  stall on a permission dialog. A mode is not how to allow some of a
  tool's calls and block others: that is the hook above - enforcement
  belongs in code.

## Context assembly

- **`skills`** - Preload is guaranteed knowledge before any task: the
  inverse of a skill's `context: fork`, same system, opposite direction of
  control. Conventions in the body that several agents need belong in a
  preloaded skill - one skill, many consumers. It is preloading, not
  access control: to stop the agent invoking other skills, leave `Skill`
  out of `tools` or put it in `disallowedTools`. A plugin skill named bare
  or qualified is a trade; the table's notes say what each form risks. The
  linter flags a preload that no longer resolves.
- **`memory`** - Pair it with body instructions to consult and update
  memory, or it sits unused. `project` is the usual choice: it travels
  with the repo.
- **`omitClaudeMd`** for workers that take everything from the delegation
  prompt; **`experimental.cacheTtl`** for long-lived agents with a large
  stable prompt.

## Execution profile and integration

- **`model`, `effort`** - Route exploration and mechanical work to cheaper
  models; this is the main cost-control lever. Low effort for search
  workers, high for review and architecture roles.
- **`maxTurns`** - Cap any autonomous or background agent as a runaway
  guard, and size the cap to the role's real task length: at the limit the
  work comes back partial.
- **`background`** - Leave unset for agents whose output the main loop
  blocks on.
- **`isolation: worktree`** - For parallel writers, so workers cannot
  trample each other's edits. Check in the table where the worktree
  starts from before relying on uncommitted or unmerged work.
- **`mcpServers`** - Reach for an inline definition to scope who can call
  a server, not to save context.
- **`hooks`** - The enforcement seam for conditional rules while this
  agent is active - see "Hooks in skills and agents" in the
  [hooks reference](../authoring-hooks/references/hooks-reference.md).

## Plugin agents

A plugin-distributed agent ignores some fields: the table marks which, its
notes say where to move what they did, and the linter flags them. Decide
before writing the role whether it can live without them. Its body reaches
files bundled with the plugin through the plugin-root variable - the same
notes say what expands there.
