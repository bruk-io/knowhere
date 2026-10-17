---
type: llm
---

PASS if the answer explains that a subdirectory CLAUDE.md is loaded on demand (when Claude reads or edits a file under that directory) and is not re-injected after compaction - only the project-root CLAUDE.md is re-read after compaction - AND says the line should move to the root CLAUDE.md (or to a hook that blocks the staging migration command) because anything that must survive a long session belongs at the root rather than in a subtree file.
FAIL if it attributes the fading only to general context loss or model forgetfulness without the subdirectory loading behaviour, or if it recommends keeping the line in packages/api/CLAUDE.md (for example by rewording it).
