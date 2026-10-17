---
type: regex
target: { source: file, path: agents/security-reviewer.md }
pattern: '^tools:[^\n]*\b(Write|Edit|Bash|NotebookEdit)\b|^tools:\s*\n(\s+-[^\n]*\n)*\s+-\s*(Write|Edit|Bash|NotebookEdit)\b'
flags: m
match: not_contains
---
