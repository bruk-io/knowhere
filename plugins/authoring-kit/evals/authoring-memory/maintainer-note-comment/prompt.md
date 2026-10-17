---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-memory, regression]
---

Update our CLAUDE.md at the repo root: add a note for human maintainers under the "Use pnpm, never npm or yarn" line explaining that the line exists because our CI cache is keyed on pnpm-lock.yaml and a stray package-lock.json breaks the cache. The note is for people reading the file, not for Claude, and it must not cost Claude any context. Edit the existing file; do not restructure it.
