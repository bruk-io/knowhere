---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-agents, capability]
---

This directory is a Claude Code plugin I am building; agents go in agents/<name>.md. Add an agent called codebase-scout that finds where a symbol or feature lives in a large repo and reports the file paths and line numbers, nothing more. It will be dispatched dozens of times per session, so make it as cheap to run as possible.
