---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-skills, capability, description-e2e]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md. Add a skill called textual-8 for writing Textual TUI code in our apps. We are on Textual 8, and much of what Claude remembers is from before 1.0: `Static.renderable` is now `Static.content`; `Select.BLANK` is now `Select.NULL`; `App.query` searches the default screen, not the active one, so query from the screen; use `query_one_optional` instead of catching NoMatches. Code written from memory keeps hitting these.
