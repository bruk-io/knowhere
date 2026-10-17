---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-agents, regression]
---

This directory is a Claude Code plugin I am building; agents go in agents/<name>.md. Add an agent called ts-fixer that fixes TypeScript type errors in the files it is handed. Every time it edits a file, prettier must run on that file - mechanically, not because the agent remembers to.
