---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-rules, regression]
---

I start Claude Code with `claude --add-dir ../shared-lib`. The shared-lib repo has its own .claude/rules/ with path-scoped rules and a CLAUDE.md, and I can read and edit its files fine from my session, but none of its rules ever load even when I edit a file they match. The same rules load when I open shared-lib directly. How do I get them to load from my main project?
