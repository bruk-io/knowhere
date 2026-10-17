---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [choosing-extension-types, regression]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md and subagents in agents/<name>.md. Add something called accessibility-reviewer that I can hand any front-end change to and get back a list of accessibility problems. Whatever it is asked to look at, it must never be able to edit files or run shell commands. Pick whichever extension type is right.
