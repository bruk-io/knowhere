---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for reviewing-extensions/review-clean-skill/graders/no-invented-problems.md: the expected verdict is PASS."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
Looks good. Minor: if you later inject `git log` too, it will need its own allowed-tools entry. Otherwise ship it.
</answer>
