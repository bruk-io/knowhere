---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-hooks, regression]
---

I set up a PreToolUse hook on Bash to stop Claude from running `git push --force`. The script prints "force push is not allowed" and exits 1 when it sees one, but Claude still runs the push; the transcript just shows a hook error. Why is it not blocking?
