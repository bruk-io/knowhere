---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-hooks, capability]
---

This directory is a Claude Code plugin I am building; hooks go in hooks/hooks.json and hook scripts under hooks/. After Claude writes or edits a TypeScript file (.ts), run `eslint --fix` on it. Do not start a hook process at all for files that are not TypeScript: filter in the hook config, not inside the script. Put the hook script at hooks/eslint-ts.sh.
