---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-hooks, capability]
---

I have a /migrate skill that runs database migrations. While it is running I want a PreToolUse hook that blocks any Bash command touching the production database, but the block should only apply during that skill, not for the rest of my session. Can I put the hook in the skill's frontmatter to get that?
