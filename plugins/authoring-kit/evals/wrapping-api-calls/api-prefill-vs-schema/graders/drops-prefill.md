---
type: regex
target: { source: file, path: skills/extract/scripts/extract.py }
pattern: 'role["'']?\s*:\s*["'']assistant'
match: not_contains
---
