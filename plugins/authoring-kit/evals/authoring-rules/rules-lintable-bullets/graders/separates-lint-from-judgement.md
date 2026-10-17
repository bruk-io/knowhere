---
type: llm
---

PASS if Claude points out that at least one of the bullets (no hardcoded hex colours, files under 200 lines) is something a program can check and belongs in a linter, lint script, ast-grep rule or hook rather than as prose in the rule, and keeps the judgement bullet (compose from primitives unless they do not fit) as the rule's content or clearly separates the two.
FAIL if all three bullets go into the rule as prose with no mention that the mechanical ones should be a lint check or hook.
