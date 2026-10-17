---
type: regex
target: { source: file, path: CLAUDE.md }
pattern: '(^|\n)[ \t]*<!--((?!-->)[\s\S])*?pnpm-lock((?!-->)[\s\S])*?-->[ \t]*(\n|$)'
---
