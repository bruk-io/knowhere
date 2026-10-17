---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-skills, regression]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md. Add a skill called service-status whose body includes, at load time, the output of a bundled script at skills/service-status/scripts/status.sh, then explains which services are unhealthy. Create the script too, as a stub that prints "ok".
