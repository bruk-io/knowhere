---
paths:
  - "**/.claude/agents/**/*.md"
---
# Subagent invariants

Applies when reading or editing a subagent.

- `tools` is the minimal boundary for the role: reviewers stay read-only, and a role that must not delegate leaves out `Agent`.
- `description` matches intent - the work a user or the main session hands over. Dispatch that must happen on an event is a hook's job, not the description's.

Procedure and frontmatter reference: Skill(authoring-kit:authoring-agents). The `authoring-auditor` agent reviews the judgement calls.

The linter asserts the mechanical invariants and gives the reason for each; it reports after every write.
