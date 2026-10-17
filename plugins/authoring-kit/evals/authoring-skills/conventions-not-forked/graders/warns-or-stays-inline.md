---
type: llm
---

PASS if Claude either keeps the style-guide skill inline (no `context: fork`) and says why, or tells the user that forking a skill made only of conventions does not work well because the forked subagent has no task to perform and cannot apply the conventions to the main conversation's work.
FAIL if Claude forks it without any such warning.
