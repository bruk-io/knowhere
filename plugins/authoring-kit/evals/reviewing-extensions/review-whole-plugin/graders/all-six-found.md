---
type: llm
---

The reply is an audit of a small Claude Code plugin with six planted problems. PASS only if the reply reports ALL six:
1. `skills/deploy-notes/SKILL.md`: the description triggers on which file is being edited (deploy/, Dockerfile) rather than on what the user asks for; the fix is a path-scoped rule or a hook.
2. `skills/branch-context/SKILL.md`: the `!` backtick injections have no fallback (`|| echo ...`), so a failing command aborts the skill load.
3. `rules/testing.md`: a rule containing numbered procedure steps; the steps belong in a skill.
4. `agents/isolated-formatter.md`: an agent that exists only for isolation or a restricted tool set; a skill with `context: fork` does that, so the agent is not justified.
5. `agents/history-reader.md`: `Bash(git *)` in `tools` does not restrict Bash to git; it grants the whole tool.
6. `CLAUDE.md`: "always run `npm run lint -- --fix` after every edit" is zero-judgement work on an event and should be a PostToolUse hook, not a memory line.
FAIL if any of the six is missing, or if the reply says a planted problem is fine.
