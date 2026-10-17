---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-hooks, regression]
---

This directory is a Claude Code plugin I am building; hooks go in hooks/hooks.json and hook scripts under hooks/. At the start of every session, tell Claude that this repo runs its tests with `bun test` (never `npm test`) and that database migrations live in db/migrations. Subagents must get the same note. Put the hook script at hooks/repo-context.sh.
