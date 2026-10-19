---
type: regex
target: { source: file, path: review.md }
flags: i
pattern: '#+[^\n]*\bimportant\b[^\n]*\n(?:(?!#)[^\n]*\n)*?[^\n]*logger\.py|\bimportant\b[^\n]*logger\.py'
---
