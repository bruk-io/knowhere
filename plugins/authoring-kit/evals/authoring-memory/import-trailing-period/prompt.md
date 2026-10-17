---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-memory, regression]
---

Our CLAUDE.md imports docs/conventions.md, but Claude Code behaves as if it has never seen that file: it keeps using npm and throwing from parser functions, both of which the conventions forbid. The import line looks right to me. Work out why the conventions are not reaching Claude and fix CLAUDE.md with the smallest change; keep the conventions in docs/conventions.md.
