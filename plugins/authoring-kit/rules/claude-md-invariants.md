---
paths:
  - "**/CLAUDE.md"
  - "**/CLAUDE.local.md"
  - "**/AGENTS.md"
---
# CLAUDE.md invariants

Applies when reading or editing project memory.

- Specific and verifiable ("use 2-space indentation"), not vague ("format properly").
- Don't restate what a path-scoped rule or an imported file already says.
- Content for Claude Code alone stays out of `AGENTS.md` - other tools read it too.

Procedure: Skill(authoring-kit:authoring-memory). The `authoring-auditor` agent reviews the judgement calls.

The linter asserts the mechanical invariants and gives the reason for each; it reports after every write.
