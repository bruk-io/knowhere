---
type: regex
target: { source: file, path: intent/demo/spec.md }
pattern: '## Areas of concern[\s\S]*?\n\d+\.(?=(?:(?!\n\d+\.)[\s\S])*?\b(?:[Ll]og(?:s|ged|ging)?|[Pp]ersonal data)\b)(?=(?:(?!\n\d+\.)[\s\S])*?Owner:)'
---
