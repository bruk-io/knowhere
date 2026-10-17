---
type: llm
---

PASS if the reply closes with a short verdict (about one sentence each) for every artifact audited: both skills (deploy-notes, branch-context), the rule (testing.md), both agents (isolated-formatter, history-reader) and CLAUDE.md - a triage line saying whether each should be kept, reshaped or replaced.
FAIL if there is no per-artifact verdict at the end, or if two or more of those six artifacts have no verdict.
