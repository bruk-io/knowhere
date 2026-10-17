---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-rules, capability]
---

Half my team uses Cursor and half uses Claude Code. I want one rule file per convention, not two copies. Can a file in .claude/rules/ carry Cursor's `description` and `globs` keys alongside Claude Code's `paths`, or will the extra keys break the rule or leak into Claude's context? For example:

```
---
description: API validation conventions
globs: src/api/**/*.ts
paths:
  - "src/api/**/*.ts"
---
# API validation
- Request bodies are validated with zod
```
