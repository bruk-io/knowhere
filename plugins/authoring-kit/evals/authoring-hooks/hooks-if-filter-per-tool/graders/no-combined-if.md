---
type: regex
target: { source: file, path: hooks/hooks.json }
pattern: '"if"\s*:\s*"[^"]*(\|\||&&|\)\s*\|)[^"]*"'
match: not_contains
---
