---
type: llm
---

PASS if the reply tells the user that an agent's `tools` / `disallowedTools` entries are tool-level, so a `Bash(git tag *)` style entry cannot limit Bash to those commands (it grants the whole tool), and names a mechanism that can limit the commands: a `PreToolUse` hook, or a permissions allow/deny rule in settings.
FAIL if the reply presents `Bash(...)` entries in the agent's frontmatter as what limits the commands, or says nothing about how the command-level limit is enforced.
