---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-rules, regression]
---

Everything under src/api/ must validate request bodies with zod. Make sure Claude always follows that when it works on those files. The rest of the repo doesn't use zod, so this must not apply anywhere else.
