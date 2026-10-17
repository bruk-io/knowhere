---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-skills, capability]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md. Add a /branch-summary skill that pulls in the current git branch name and the last five commit subjects when it loads, then summarises what the branch is about.
