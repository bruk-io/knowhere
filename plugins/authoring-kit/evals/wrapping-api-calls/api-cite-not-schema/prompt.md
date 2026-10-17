---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [wrapping-api-calls, regression]
---

This directory is a Claude Code plugin I am building. Write a Python tool at skills/research/scripts/cite.py (anthropic Python SDK) that takes a question and one or more text or markdown file paths, asks Claude to answer from those files only, and prints a JSON object {"answer": ..., "citations": [{"cited_text": ..., "source": ..., "location": ...}]} to stdout. Two hard requirements: every claim in the answer must be traceable to an exact passage in the files I passed, never to anything else, and the output must be guaranteed to be valid JSON because another script parses it.
