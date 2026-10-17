---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-skills, regression]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md. Add a /deploy skill that runs ./scripts/deploy.sh to push the current build to production.
