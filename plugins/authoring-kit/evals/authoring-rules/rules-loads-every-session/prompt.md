---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-rules, regression]
---

My .claude/rules/sql.md starts like this:

```
---
paths: **/*.sql
---
# SQL conventions
```

But /context lists it under memory files the moment a session starts, before I have touched any file, and it is showing up in every session including ones that never go near SQL. I thought paths was supposed to scope it. What is wrong?
