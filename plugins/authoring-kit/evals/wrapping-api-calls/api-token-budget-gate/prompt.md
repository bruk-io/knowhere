---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [wrapping-api-calls, regression]
---

This directory is a Claude Code plugin I am building. Before my summarise skill sends a long document to Claude I want to know how many tokens the prompt is, so the skill can refuse anything over a budget instead of paying for a call that fails. Write skills/summarise/scripts/budget_check.py (anthropic Python SDK): it reads the document from stdin, takes --model and --max-tokens arguments, prints {"input_tokens": N, "within_budget": true|false} as JSON, and must not spend money on a generation to find out.
