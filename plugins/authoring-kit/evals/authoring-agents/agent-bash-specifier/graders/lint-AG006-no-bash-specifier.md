---
type: regex
target: { source: file, path: agents/release-tagger.md }
pattern: '^(tools|disallowedTools):[^\n]*Bash\(|^(tools|disallowedTools):\s*\n(\s+-[^\n]*\n)*\s+-\s*[\"'']?Bash\('
flags: m
match: not_contains
---
