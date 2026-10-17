---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-agents, capability]
---

This directory is a Claude Code plugin I am building; agents go in agents/<name>.md. Add an agent called release-tagger that tags the current commit and pushes the tag. In the shell it may run `git tag` and `git push --tags` and nothing else - no other commands at all.
