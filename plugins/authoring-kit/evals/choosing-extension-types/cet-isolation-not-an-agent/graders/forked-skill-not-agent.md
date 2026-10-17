---
type: llm
---

PASS if the answer says that isolation (a separate context, keeping noise out of the main conversation) is not by itself a reason to write a subagent, and recommends a skill that runs in a forked context (`context: fork` in the skill's frontmatter) as the mechanism for this single, self-contained workflow.
FAIL if the answer endorses writing a subagent as the way to get isolation, or never mentions that a skill can run forked.
