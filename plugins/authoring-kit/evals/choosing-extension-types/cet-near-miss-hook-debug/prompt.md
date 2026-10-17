---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [choosing-extension-types, regression]
---

My PreToolUse hook is supposed to stop Claude from running `git push --force`, but it never blocks anything. The handler is a script that prints "blocked" and does `exit 1` when the command matches. The matcher is `Bash`. Why does the push still go through?
