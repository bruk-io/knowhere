---
type: regex
target: { source: file, path: hooks/hooks.json }
pattern: '"onFailure"\s*:\s*"block"|\|\|\s*exit 2'
---
