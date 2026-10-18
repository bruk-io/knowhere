---
type: llm
focus: { source: file, path: review.md }
---

PASS if the review does not approve the change. Any verdict that holds or blocks it counts, in any words: "hold", "changes requested", "not ready", "do not merge", or saying it does not approve.
FAIL only if the review approves the change, or says it is ready to merge as it is.
