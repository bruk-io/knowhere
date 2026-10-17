---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-rules, regression]
---

I added .claude/rules/generated.md with paths "src/generated/**" saying those files are codegen output and must never be hand-edited. InstructionsLoaded shows it loading with path_glob_match, so it is definitely in context, and yet yesterday Claude edited one of those files anyway. What do I change so this cannot happen, rather than hoping Claude remembers?
