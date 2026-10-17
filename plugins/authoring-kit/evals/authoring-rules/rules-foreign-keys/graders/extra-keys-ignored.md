---
type: llm
---

PASS if the answer says yes: Claude Code reads only `paths`, keys it does not know are ignored without an error, and the whole frontmatter is stripped before the body reaches context, so the extra keys neither break the rule nor leak into context.
FAIL if it says the extra keys will break the rule, will cause an error, or will appear in Claude's context, or if it tells the user to keep two separate files or is unable to say whether the extra keys are safe.
