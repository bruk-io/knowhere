---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-memory, regression]
---

This repo keeps its engineering conventions in AGENTS.md at the root, shared by every AI tool we use; it stays the single source of truth. We now also want two Claude Code-only notes: use plan mode for any change under src/billing/, and run `pnpm verify` before claiming a task is done. Update the Claude Code project memory so sessions get both the AGENTS.md conventions and those two notes, without duplicating the conventions anywhere. Write a CLAUDE.md at the repo root.
