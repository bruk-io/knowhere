---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [wrapping-api-calls, regression]
---

This directory is a Claude Code plugin I am building. I have about twelve thousand customer reviews as individual .txt files under data/reviews/ and I want each one tagged with a sentiment and up to three topics. It does not need to be interactive, it can run overnight, and I want it as cheap as possible. Write the tool at skills/review-tagger/scripts/tag_reviews.py using the anthropic Python SDK.
