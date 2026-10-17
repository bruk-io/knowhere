---
type: llm
---

PASS if the answer says that Claude Code reads AGENTS.md only as a stand-in when no CLAUDE.md or CLAUDE.local.md exists at or above the working directory, so the new CLAUDE.local.md is what stopped AGENTS.md loading, AND proposes a fix that keeps AGENTS.md loading: an `@AGENTS.md` import line in CLAUDE.local.md or in a CLAUDE.md, or switching the Project instructions setting (`instructionFiles`) to read both.
FAIL if it blames something else (caching, a syntax problem in AGENTS.md, precedence or override between the two files), if it does not identify the CLAUDE.local.md as the cause, or if the fix is a line that merely tells Claude to read AGENTS.md.
