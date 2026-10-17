# Hooks reference

The detail behind [SKILL.md](../SKILL.md), loaded only when needed. The tool owns
the tables - `hooktool events` for events, `hooktool fields` for handler fields -
and the official [hooks reference](https://code.claude.com/docs/en/hooks) owns
each event's input schema; this file keeps the evaluation rules, the protocol and
observed behaviour. **(tested)** marks a statement confirmed by a headless
experiment on 2.1.295. `hooktool` throughout means
`python3 <this skill's directory>/scripts/hooktool.py`: the plugin puts nothing
on PATH, so there is no bare command.

## How a hook fires

When an event fires and a matcher group matches, Claude Code runs every handler
in the group, in parallel. The handler gets a JSON payload - on **stdin** for
`command` hooks, as the **POST body** for `http` hooks - and signals back through
its **exit code** and optionally **stdout JSON**.

The same handler defined in more than one settings file runs once; a plugin's or
skill's copy of it stays separate and runs as well. Hook entries merge across
settings levels rather than replacing each other.

## Events

`hooktool events` prints every event in lifecycle order: whether exit 2 blocks,
which field the matcher filters, whether plain stdout or `additionalContext`
reaches Claude, and the closed matcher values. `events --json` adds, per event,
the handler types it runs and a note on what exit 2 does there - read the note
before relying on stderr from an event that cannot block: it goes to Claude, the
user, the debug log or nowhere, depending on the event.

Two things the table cannot say:

- A handler of a type the event does not run is skipped without an error at run time (`hooktool validate` makes it one).
- On `SessionStart` an `mcp_tool` handler is skipped at launch, before MCP servers connect.

## Matchers

Omit `matcher`, or use `"*"` or `""`, to fire on every occurrence. A matcher on an
event that takes none is silently ignored, and a value outside an event's closed
set never matches (`hooktool events` lists the sets). Otherwise the characters
decide how it is evaluated:

| Matcher | Evaluated as | Example |
|---|---|---|
| only letters, digits, `_`, `-`, spaces, `,`, `\|` | exact string, or a list of exact strings separated by `\|` or `,` | `Bash`; `Edit\|Write`; `code-reviewer` |
| contains anything else | JavaScript regex, **unanchored** | `mcp__memory__.*`; `^Notebook`; `Edit.*` also matches `NotebookEdit` |

Consequences worth knowing:

- `mcp__memory` is an exact string and matches no tool. Write `mcp__memory__.*`. A plugin's own MCP tools are named `mcp__plugin_<plugin>_<server>__<tool>`.
- A plugin-scoped agent type such as `my-plugin:reviewer` contains a colon, so it is a regex: anchor it, `^my-plugin:reviewer$`.
- `FileChanged` and `StopFailure` use a narrower exact set (letters, digits, `_`, `|`).
- A `SubagentStop` matcher that names agent types does not match the empty `agent_type` of Claude Code's internal agents; an omitted matcher does.

**Tool names (tested, 2.1.295).** The file-writing tools are `Write`, `Edit` and
`NotebookEdit`. `MultiEdit` is not in the tool list any more; a matcher that
names it is dead weight. `NotebookEdit` carries `tool_input.notebook_path`, not
`file_path`. The subagent tool reports as `Agent`. A `PostToolUse` hook on
`Edit|Write` does not fire when a Bash command rewrites the file - use
`FileChanged` for "whatever wrote it".

## The `if` filter

`matcher` filters the group; `if` filters one handler, on the tool name **and its
arguments**, using permission-rule syntax. When it does not match, the handler's
process is never started.

```json
{ "matcher": "Write|Edit",
  "hooks": [ { "type": "command", "if": "Edit(*.ts)", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/lint-ts.sh" } ] }
```

- Only evaluated on the tool events: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `PermissionDenied`. On any other event a handler with `if` **never runs** (tested on `SessionStart`).
- Exactly one rule. There is no list, `|`, `||` or `&&` syntax; `"Write(a)|Edit(b)"` silently never runs (tested). Use one handler per rule.
- The tool name is matched literally (tested): `Edit(**/SKILL.md)` does not fire for a `Write` call, although `Edit(...)` *permission* rules cover every file-editing tool. Covering Write and Edit takes two handlers.
- File patterns (tested): `Write(*.md)` and `Write(**/*.md)` both match a `.md` file at any depth, including one outside the working directory. A single-segment directory pattern such as `Edit(src/**)` is rooted at the working directory; write `Edit(**/src/**)` for any depth.
- Bash patterns check each subcommand (`Bash(git *)` matches `npm test && git push`), and when Claude Code cannot parse the command the hook runs anyway. The filter is best-effort: enforce a hard allow or deny with permissions, not `if`.

## Handler types and fields

`hooktool fields [TYPE]` prints every field: which handler types take it,
required or optional, type, default and effect. What that table cannot express:

- **Timeout defaults are lower on some events**: 30 s on `UserPromptSubmit` and the model-switch events, 10 s on `MessageDisplay`; `SessionEnd` hooks share a 1.5 s budget.
- **`http`**: a non-2xx status is a *non-blocking* error; block with a 2xx JSON body.
- **`mcp_tool`**: the tool's text output is read like command stdout.
- **`prompt`** is a single-turn LLM judgement; **`agent`** is a subagent with tools, and experimental.
- **Shell form** (a `command` without `args`) runs through `sh -c`.
- **`onFailure: "block"`** has no effect on `Stop`, `SubagentStop`, `TaskCompleted`, `TeammateIdle`, or on background hooks. Without it a policy hook with a wrong path lets everything through.
- **`async`**: its `additionalContext` arrives on the next turn, and in `-p` mode a still-running async hook is killed at teardown.

## Stdin input

Common fields: `session_id`, `prompt_id`, `transcript_path`, `cwd`,
`scratchpad_dir`, `permission_mode`, `effort`, `hook_event_name`. Inside a
subagent (or with `--agent`): `agent_id`, `agent_type`.

Frequently used event fields:

- Tool events: `tool_name`, `tool_input`, `tool_use_id`; `PostToolUse` adds `tool_response` and `duration_ms`. `tool_input.command` for Bash; `tool_input.file_path` for `Write`/`Edit`/`Read` is **always absolute** (backslashes on Windows).
- `UserPromptSubmit`: `prompt`.
- `SessionStart`: `source`, sometimes `model`.
- `Stop` / `SubagentStop`: `stop_hook_active` (true when already continuing because of a stop hook - check it to avoid a loop) and `last_assistant_message`.

Extract with `jq`, e.g. `jq -r '.tool_input.command // empty'`.

## Exit codes

- **0** - success. Stdout that starts with `{` and ends with `}` is parsed as JSON output; anything else is plain text. Claude never sees stderr from a hook that exits 0.
- **2** - blocking error. On events that block, the action stops and stderr is the reason. JSON on stdout cannot override the block.
- **anything else** - non-blocking error: the action proceeds and the transcript shows a `hook error` notice. **Exit 1 does not block.** A policy hook must exit 2 (or set `onFailure: "block"`).

## Stdout JSON (exit 0)

- `hookSpecificOutput.additionalContext` - text for Claude's context. Requires `hookSpecificOutput.hookEventName`. Accepted on the events `hooktool events` marks ADDL-CONTEXT.
- `PreToolUse`: `hookSpecificOutput.permissionDecision` - `allow` / `deny` / `ask` / `defer`, with `permissionDecisionReason`; `hookSpecificOutput.updatedInput` rewrites the tool input.
- `PermissionRequest`: `hookSpecificOutput.decision` - `{ "behavior": "allow" | "deny", "updatedInput": ... }`.
- `PostToolUse`: `updatedToolOutput` replaces what Claude sees of the result.
- `decision: "block"` + `reason` (top level) - `UserPromptSubmit`, `UserPromptExpansion`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Stop`, `SubagentStop`, `ConfigChange`, `PreCompact`, `TaskCreated`. `"block"` is the only value.
- `continue: false` + `stopReason` - stops Claude entirely; takes precedence over event-specific decisions.
- `systemMessage` - a warning shown to the user.
- `suppressOutput` - accepted but has no effect; a successful hook's stdout is never shown in the transcript anyway.

`additionalContext`, `systemMessage` and plain stdout are each capped at 10,000
characters; beyond that Claude gets a file path and a 2,000-character preview.

## What reaches Claude

Plain stdout on exit 0 is added to Claude's context only on the four events
`hooktool events` marks STDOUT->CTX (`SessionStart` and `UserPromptSubmit` among
them). Everywhere else plain stdout goes to the debug log.

**`PostToolUse` (tested).** A hook on `Write` that printed a marker three ways:

| Handler output | Did the model receive it? |
|---|---|
| plain stdout, exit 0 | no |
| stdout JSON `hookSpecificOutput.additionalContext`, exit 0 | yes - as `PostToolUse:Write hook additional context: <text>` |
| stderr, exit 2 | yes - as `PostToolUse:Write hook blocking error from command: "<command>": [<command>]: <stderr>`; the write still happened |

So `additionalContext` is the feedback channel for a working hook; exit 2 also
reaches Claude but is labelled an error and repeats the hook's command line.

**`SessionStart` (tested).** Plain stdout arrives as
`SessionStart:startup hook success: <text>`. It fires once per session start
(`source` says which kind) and **not** for subagents: spawning a subagent fired
`SubagentStart` only, and the subagent did not see the `SessionStart` text. To
give subagents standing context, return `additionalContext` from a
`SubagentStart` hook. With no matcher the hook re-fires after `/clear`,
compaction, resume and fork, which is what a standing-context hook wants.

Write injected text as statements of fact ("This repo uses `bun test`"), not as
system-style commands, which can trip Claude's prompt-injection defences.

## Environment and paths

Every hook process gets `CLAUDE_PROJECT_DIR` (the project root; it stays put when
Claude enters a worktree - read `cwd` from the payload for where Claude is), and
`CLAUDE_EFFORT` when the model supports effort levels. Plugin hooks also get `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`
and `CLAUDE_PLUGIN_OPTION_<KEY>` per user-config value. `SessionStart`, `Setup`,
`CwdChanged` and `FileChanged` hooks get `CLAUDE_ENV_FILE`: append `export`
lines to it to set variables for later Bash commands. `CLAUDE_CODE_REMOTE` is
`"true"` in cloud sessions.

`${CLAUDE_PROJECT_DIR}`, `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` are
also substituted as placeholders in `command` and `args`. Handlers run in the
session's current directory, so reference scripts through a placeholder, never a
relative path.

## Hooks in skills and agents

Hooks can live in a skill's or subagent's `hooks:` frontmatter, in the same
shape as in settings.

- **Skill**: registered when the skill is invoked and kept **for the rest of the session**, not just the skill's turn.
- **Subagent**: active only while that subagent runs. A `Stop` hook there is converted to `SubagentStop`.
- **Plugin subagent**: its hooks go in the plugin's `hooks/hooks.json` with an agent-type matcher, because frontmatter `hooks` is among the fields `claude-lint fields agent` marks as ignored there.

Settings, managed and plugin hooks also fire **inside** subagents for their tool
calls, with `agent_id` and `agent_type` in the payload.

## Hooks in a plugin

A plugin ships hooks in `hooks/hooks.json` at the plugin root, and may add more
through the `hooks` key of `plugin.json` (a path, an inline object, or an array
of either). Both load and merge. They register when the plugin loads - no skill
has to be invoked first - and changes need `/reload-plugins` or a restart.

- **A hooks file needs the outer `{"hooks": {...}}` wrapper.** A file holding only the event map fails to load, with no hook firing and nothing in the transcript (tested). A top-level `description` is allowed. The inline object in `plugin.json` is the event map itself, without a wrapper (tested).
- **Paths go through `${CLAUDE_PLUGIN_ROOT}`**, never a hard-coded path; the install path changes across updates and can contain spaces. `${CLAUDE_PLUGIN_DATA}` is the directory for state that survives updates.
- **Quoting.** In shell form wrap the placeholder in double quotes; exec form needs none. With the plugin installed under a directory named `my plug` (tested), `sh "${CLAUDE_PLUGIN_ROOT}/hooks/x.sh"`, `sh "$CLAUDE_PLUGIN_ROOT/hooks/x.sh"` and exec-form `sh` + `["${CLAUDE_PLUGIN_ROOT}/hooks/x.sh"]` ran; unquoted `sh ${CLAUDE_PLUGIN_ROOT}/hooks/x.sh` did not.

```json
{
  "description": "rule on first touch, lint on write",
  "hooks": {
    "SessionStart": [
      { "matcher": "startup|clear|compact",
        "hooks": [ { "type": "command", "command": "sh \"${CLAUDE_PLUGIN_ROOT}/hooks/reset-rule-delivery.sh\"", "timeout": 10 } ] }
    ],
    "PostToolUse": [
      { "matcher": "Read|Write|Edit",
        "hooks": [ { "type": "command", "command": "sh \"${CLAUDE_PLUGIN_ROOT}/hooks/lint-on-write.sh\"", "timeout": 30 } ] }
    ]
  }
}
```

The docs now prefer exec form for placeholder paths
(`"command": "sh", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/x.sh"]`). The quoted
shell form above stays correct and is the safer choice for a plugin that may be
loaded by an older Claude Code that does not know `args`.

`${user_config.KEY}` is substituted in exec-form `args` only. A shell-form plugin
hook that references it fails instead of running; read
`$CLAUDE_PLUGIN_OPTION_<KEY>` from the environment there.

`hooktool validate hooks/hooks.json` asserts the wrapper (an error) and the
quoting (a warning); `claude plugin validate .` checks the whole plugin.

### Worked example - delivering a rule on first touch

The config above is this plugin's own `hooks/hooks.json`, less the `PreToolUse`
group that holds its auditor's Bash to the linter. Claude Code does not load a
plugin's `rules/`, so the `PostToolUse` hook delivers them:

- **The shim decides nothing.** `lint-on-write.sh` exits before starting Python unless the payload holds a string ending in `.md"` or `.json"` (the shell pre-filter of "Keeping a per-edit hook cheap"), then hands the event to `claude-lint hook`. Which paths are artifacts, and of which kind, is the linter's `classify` - no path list in the shell or the config.
- **First touch of a kind** by the session, or by a subagent (keyed on `agent_id`), prints one JSON object whose `additionalContext` is that kind's rule file, frontmatter removed, headed `[<plugin>] rule <name>` and closed with the linter command, written with the install's real path. The first one a session receives is led by the prefer-code litmus. On a `Write` or `Edit` the same object carries the lint findings after it.
- **Once** is a marker file created exclusively under the temp directory, per plugin, session, agent and kind - session state, so not `${CLAUDE_PLUGIN_DATA}`. If the marker cannot be written the rule is delivered every time instead of never.
- **Reset**: `reset-rule-delivery.sh` drops the session's markers on a `SessionStart` with source `clear` or `compact`, when the delivered text has left context, and `startup`, because a new session can carry an id that already has markers. Not `resume`. It prints nothing - `SessionStart` stdout becomes context.
- **Skipped** for a kind whose rule is installed in the project's `.claude/rules/` where that copy's `paths` match the file: Claude Code loads it natively. The litmus and the linter command still arrive, once.
- **Always exits 0**, and is a no-op when `python3` or the linter cannot be found.

## Keeping a per-edit hook cheap

A `PostToolUse` hook on `Write|Edit` starts a process for every edit, synchronously.
Three ways to keep that small, cheapest first:

- **An `if` filter** means no process at all for non-matching files, at the cost of one handler per tool-and-pattern pair (`Write(*.md)`, `Edit(*.md)`, ...), which puts a path list in the config.
- **A shell pre-filter**: read stdin with shell builtins and exit before starting an interpreter unless the payload could be relevant. Measured on a Python linter hook: about 58 ms per edit when every edit starts Python, about 3 ms with a builtin-only extension test in front. The price is a second copy of "which files matter" outside the tool that owns that decision.
- **`async: true`** when Claude does not need the result on this turn.

## Managing hooks

- `/hooks` opens a read-only browser of every configured hook and where it comes from.
- `"disableAllHooks": true` in settings turns all hooks off (managed hooks only from managed settings). For one run: `--settings '{"disableAllHooks": true}'`. There is no per-hook disable.
- `allowManagedHooksOnly` (managed settings) blocks user, project, local and plugin hooks.
- Edits to hooks in settings files are picked up by the file watcher; `claude --debug` writes each hook's output and outcome to `~/.claude/debug/<session-id>.txt`.

## Testing a hook headless

Run `claude -p "<prompt>" --output-format stream-json --verbose` in a scratch
project and have the handler append its stdin to a log file: the log shows what
fired and with what payload, and asking the model to quote a marker shows what
reached it. Two things to expect (tested):

- A write under `.claude/` is a protected-path write. In `-p` mode it is refused as "a sensitive file" with `--allowedTools Write`, with an `Edit(...)` allow rule, and in `acceptEdits` mode; only `bypassPermissions` lets it through. A refused write fires no `PostToolUse` hook.
- An installed copy of a plugin and a `--plugin-dir` copy both run their hooks. Disable the installed one for the run with `--settings '{"enabledPlugins": {"<name>@<marketplace>": false}}'`.

## Worked examples

**Format after every edit** (`PostToolUse`, nothing to report):

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Edit|Write",
        "hooks": [ { "type": "command", "command": "jq -r '.tool_input.file_path' | xargs prettier --write" } ] }
    ]
  }
}
```

**Block reads of secret files** (`PreToolUse`, exit 2):

```bash
#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
case "$FILE" in
  *.env|*/.git/*) echo "Blocked: $FILE is protected by policy." >&2; exit 2 ;;
esac
exit 0
```

Register it with `"onFailure": "block"` if a missing script must not fail open.

**Report linter findings to Claude** (`PostToolUse`, `additionalContext`): the
edit has already happened, so the job is feedback, not blocking. Print the JSON
below on stdout and exit 0 - findings echoed as bare text never reach Claude.

```bash
#!/bin/bash
FILE=$(jq -r '.tool_input.file_path // empty')
[ -n "$FILE" ] || exit 0
FINDINGS=$(ruff check --quiet "$FILE" 2>&1) && exit 0   # clean: say nothing
jq -n --arg ctx "Lint findings for $FILE - fix before continuing:
$FINDINGS" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
exit 0
```

which emits, for example:

```json
{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"Lint findings for src/app.py - fix before continuing:\nF401 `os` imported but unused"}}
```

**Keep working until tests pass** (`Stop`, exit 2): a handler that runs the suite,
exits 0 to allow stopping when green, or prints a reason to stderr and exits 2 to
push Claude to continue. Guard with `stop_hook_active` so it cannot loop forever
(Claude Code also caps consecutive continuations at 8).

## Sources

- Hooks reference: https://code.claude.com/docs/en/hooks
- Hooks guide: https://code.claude.com/docs/en/hooks-guide
- Plugins reference: https://code.claude.com/docs/en/plugins-reference
