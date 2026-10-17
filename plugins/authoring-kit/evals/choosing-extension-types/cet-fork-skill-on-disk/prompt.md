---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [choosing-extension-types, capability]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md and subagents in agents/<name>.md. Add something called flaky-finder that reruns our test suite three times with `pnpm test`, works out which tests failed in some runs but not others, and reports just their names. The reruns produce thousands of lines, so it has to run in its own context and keep that noise out of my conversation. I cannot decide whether it should be a skill or a subagent - pick whichever is right and write it.
