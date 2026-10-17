---
max_turns: 3
allowed_tools: [Write]
tags: [judge-calibration]
description: "Judge calibration for authoring-skills/e2e-release-notes/graders/description-says-when-and-why.md: the expected verdict is FAIL."
---

Write exactly the text between the <file> tags to skills/release-notes/SKILL.md, then reply "done". Do not change it.

<file>
---
name: release-notes
description: Use when the user asks for release notes or a changelog. Covers grouping, PR links and breaking changes.
---

Group entries under Added / Changed / Fixed. Leave out dependency bumps and CI-only PRs. Link every PR number. Breaking changes first, under BREAKING, with a one-line migration note.
</file>
