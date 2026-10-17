---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-rules, regression]
---

Set up rules for this repo: request bodies under src/api/ are validated with zod and errors use our ErrorEnvelope type; files under db/migrations/ are never edited once merged, only new migrations are added; React code under src/ui/ uses function components and hooks, never class components.
