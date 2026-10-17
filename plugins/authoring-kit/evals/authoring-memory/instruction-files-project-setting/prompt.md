---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-memory, capability]
---

We want Claude Code to load both our CLAUDE.md and our AGENTS.md (AGENTS.md is shared with other tools; CLAUDE.md has Claude-only notes). I found the "Project instructions" option in /config, set it to read both, and committed the resulting pluginConfigs block with instructionFiles set to claude-md-and-agents-md into .claude/settings.json so the whole team gets it. On my machine it works, but my teammates still only get CLAUDE.md. Why, and what should we do instead?
