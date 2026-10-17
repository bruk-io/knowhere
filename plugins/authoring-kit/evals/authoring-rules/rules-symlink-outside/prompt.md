---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-rules, capability]
---

I keep my team conventions in ~/dev/shared-rules/ and in each repo I run `ln -s ~/dev/shared-rules/typescript.md .claude/rules/typescript.md`. The symlink is there, the file has valid frontmatter with paths for "**/*.ts", but the rule never loads in any of the repos. Other rules in the same .claude/rules/ folder load fine. Why, and what should I do instead?
