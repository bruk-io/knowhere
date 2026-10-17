---
type: regex
target: { source: file, path: hooks/stop-gate.sh }
pattern: 'exit 2|"decision"\s*:\s*"block"|decision:\s*"block"'
---
