---
type: llm
---

PASS if the answer identifies the description as the cause and proposes a rewritten description that does both: (1) tells Claude to load the skill before starting the work itself - for example "load this before writing, reviewing or tuning any SQL query" - rather than only naming topics or situations; (2) says why Claude needs the skill over its own knowledge, such as the team's query conventions or how to read their EXPLAIN output.
FAIL if it does not rewrite the description, if the rewrite misses either point, or if it presents something else (for example `paths`, a rule or a hook) as the main fix.
