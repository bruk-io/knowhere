---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-skills, capability, description-e2e]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md. Add a skill called api-errors for the error responses of our HTTP API. Our rules: errors are RFC 9457 problem+json with `type`, `title`, `status` and `detail`; `type` is a URL from our registry, https://errors.acme.dev/<code>, and every new code is added to docs/errors.md; validation failures return 422, not 400, with an `errors` array of {field, message}; `detail` never contains stack traces or SQL. Handlers written without this keep returning ad-hoc {error: '...'} bodies.
