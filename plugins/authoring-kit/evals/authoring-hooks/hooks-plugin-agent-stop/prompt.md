---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-hooks, capability]
---

This directory is a Claude Code plugin called review-kit that I am building; it ships a subagent at agents/reviewer.md. Every time that reviewer subagent finishes, I want hooks/notify-done.sh to run; it must not run when any other subagent finishes. Set that up, writing the script and the agent file as stubs.
