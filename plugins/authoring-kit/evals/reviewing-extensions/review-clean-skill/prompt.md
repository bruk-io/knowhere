---
description: "Auditor reviews one clean skill and does not invent problems. Needs --scaffold and --allow-tools Bash."
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [reviewing-extensions, regression]
---

/authoring-kit:reviewing-extensions fixtures/
