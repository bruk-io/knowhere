---
type: llm
---

The reply reviews one well-formed skill, `skills/pr-summary/SKILL.md`: an intent-based description, one load-time injection (the `!` backtick line) that ends in a `|| echo` fallback and is pre-approved by `allowed-tools: Bash(gh pr view *)`, and a short body.
PASS if the reply does not call the skill broken or blocked and makes no false claim about it. Suggestions and minor improvements (extra JSON fields, pre-approving a further command such as `git log`, wording, the `2>/dev/null`, output size, untrusted PR text) are fine, however they are labelled.
FAIL if the reply says the skill will fail to load or is broken, or makes any of these false claims: the injection has no fallback; the injection itself is not pre-approved by `allowed-tools`; the description is keyed on which file is being edited; the skill should be a rule, agent or hook instead.
