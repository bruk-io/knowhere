---
type: llm
---

PASS if the answer says a symlink whose target is outside the project directory is treated like an external import and is not loaded (and that a path-scoped one stays unloaded even when external imports are approved), and recommends putting shared rules in ~/.claude/rules/ or copying the file into the repo instead of symlinking.
FAIL if it says symlinks are simply unsupported with no mention of the outside-the-project distinction, or if it suggests only fixing permissions, the glob, or the frontmatter.
