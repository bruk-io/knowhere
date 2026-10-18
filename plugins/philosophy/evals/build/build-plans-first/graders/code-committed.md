---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: plan: 01[^\n]*\n[\s\S]*\tcommit(?: \(amend\))?: '
---
