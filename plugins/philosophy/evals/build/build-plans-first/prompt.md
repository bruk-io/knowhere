---
max_turns: 40
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
append_system_prompt: "Do not ask questions. There is no GitHub here: push to origin, but don't open a PR or turn on auto-merge. When you stop, print the output of `git log --stat --reverse --format=%s main..HEAD`."
tags: [build, capability]
---

/philosophy:build demo
