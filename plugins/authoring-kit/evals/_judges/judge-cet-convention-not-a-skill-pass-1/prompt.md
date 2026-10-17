---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for choosing-extension-types/cet-convention-not-a-skill/graders/path-scoped-rule.md: the expected verdict is PASS."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
A skill only loads when Claude decides its description matches, so it will sometimes be skipped. Put the zod requirement in a path-scoped rule, .claude/rules/api-validation.md with paths: ["src/api/**"], which loads whenever Claude reads or edits a matching file. Add an ast-grep check in CI or a PostToolUse hook for the mechanical part.
</answer>
