---
type: llm
---

PASS if the answer explains that a skill loads only when the model judges its description to match, so it cannot be relied on for a constraint that must hold every time, and recommends a path-scoped rule (a markdown file under .claude/rules/ with `paths` frontmatter matching src/api/**) that loads whenever Claude reads or edits a matching file - on its own or alongside a deterministic check (linter, ast-grep, hook) for the mechanically checkable part.
FAIL if the answer never recommends a path-scoped rule, or its main fix is to rewrite the skill's description, add `paths` to the skill, or otherwise keep the convention only in the skill.
