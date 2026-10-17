---
paths:
  - "**/.claude/rules/**/*.md"
---
# Rule-file invariants

Applies when reading or editing a rule.

- One topic per file.
- If it must be mechanically enforced, it's a hook, not a rule.
- A bullet a program could check is a lint rule with its reason in the message, not a bullet. What stays here needs judgement.

Procedure: Skill(authoring-kit:authoring-rules). The `authoring-auditor` agent reviews the judgement calls.

The linter asserts the mechanical invariants and gives the reason for each; it reports after every write.
