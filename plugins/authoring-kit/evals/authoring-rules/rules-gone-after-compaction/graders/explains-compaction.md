---
type: llm
---

PASS if the answer says that after compaction a path-scoped rule is not re-injected and comes back only when Claude next reads, writes or edits a matching file, and names at least one mitigation (for example re-reading an endpoint file after compaction, making the constraint an unscoped rule or CLAUDE.md line that is re-injected after compaction, a hook that enforces or re-injects it, or a SessionStart compact hook).
FAIL if it says compaction has no effect on rules, blames the glob or the rule body, or gives no mechanism for why the rule disappeared.
