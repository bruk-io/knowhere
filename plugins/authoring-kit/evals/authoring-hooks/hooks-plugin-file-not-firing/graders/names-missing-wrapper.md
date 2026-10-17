---
type: llm
---

PASS if the answer identifies the cause as the file missing the outer `"hooks"` wrapper (the event map must sit under a top-level `{"hooks": {...}}` key in a plugin's hooks/hooks.json) and shows or describes the corrected shape.
FAIL if the main diagnosis is something else (the quoting of the placeholder, the script path, the matcher, permissions, the timeout, or needing a different event) without naming the missing wrapper.
