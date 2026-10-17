---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-hooks, capability]
---

I have a PostToolUse hook with matcher `Edit|Write` that runs prettier on the file Claude just changed, and it works for normal edits. But when Claude rewrites a file with `sed -i` or a `cat > file` in a Bash command, the formatter never runs. How do I make the hook cover those cases too?
