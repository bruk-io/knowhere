---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-hooks, capability]
---

This directory is a Claude Code plugin I am building; hooks go in hooks/hooks.json and hook scripts under hooks/. I never want Claude to run `rm -rf` in this project, not even by mistake. Set that up; put the hook script at hooks/block-rm.sh.
