---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for authoring-skills/never-triggers/graders/fixes-description.md: the expected verdict is FAIL."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
Add `paths: ["**/*.sql"]` to the frontmatter so the skill loads whenever Claude works on a .sql file. That is the reliable fix; the description matters less.
</answer>
