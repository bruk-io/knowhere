---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [wrapping-api-calls, regression]
---

This directory is a Claude Code plugin I am building. My skill calls the tool skills/extract/scripts/extract.py to pull {"name": string, "email": string, "company": string} out of an email signature. Today the script prefills the assistant turn with "{" to force JSON, but about one run in twenty the output is still not parseable. Rewrite skills/extract/scripts/extract.py (anthropic Python SDK, signature text on stdin, JSON on stdout) so that the JSON is guaranteed by the API itself, and keep the prefill trick if it still helps.
