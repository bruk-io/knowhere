---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-skills, capability, description-e2e]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md. Add a skill called migration-safety for writing and reviewing our Postgres schema migrations. Our rules: set `lock_timeout = '5s'` at the top of every migration; never add a column with a default and NOT NULL in one statement on a large table; create indexes with CREATE INDEX CONCURRENTLY outside a transaction; backfill in batches of 10k rows in a separate migration; every migration has a working down step. Migrations Claude wrote have broken these rules before.
