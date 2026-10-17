---
paths:
  - "**/SKILL.md"
  - "**/.claude/commands/**/*.md"
---
# SKILL.md invariants

Applies when reading or editing a skill or slash command.

- `description` says what the skill does, when to load it relative to the task (before writing, reviewing, debugging or advising on it) and what Claude gets wrong without it. Delivery keyed on which file is being read or written belongs in a path-scoped rule or a hook, which are guaranteed to run (the linter flags the obvious cases at info level).
- A `context: fork` body is an explicit task, not guideline prose (a forked guideline returns nothing useful).

Procedure and frontmatter reference: Skill(authoring-kit:authoring-skills). The `authoring-auditor` agent reviews the judgement calls.

The linter asserts the mechanical invariants and gives the reason for each; it reports after every write.
