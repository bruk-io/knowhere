---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-skills, capability]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md. Add a skill called deploy-target that, when it loads, shows the value of the DEPLOY_ENV environment variable and then tells me what that environment is for.
