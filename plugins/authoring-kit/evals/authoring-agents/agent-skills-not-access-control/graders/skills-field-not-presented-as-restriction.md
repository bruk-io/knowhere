---
type: llm
---

PASS if the reply makes the "no other skills" requirement hold through the agent's tool policy (`Skill` left out of a `tools` allowlist, or `Skill` in `disallowedTools`), and does not claim that the `skills:` preload list limits which skills the agent can invoke. Saying that `skills:` only preloads is fine but not required.
FAIL if the reply says or implies that listing doc-style under `skills:` is what stops the agent using other skills, or offers no tool-level restriction at all.
