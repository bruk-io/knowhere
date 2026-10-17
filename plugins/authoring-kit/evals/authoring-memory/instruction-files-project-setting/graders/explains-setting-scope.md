---
type: llm
---

PASS if the answer says the instructionFiles / Project instructions setting is honoured only in user settings (~/.claude/settings.json), a --settings file, or managed settings, and is ignored in project (.claude/settings.json) and local settings - which is why it works for the author (whose /config wrote it to user settings) and not for teammates - AND recommends bridging instead by having CLAUDE.md import AGENTS.md with an `@AGENTS.md` line.
FAIL if it says the project setting should work and looks for a typo, a stale cache or a version mismatch as the main cause, or if the proposed fix is a line in CLAUDE.md that merely tells Claude to read AGENTS.md, or asks each teammate to change their own settings without mentioning the import bridge.
