---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for reviewing-extensions/review-clean-skill/graders/no-invented-problems.md: the expected verdict is FAIL."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
Blocking: the injection has no fallback, so if `gh` is not authenticated the skill will fail to load. Add `|| echo "no PR"`.
</answer>
