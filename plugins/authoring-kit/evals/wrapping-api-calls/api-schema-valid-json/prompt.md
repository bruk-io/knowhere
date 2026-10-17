---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [wrapping-api-calls, regression]
---

This directory is a Claude Code plugin I am building. I have a skill that classifies support tickets, and the rest of my pipeline parses its output as JSON, so it breaks whenever the model wraps the JSON in prose or leaves a field out. I need the result to be valid JSON every single time, matching this shape: {"category": "billing" | "bug" | "feature", "urgency": 1-5, "summary": string}. Write me a small Python tool at skills/triage/scripts/classify.py that the skill calls with the ticket text on stdin and that prints that JSON to stdout, using the anthropic Python SDK.
