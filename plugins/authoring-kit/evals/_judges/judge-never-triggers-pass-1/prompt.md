---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for authoring-skills/never-triggers/graders/fixes-description.md: the expected verdict is PASS."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
The description is the problem: "Helper for SQL." gives Claude no reason to load it. Rewrite it:

```
description: Our SQL query conventions and how to read our EXPLAIN plans. Load this before writing, reviewing or tuning any SQL query, even a one-liner - Claude's default style breaks our conventions.
```
</answer>
