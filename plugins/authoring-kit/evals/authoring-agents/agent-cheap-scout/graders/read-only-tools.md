---
type: regex
target: { source: file, path: agents/codebase-scout.md }
pattern: '^tools:[^\n]*\b(Write|Edit|Bash)\b|^tools:\s*\n(\s+-[^\n]*\n)*\s+-\s*(Write|Edit|Bash)\b'
flags: m
match: not_contains
---
