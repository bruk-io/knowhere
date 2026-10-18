---
type: regex
target: { source: file, path: .git/commit-files.log }
pattern: '^== plan: 01[^\n]*\n(?:intent/demo/plans/01-[^\n]*\.md\n)+(?:== |$)'
---
