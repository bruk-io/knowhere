---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-rules, regression]
---

Add a rule so that whenever Claude works on a *.test.ts or *.spec.ts file, anywhere in the repo, it uses vitest's `vi.fn()` and never jest mocks, and keeps one describe block per exported function. It must not load for other files.
