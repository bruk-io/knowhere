---
name: reviewing-extensions
description: Review Claude Code extensions - skills, rules, subagents, CLAUDE.md, hooks or a whole plugin - for the judgement problems a linter cannot catch, with the lint findings folded in. Typed as /authoring-kit:reviewing-extensions, optionally followed by a path.
argument-hint: "[path]"
disable-model-invocation: true
context: fork
agent: authoring-kit:authoring-auditor
background: false
---

Audit the Claude Code extensions at: $ARGUMENTS

If no path follows the colon, audit the working directory, letting the linter
decide what counts as an artifact. If the working directory is the user's home
directory, its `.claude/` is their personal configuration, not a project: do
not audit it - report that no path was given and ask for one.

Report by severity, as your instructions say. Never edit.
