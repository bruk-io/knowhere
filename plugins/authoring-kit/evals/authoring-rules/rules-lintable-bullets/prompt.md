---
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
append_system_prompt: "Do not ask the user questions; make reasonable assumptions and do the task."
tags: [authoring-rules, capability]
---

Add a rule for everything under src/ui/ with our component conventions: no hardcoded hex colours in styles, colours come from the tokens exported by src/ui/theme.ts; component files stay under 200 lines; and components should be composed from existing primitives rather than reimplementing them unless the primitive genuinely does not fit.
