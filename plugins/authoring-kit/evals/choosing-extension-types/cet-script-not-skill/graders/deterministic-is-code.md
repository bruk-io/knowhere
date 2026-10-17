---
type: llm
---

PASS if the answer says the parsing, sorting and table formatting are deterministic and hands that work to code (a bundled script, or a single command such as jq or node that the skill runs), so the skill body is at most a thin wrapper saying when to run it and how to present the result.
FAIL if the answer has the model itself read package.json, collect the entries, sort them and format the table by following prose steps, with no script or command doing the deterministic work.
