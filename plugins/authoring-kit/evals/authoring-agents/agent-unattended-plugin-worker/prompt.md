---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-agents, capability]
---

This directory is a Claude Code plugin I am building; agents go in agents/<name>.md. Add an agent called nightly-fixer that runs in the background, unattended, fixing lint errors across the repo while nobody is watching.
