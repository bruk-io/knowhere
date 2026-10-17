---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-hooks, regression]
---

This directory is a Claude Code plugin I am building; hooks go in hooks/hooks.json and hook scripts under hooks/. After every Write or Edit of a Python file, run `ruff check` on that file and make sure Claude sees the findings so it fixes them before moving on. Put the hook script at hooks/ruff-feedback.sh.
