---
type: llm
---

PASS if the reply says the cause is that a skill with `disable-model-invocation: true` cannot be preloaded by an agent's `skills` field (it is skipped, silently or with only a debug-log warning), and proposes a fix such as removing `disable-model-invocation` from that skill, moving the procedure into a separate preloadable skill, or putting it in the agent body.
FAIL if the reply blames something else as the main cause (the bare name, a missing plugin prefix, the `tools` list, a path problem) or does not connect `disable-model-invocation` to preloading.
