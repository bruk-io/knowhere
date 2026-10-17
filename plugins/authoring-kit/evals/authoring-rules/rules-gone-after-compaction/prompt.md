---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-rules, regression]
---

Long session today. For the first hour Claude followed my .claude/rules/api.md rule (paths "src/api/**") every time it touched an endpoint. Then the context got compacted, and in the work right after that it wrote an endpoint without zod validation, which the rule forbids. Nothing about the rule changed. What happened, and is there anything to do about it?
