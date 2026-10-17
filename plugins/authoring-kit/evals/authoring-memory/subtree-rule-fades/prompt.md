---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-memory, regression]
---

In our monorepo the line "Never run database migrations against the shared staging DB; use `make db-local`" lives in packages/api/CLAUDE.md. In long Claude Code sessions it is respected at the start, but after a while (often after the conversation gets compacted) Claude starts suggesting migrations against staging again, even when it is still working in packages/api. The root CLAUDE.md does not mention it. Why does the instruction fade, and where in Claude Code project memory should it live?
