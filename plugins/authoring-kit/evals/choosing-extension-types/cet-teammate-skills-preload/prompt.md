---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [choosing-extension-types, regression]
---

I have an agent definition at .claude/agents/migrator.md whose frontmatter preloads our database conventions with `skills: [db-conventions]`, and the body is short because the skill carries the rules. I now want to run three migrators at once as teammates in an agent team so they can share what they find about the schema. Will the migrators still have the conventions?
