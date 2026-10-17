---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-rules, regression]
---

I have .claude/rules/migrations.md with this frontmatter:

```
---
paths:
  - "db/migrations/**/*.sql"
---
```

The body says migrations are append-only and every table needs a created_at column. When I ask Claude to grep the migrations folder for a column name and then tell me what our migration conventions are, it has no idea the rule exists. The glob looks right to me. What is going on?
