---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [choosing-extension-types, regression]
---

We never want hardcoded hex colours like #ff0000 in our TypeScript components; everything must come from the theme tokens. My plan is a PostToolUse hook on Write and Edit whose handler asks Claude to look at the edited file and judge whether it introduced a hardcoded colour, and fail if so. Is that a good design?
