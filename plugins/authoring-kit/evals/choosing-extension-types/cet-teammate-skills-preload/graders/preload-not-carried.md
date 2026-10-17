---
type: llm
---

PASS if the answer says that when an agent definition is used as a teammate in an agent team it keeps its tools and body but does NOT get its `skills` preload, so the migrators would run without the conventions, and offers a fix (put the conventions in the agent body, or use parallel subagents or a workflow instead of an agent team if the preload matters).
FAIL if the answer says the conventions will load as usual, or does not mention that teammates lose the `skills` preload.
