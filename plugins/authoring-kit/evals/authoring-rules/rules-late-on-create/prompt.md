---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-rules, capability]
---

My path-scoped rule in .claude/rules/handlers.md (paths "src/handlers/**/*.ts") is not loading when it should. It says every handler file starts with a licence header and exports a single named handler. When Claude edits an existing handler it follows the rule perfectly. But when I ask it to create a brand new handler file, the file it writes has no header - and only on its next edit does it add it. Does a Write not count as touching the file, or what is going on?
