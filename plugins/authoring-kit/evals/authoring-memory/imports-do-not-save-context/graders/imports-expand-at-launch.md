---
type: llm
---

PASS if the answer says the plan will not reduce context, because imported files are expanded inline at launch and cost the same tokens as if the text were in CLAUDE.md, AND recommends reducing what loads instead: cutting content Claude can derive from the codebase, moving file-domain conventions to path-scoped rules (`.claude/rules/` with `paths`), moving procedures to skills, or moving checkable lines to hooks (any two of these is enough).
FAIL if it says the split will save context, hedges that imports might be lazy-loaded or loaded on demand, or offers no alternative beyond "shorten it".
