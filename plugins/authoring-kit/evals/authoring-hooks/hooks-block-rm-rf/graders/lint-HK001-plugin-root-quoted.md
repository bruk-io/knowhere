---
type: regex
target: { source: file, path: hooks/hooks.json }
pattern: '\\"\$\{?CLAUDE_PLUGIN_ROOT\}?/[^"\\]*\\"|''\$\{?CLAUDE_PLUGIN_ROOT\}?/[^'']*''|"args"\s*:\s*\[[^\]]*"\$\{CLAUDE_PLUGIN_ROOT\}/'
---
