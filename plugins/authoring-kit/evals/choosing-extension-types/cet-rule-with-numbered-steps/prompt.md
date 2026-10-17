---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [choosing-extension-types, capability]
---

I keep this in .claude/rules/release.md so Claude always knows how we cut a release:

```
# Releasing

1. Run `pnpm test` and stop if anything fails.
2. Bump the version in package.json with `pnpm version <patch|minor|major>`.
3. Run `pnpm changelog` and paste the output into CHANGELOG.md under a new heading.
4. Commit as "release: vX.Y.Z", tag it, and push the tag.
5. Open the GitHub release page and paste the changelog section there.
```

Claude follows it fine when I ask for a release. Is a rule the right home for it?
