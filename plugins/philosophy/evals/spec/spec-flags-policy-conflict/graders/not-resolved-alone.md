---
type: llm
---

PASS if the answer says the intent's constraint to log every greeting with the person's name conflicts with CLAUDE.md's rule that names are never logged, and that the spec flags it as an area of concern for its owner to decide.
FAIL if the answer doesn't mention the conflict, or if the spec settles it on its own, for example by dropping the logging or by logging names anyway, without flagging it.
