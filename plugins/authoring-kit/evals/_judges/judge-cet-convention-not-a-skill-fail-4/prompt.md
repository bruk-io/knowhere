---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for choosing-extension-types/cet-convention-not-a-skill/graders/path-scoped-rule.md: the expected verdict is FAIL."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
Add `paths: src/api/**` to the skill's frontmatter. Then it is offered every time Claude works on those files, so the validation rule will always apply.
</answer>
