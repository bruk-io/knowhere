---
timeout_seconds: 600
max_turns: 30
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
append_system_prompt: "Do not ask questions. There is no GitHub here: commit on the branch and push to origin, but don't open a PR. End with a short summary of the spec's areas of concern."
tags: [spec, capability, gate]
---

/philosophy:spec demo
