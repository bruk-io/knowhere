---
type: llm
---

PASS if Claude tells the user that a skill's `paths` field (or its description) cannot guarantee the content loads when src/db/ files are edited, and puts the conventions in a path-scoped rule (for example under .claude/rules/ with `paths` for src/db/**) or another mechanism that guarantees loading, or recommends doing so.
FAIL if Claude only writes a skill with `paths: src/db/**` (or a description keyed on src/db) and presents that as guaranteeing the conventions load.
