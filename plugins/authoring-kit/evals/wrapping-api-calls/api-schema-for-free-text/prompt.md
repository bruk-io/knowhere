---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [wrapping-api-calls, regression]
---

I have a Claude Code skill that drafts the pull request description for the current branch; a human reads it and edits it in the GitHub UI, nothing parses it. To make it more robust I am thinking of having the skill call a small script that sends the draft request through the Anthropic API with structured outputs so the description is guaranteed to come back in a fixed JSON shape. Good idea? If so sketch the script, if not tell me what I should do instead.
