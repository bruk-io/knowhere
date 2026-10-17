---
type: llm
focus: { source: file, path: skills/migration-safety/SKILL.md }
---

Judge only the `description` field in the frontmatter.
PASS if all three hold: (1) it tells Claude to load the skill before starting the work itself - for example "load this before writing, reviewing or ..." - rather than only naming the topics or situations it relates to; (2) it names at least one specific thing Claude would get wrong without the skill, taken from the house rules in the request; (3) the trigger is an activity or request, not a file path, glob or extension being opened or edited.
FAIL if there is no description or any of the three is missing.
