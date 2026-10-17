---
type: regex
target: { source: file, path: agents/docs-writer.md }
pattern: '^tools:[^\n]*\bSkill\b|^tools:\s*\n(\s+-[^\n]*\n)*\s+-\s*[\"'']?Skill\b'
flags: m
match: not_contains
---
