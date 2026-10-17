---
type: llm
focus: { source: file, path: skills/release-notes/SKILL.md }
---

Judge only the `description` field in the frontmatter.
PASS if it says what the skill does and when to use it in terms of what a user asks for (for example "draft release notes", "write the changelog for this release", "summarise merged PRs"), with the main use case first.
FAIL if there is no description, if it is a bare label such as "Release notes helper", or if its trigger is keyed on a file path, glob or extension being opened or edited.
