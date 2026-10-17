---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for authoring-memory/import-chain-too-deep/graders/explains-hop-limit.md: the expected verdict is PASS."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
Claude Code follows @imports only a limited number of hops deep (five, per the docs). Your chain is CLAUDE.md -> index -> backend -> api -> ... -> errors.md, so errors.md sits past that depth and never loads, which is why the others work and it does not. Flatten it: import every guide directly from CLAUDE.md (or from the index), so no file is nested inside another.
</answer>
