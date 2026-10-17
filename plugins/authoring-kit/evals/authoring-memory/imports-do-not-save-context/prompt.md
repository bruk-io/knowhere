---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-memory, regression]
---

Claude Code warns at startup that our CLAUDE.md is too large (it is about 600 lines). My plan is to split it into six topic files under docs/claude/ and replace the body of CLAUDE.md with six @import lines, so that each session only pays for the small top-level file. Will that bring the context cost down? If not, what would?
