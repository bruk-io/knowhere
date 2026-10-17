---
type: llm
---

PASS if the final message says the import failed because the full stop (period) directly after `@docs/conventions.md` is read as part of the path, so the import resolved to a file that does not exist and nothing was imported.
FAIL if it gives another cause (imports not supported mid-sentence, the file needs to be in CLAUDE.md, the path should be absolute, a caching problem) or inlines the conventions into CLAUDE.md instead of keeping the import.
