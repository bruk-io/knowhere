---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-agents, regression]
---

This directory is a Claude Code plugin I am building; agents go in agents/<name>.md. Add an agent called security-reviewer that reviews code changes for security problems. It must never be able to change files, run commands or hand its work to another agent, whatever it is asked.
