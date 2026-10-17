---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-agents, regression]
---

My plugin ships an agent at agents/releaser.md with this frontmatter:

```
---
name: releaser
description: Cuts a release. Use when asked to release, tag or publish a version.
tools: Read, Grep, Glob, Bash
skills:
  - deploy
---
```

and a skill at skills/deploy/SKILL.md whose frontmatter is:

```
---
name: deploy
description: Pushes the current build to production.
disable-model-invocation: true
---
```

The skill resolves fine (`/deploy` works in the main session), but the releaser agent never seems to know the deploy procedure when it starts. Why, and what should I change?
