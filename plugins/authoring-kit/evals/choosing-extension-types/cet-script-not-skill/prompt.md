---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [choosing-extension-types, capability]
---

I want a skill that, when I ask for a dependency report, reads package.json, lists every dependency and devDependency with its version, sorts them alphabetically and prints them as a markdown table with a column saying which section each came from. Where should this logic live - should I write the steps into the skill body?
