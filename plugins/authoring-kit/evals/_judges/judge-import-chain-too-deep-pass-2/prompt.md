---
max_turns: 2
allowed_tools: []
tags: [judge-calibration]
description: "Judge calibration for authoring-memory/import-chain-too-deep/graders/explains-hop-limit.md: the expected verdict is PASS."
---

Reply with exactly the text between the <answer> tags and nothing else - no preamble, no quotes, no tags.

<answer>
The chain is too deep. Imports are only followed four hops, and docs/ai/errors.md is the sixth file in the chain, so its content never reaches Claude. Merge the small guides or import them all from the index file so the depth is one or two.
</answer>
