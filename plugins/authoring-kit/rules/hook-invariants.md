---
paths:
  - "**/.claude/settings*.json"
  - "**/hooks/hooks.json"
---
# Hook invariants

Applies when reading or editing hook configuration.

- Decide deliberately whether a gate fails open or closed when its script is missing or crashes. No check can make that call for you.
- Anything checkable gets a deterministic `command` handler; a `prompt` or `agent` handler is for judgement no script can make.

Procedure and protocol reference: Skill(authoring-kit:authoring-hooks). The `authoring-auditor` agent reviews the judgement calls.

`hooktool validate` asserts the structure and gives the reason for each finding; the linter runs it after every write.
