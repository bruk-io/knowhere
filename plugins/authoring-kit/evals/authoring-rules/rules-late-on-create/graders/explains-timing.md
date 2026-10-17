---
type: llm
---

PASS if the answer says that a Write to a matching path does trigger the rule, but the rule is delivered with the Write's tool result, so on the call that creates the file it arrives after the file is already written and only informs the next step - and it offers at least one workaround (for example a PostToolUse hook that checks or fixes the header, an unscoped rule or CLAUDE.md line, a skill or template for creating handlers, or reading an existing handler before writing a new one).
FAIL if it says Write does not trigger a path-scoped rule and only Read does, if it tells the user to fix the glob or the body, or if it gives no explanation of the timing.
