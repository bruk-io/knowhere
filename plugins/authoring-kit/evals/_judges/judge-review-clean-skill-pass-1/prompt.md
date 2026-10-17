---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for reviewing-extensions/review-clean-skill/graders/no-invented-problems.md: the expected verdict is PASS."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
## Judgement
No blocking problems. skills/pr-summary is sound: the description is intent-based, the injection ends in an `|| echo` fallback and `allowed-tools: Bash(gh pr view *)` pre-approves it.
Suggestions: the PR body is untrusted text, so keep the instruction to treat it as data; you could add `--json files` for more context.
## Mechanical
claude-lint: 1 artifact checked, 0 errors.
</answer>
