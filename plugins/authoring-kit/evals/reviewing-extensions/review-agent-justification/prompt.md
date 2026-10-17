---
description: "Auditor flags an agent that exists only for isolation and tool limits, and Bash(git *) in tools believed to restrict Bash. Needs --scaffold and --allow-tools Bash."
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [reviewing-extensions, capability]
---

/authoring-kit:reviewing-extensions fixtures/
