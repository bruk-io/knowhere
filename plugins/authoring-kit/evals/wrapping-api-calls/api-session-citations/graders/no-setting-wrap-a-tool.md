---
type: llm
---

PASS if the answer says both of these: (1) there is no setting, flag or CLAUDE.md line that turns the API's citations feature on for an interactive Claude Code session, because Claude Code controls the requests it sends; and (2) the way to get guaranteed citations is to make your own Messages API call with citations enabled inside a tool or script (for example a small CLI) that the session calls, which then returns the cited answer.
FAIL if it claims a setting, flag or CLAUDE.md instruction can enable API citations for the session, or if it offers only prompt-based "please quote your sources" as the solution without pointing at a wrapped API call.
