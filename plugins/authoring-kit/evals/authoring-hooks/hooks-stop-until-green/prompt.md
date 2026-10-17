---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-hooks, capability]
---

This directory is a Claude Code plugin I am building; hooks go in hooks/hooks.json and hook scripts under hooks/. Do not let Claude stop while `npm test` is failing: when it tries to finish, run the tests and send it back to work if they fail. Put the hook script at hooks/stop-gate.sh.
