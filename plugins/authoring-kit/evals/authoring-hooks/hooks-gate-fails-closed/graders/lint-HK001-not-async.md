---
type: regex
target: { source: file, path: hooks/hooks.json }
pattern: '"async"\s*:\s*true'
match: not_contains
---
