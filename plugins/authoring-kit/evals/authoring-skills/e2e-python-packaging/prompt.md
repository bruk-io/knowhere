---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-skills, capability, description-e2e]
---

This directory is a Claude Code plugin I am building; skills go in skills/<name>/SKILL.md. Add a skill called python-packaging for how Python is run and packaged in our repos. Our rules: uv is the only tool - `uv add`, `uv run`, `uv sync`; never pip, pip-tools, poetry or a hand-made venv; single-file scripts declare their dependencies inline (PEP 723) and run with `uv run script.py`; uv.lock is committed. Claude keeps suggesting `pip install` and requirements.txt.
