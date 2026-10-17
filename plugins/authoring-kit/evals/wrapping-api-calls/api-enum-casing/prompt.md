---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [wrapping-api-calls, capability]
---

This directory is a Claude Code plugin I am building. Write skills/router/scripts/route.py (anthropic Python SDK): it reads a support ticket from stdin, asks Claude which queue it belongs to, and the answer must be guaranteed to be exactly one of "billing", "bug" or "feature" so that the next line can do HANDLERS[queue] with HANDLERS = {"billing": "finance-team", "bug": "eng-oncall", "feature": "product-inbox"} and print the handler name. It must never raise a KeyError.
