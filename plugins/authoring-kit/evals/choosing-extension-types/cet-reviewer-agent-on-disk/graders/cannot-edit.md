---
type: llm
focus: { source: file, path: agents/accessibility-reviewer.md }
---

Judge only the frontmatter.
PASS if the agent's tool policy prevents editing and shell: either a `tools` list that contains neither Write, Edit, MultiEdit nor Bash, or a `disallowedTools` list that names Write, Edit and Bash (or equivalent).
FAIL if the frontmatter has no tool restriction, or still allows Write, Edit or Bash.
