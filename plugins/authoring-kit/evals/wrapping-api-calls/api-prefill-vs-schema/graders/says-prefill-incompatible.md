---
type: llm
---

PASS if Claude tells the user that the assistant prefill ("{") was removed because prefilling cannot be combined with structured outputs (the API rejects the request or it is not supported), so the schema replaces the trick rather than sitting beside it.
FAIL if Claude keeps the prefill alongside structured outputs, or removes it without saying that the two are incompatible.
