---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for reviewing-extensions/review-clean-skill/graders/no-invented-problems.md: the expected verdict is FAIL."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
This should not be a skill. A PR summary that must always appear belongs in a hook on PreToolUse, so convert it.
</answer>
