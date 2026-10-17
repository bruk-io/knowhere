---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-hooks, capability]
---

This directory is a Claude Code plugin I am building; hooks go in hooks/hooks.json and hook scripts under hooks/. Before any `git push`, run ./scripts/preflight.sh and refuse the push if it fails. This gate must never let a push through, even if the hook script itself is missing or crashes. Put the hook script at hooks/push-gate.sh.
