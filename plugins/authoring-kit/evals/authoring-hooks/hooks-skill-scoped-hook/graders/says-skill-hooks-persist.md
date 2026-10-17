---
type: llm
---

PASS if the answer says that hooks declared in a skill's frontmatter stay registered for the rest of the session once the skill is invoked (they are not removed when the skill's turn ends), so the frontmatter alone does not give the "only during the skill" scoping, and offers an alternative (for example a subagent whose hooks are active only while it runs, a `context: fork` skill, or a hook whose script checks its own state).
FAIL if the answer says or implies that a skill-frontmatter hook is active only while the skill runs, or gives the frontmatter as the answer without that caveat.
