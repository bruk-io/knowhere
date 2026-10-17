---
name: authoring-hooks
description: 'Use when something must happen on every tool call or lifecycle event without relying on the model - blocking commands, formatting or linting after edits, gating on tests, injecting context - or a hook is not firing or not blocking. Hook behaviour has traps Claude gets wrong from memory (which exit code blocks, matcher syntax, gates that fail open, plugin hook file shape), so load this before writing, reviewing, debugging or advising on any hook, even a small one.'
allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/hooktool.py" *)
---

# Authoring Claude Code hooks

Hooks are Claude Code's enforcement layer: shell, HTTP, MCP-tool, or LLM handlers that fire
on lifecycle events and run **every time the event matches, regardless of what the
model decides**. They are the only extension type that gives a hard guarantee: the
harness runs the handler, so nothing depends on the model choosing to act.

## First - is a hook actually the right extension type?

Reach for a hook only when something **must happen deterministically on an event**:

- Block a tool call or command → `PreToolUse`, exit 2
- Run a formatter or linter after edits → `PostToolUse`
- Keep working until a check passes → `Stop`, exit 2
- Back up state before compaction → `PreCompact`
- Inject standing context at session start → `SessionStart` (plain stdout is injected; it does not fire for subagents - `SubagentStart` does)

Do **not** use a hook when:

- The behaviour is guidance the model applies with judgement → that's CLAUDE.md, a rule, or a skill.
- The rule is already enforced in CI → prefer the CI gate; a hook is the fast local mirror, not a replacement.
- You're tempted to write a hook whose handler is an LLM "judging" something checkable → use a deterministic check instead ([`choosing-extension-types/references/minimizing-model-work.md`](../choosing-extension-types/references/minimizing-model-work.md), "Anti-patterns - context where code belongs"). The `prompt` and `agent` handler types exist for the rare case where fixed logic genuinely can't decide.

Choosing the handler is itself the gate's decision - invoke Skill(authoring-kit:choosing-extension-types): a `command` handler runs deterministic code (guaranteed to run, fixed result), while `prompt`/`agent` handlers put the model in the loop (guaranteed to run, sampled result). Bias to `command`.

If none of those fit, the work probably belongs to a different extension type - hand back to the selector.

## Workflow

The bundled `hooktool` is not on PATH: run it by the full path shown in each
step (already expanded for this install), quoted exactly as written.

1. **Pick the event.** The table lists every event: whether exit 2 blocks, what the matcher filters, and which channels reach Claude:
   ```
   python3 "${CLAUDE_SKILL_DIR}/scripts/hooktool.py" events
   ```
2. **Scaffold the config** rather than writing JSON by hand:
   ```
   python3 "${CLAUDE_SKILL_DIR}/scripts/hooktool.py" scaffold --event PostToolUse --matcher "Edit|Write" \
     --type command --command '"$CLAUDE_PROJECT_DIR"/.claude/hooks/format.sh'
   ```
   Narrow a tool-event hook further with `--if 'Edit(*.ts)'`: one permission rule on the tool name and its arguments, and the handler's process is not started when it does not match.
3. **Write the handler.** A command hook reads the event JSON on **stdin**, does its work, and signals back: **exit 2 to block** (stderr is the reason), exit 0 to proceed, or stdout JSON for structured control. Exit 1 does not block.
   Which channel reaches Claude on which event is in the step 1 table and in "What reaches Claude" in [references/hooks-reference.md](references/hooks-reference.md), with the input and output fields and worked examples.
4. **Validate before installing** (exit 1 on errors; read the warnings too). Add `--plugin` for a plugin's hooks file:
   ```
   python3 "${CLAUDE_SKILL_DIR}/scripts/hooktool.py" validate .claude/settings.json
   ```
5. **Place it.** Project: `.claude/settings.json`. User: `~/.claude/settings.json`. Or a skill's or agent's `hooks:` frontmatter, where lifetimes differ - "Hooks in skills and agents" in the reference.

## Handlers are tools - hold them to the bar

A hook handler is a tool the harness calls, so the conventions in
[`choosing-extension-types/references/minimizing-model-work.md`](../choosing-extension-types/references/minimizing-model-work.md) ("Designing tools the
model calls") apply: read stdin, keep
**stdout for structured decisions** and **stderr for the human-readable reason**,
exit non-zero deliberately, and keep it fast - it runs synchronously on every
matched event. For side effects that must not block (logging, notifications),
add `"async": true` - `validate` warns when a gate has it. A gate that must not
fail open when its script is missing or crashes sets `"onFailure": "block"`.

## Bundled tool

`hooktool` documents itself; this is injected fresh at load so it can't drift:

!`python3 "${CLAUDE_SKILL_DIR}/scripts/hooktool.py" claudemd 2>/dev/null || echo "(hooktool docs unavailable - run hooktool.py with --help)"`

## Hooks in a plugin

A plugin ships hooks at `hooks/hooks.json` in the plugin root; they register when
the plugin loads, with no skill invoked first. The file's shape and its quoting
are asserted by `validate --plugin` (step 4). What it cannot assert: reach
bundled scripts through the plugin-root variable, never a hard-coded path - the
install path changes on every update - and keep state that must outlive an update
in the plugin data directory, not beside the scripts. Literal, copyable example:
"Hooks in a plugin" in the reference - spelled out there because those variables
are expanded to paths when this file loads.

## Delivering a rule on file touch from a plugin

Claude Code does not load a plugin's `rules/`, so a plugin that needs "when you
touch these files, this holds" delivers the rule itself: a `PostToolUse` hook on
`Read|Write|Edit` returns the rule text as `additionalContext` the first time a
session touches a matching file. To behave like a native path-scoped rule it
arrives once per context (the session and each subagent), again whenever that
context is lost, and not at all where the project already loads the rule
natively. Keep it to a few lines of judgement and the name of the skill with
the procedure - every session that touches such a file pays for it - and never
make it a gate: fail toward delivering twice rather than never. How this plugin
does each of those: the worked example under "Hooks in a plugin" in the
reference.

## Full event & protocol reference

Matcher and `if` evaluation, the stdin and stdout JSON fields, exit codes, and observed behaviour the tool's tables cannot express:
[references/hooks-reference.md](references/hooks-reference.md) and the official [hooks docs](https://code.claude.com/docs/en/hooks).
