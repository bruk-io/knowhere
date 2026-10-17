---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [choosing-extension-types, regression]
---

I wrote a skill called api-conventions that says every handler under src/api/ must validate its request body with a zod schema before touching it. Most of the time Claude applies it, but every so often it edits a handler and skips the validation, so I assume the skill did not load that time. What is the right way to make this hold every time Claude touches those files?
