---
type: llm
focus: { source: file, path: agents/security-reviewer.md }
---

Judge only the frontmatter. The agent must not be able to delegate to other agents.
PASS if `tools` is an explicit allowlist that does not include `Agent`, or `disallowedTools` includes `Agent`.
FAIL if `Agent` appears in `tools`, or if there is no `tools` allowlist and `disallowedTools` does not list `Agent` (every tool, Agent included, is then available), or if the only restriction is a sentence in the body.
