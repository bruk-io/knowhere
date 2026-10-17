---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [wrapping-api-calls, regression]
---

My CI job runs `claude -p "Review the diff and report findings"` and then a script parses the reply as JSON with the shape {"findings": [{"file": string, "line": number, "severity": "low"|"medium"|"high", "message": string}]}. It breaks a few times a week because the reply is not quite valid JSON. What is the simplest way to make that reply schema-valid every time? I would rather not write my own API client if I can avoid it.
