---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: 'checkout: moving from main to build/demo/01\n(?:[^\n]*\t(?!commit)[^\n]*\n)*[^\n]*\tcommit: plan: 01'
---
