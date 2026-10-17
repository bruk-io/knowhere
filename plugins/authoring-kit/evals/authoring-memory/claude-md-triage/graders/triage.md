---
type: llm
---

PASS if the answer moves line 1 to a hook (for example a PostToolUse hook) rather than leaving it as an instruction, AND moves line 2 to a path-scoped rule (a `.claude/rules/` file with `paths` scoped to src/ui/) rather than leaving it in CLAUDE.md. Line 3 may stay in CLAUDE.md or become a skill; either is fine.
FAIL if line 1 is left as a CLAUDE.md instruction, or if line 2 is left in CLAUDE.md or moved somewhere that loads in every session.
