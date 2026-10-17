---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-memory, capability]
---

Our repo has no CLAUDE.md; all our conventions live in AGENTS.md so Cursor, Codex and Claude Code share them, and that worked fine in Claude Code. Yesterday I added a CLAUDE.local.md with a few personal notes (my preferred test runner flags), and since then Claude Code acts as if the AGENTS.md conventions do not exist. My teammates, who have no CLAUDE.local.md, still see them. I am on Claude Code 2.1.300. What is going on, and what is the smallest fix?
