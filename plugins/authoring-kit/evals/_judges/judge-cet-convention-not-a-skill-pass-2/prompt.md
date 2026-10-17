---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for choosing-extension-types/cet-convention-not-a-skill/graders/path-scoped-rule.md: the expected verdict is PASS."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
Skills load only when Claude judges the description relevant, so one cannot guarantee this. Make it a hook plus a rule: a PostToolUse hook that runs a lint check for unvalidated handlers blocks the obvious misses, and a path-scoped rule under .claude/rules/ scoped to src/api/** keeps the convention in front of Claude whenever it touches those files.
</answer>
