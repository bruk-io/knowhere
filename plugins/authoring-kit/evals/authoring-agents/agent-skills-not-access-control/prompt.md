---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-agents, regression]
---

This directory is a Claude Code plugin I am building; agents go in agents/<name>.md. It already has a skill at skills/doc-style/SKILL.md with our documentation conventions. Add an agent called docs-writer that writes and edits Markdown docs. It should always start with the doc-style conventions in hand, and it must not be able to use any other skill in the plugin or the project.
