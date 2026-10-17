---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-agents, regression]
---

This directory is a Claude Code plugin I am building; agents go in agents/<name>.md. Add an agent called migration-worker. I will spawn five of them at once, each converting a different module from JavaScript to TypeScript and committing its work. They must not step on each other's edits.
