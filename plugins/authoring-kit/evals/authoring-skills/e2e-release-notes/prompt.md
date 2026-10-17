---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-skills, capability, description-e2e]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md. Add a skill called release-notes for drafting our release notes. Our house rules: entries are grouped under Added / Changed / Fixed, never by PR author; dependency bumps and CI-only PRs are left out; every entry links its PR number; breaking changes go first under a BREAKING heading with a one-line migration note. People forget these rules every release.
