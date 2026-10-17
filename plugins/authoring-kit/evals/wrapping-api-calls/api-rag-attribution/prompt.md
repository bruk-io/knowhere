---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [wrapping-api-calls, capability]
---

This directory is a Claude Code plugin I am building. I have a tool skills/kb/scripts/search_kb.py that already queries our internal knowledge base at call time and returns a list of {"title", "url", "text"} hits. Write skills/kb/scripts/answer_kb.py (anthropic Python SDK) that runs that search for a question, hands the hits to Claude, and prints an answer where each statement is attributed to the exact hit it came from, so that I can show the sources next to the answer and trust them. The hits are retrieved fresh on every call, not stored ahead of time.
