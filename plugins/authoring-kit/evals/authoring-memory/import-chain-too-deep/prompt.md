---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-memory, regression]
---

Our CLAUDE.md pulls in our guidelines through a chain of @imports under docs/ai/ (an index that imports the backend guide, which imports the API guide, and so on). The last file in the chain, docs/ai/errors.md, says never to swallow errors, but Claude Code happily writes empty catch blocks and does not seem to know that file exists. The other guides in the chain are followed. Every path resolves when I check it by hand. What is wrong, and how should we restructure?
