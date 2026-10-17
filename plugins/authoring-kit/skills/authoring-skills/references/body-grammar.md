# Skill body grammar - exact syntax

The literal, copyable syntax behind the "Body grammar" section of
[SKILL.md](../SKILL.md), which holds the judgement (when to inject, why a
fallback, what to bound). The literals live here because a SKILL.md body is
preprocessed at load and a reference file, read on demand, never is.

> Behaviour marked "observed" was seen by loading probe skills headless on
> Claude Code 2.1.295. Everything else is from the skills docs
> (https://code.claude.com/docs/en/skills, checked 2026-10-09), which now
> document most of what used to be observation only.

## Where the grammar applies

| File | Preprocessed? |
| --- | --- |
| `SKILL.md` body (and `.claude/commands/*.md`) | Yes - directives run, placeholders substitute |
| A skill's `references/` and other supporting files | No - plain text when Read |
| Subagent bodies in `.claude/agents/` or `~/.claude/agents/` | No - arrives as literal text (observed) |
| Subagent bodies in a plugin's `agents/` | Only the plugin path variables expand (which: the plugin-agent note in `claude-lint fields agent`); directives and argument placeholders stay literal (observed) |
| Rule files and CLAUDE.md | No - arrives as literal text |
| A skill synced from claude.ai, run on your machine | Directives never run; `@` references and some variables stay literal |

## Dynamic context injection

The command runs locally before the model sees the skill; its output replaces
the directive. Substitution is one pass over the original file: output is
inserted as plain text and is not re-scanned, so a command cannot emit a
directive for a later pass.

Inline - an exclamation mark immediately followed by a backtick-quoted command.
It is recognised only at the start of a line or straight after whitespace; glued
to another character, as in ``KEY=!`cmd` ``, it is left as text and does not
run:

```text
Current branch: !`git branch --show-current 2>/dev/null || echo "no data: not a git repository"`
```

Fenced, for multi-line - a code fence whose opening line is three backticks
followed by an exclamation mark:

````text
```!
git status --short 2>/dev/null | head -30 | grep . || echo "no data: clean tree or not a git repository"
git log --oneline -5 2>/dev/null || echo "no data: no commits yet"
```
````

### The fallback pattern

A command that exits non-zero aborts the whole skill invocation, not just its
own directive: Claude never sees the body, and the user gets
`Shell command failed for pattern "..."` with the output under `[stderr]`
(docs; observed with an exit code of 3). The one carve-out is exit code 1 from
search and comparison commands such as `grep` and `diff`, which is treated as a
normal result. With the default bash shell stderr is merged into the injected
text. Silencing it with `2>/dev/null` does not change the exit status, so that
alone still aborts (observed). Silence it and chain an echo so the skill
degrades into something actionable instead of failing to load:

```text
!`cmd 2>/dev/null || echo "no data: <reason>"`
```

The docs' own idiom for a command expected to exit non-zero is a trailing
`|| true`; the echo form is the same guard with a reason attached. `claude-lint`
rule SK005 flags a directive with neither.

### Reading an environment variable

Ordinary shell variables written in body text (`$VAR`) are not expanded. Read
one with `printenv`, pre-approved for that one name:

```text
allowed-tools: Bash(printenv DEPLOY_ENV)

!`printenv DEPLOY_ENV 2>/dev/null || echo "no data: DEPLOY_ENV is not set"`
```

The obvious `echo $VAR` does not load: an echo that expands a variable fails the
permission check, quoted or not, and a `Bash(echo *)` entry does not rescue it
(observed; only `$HOME`, and `$USER` inside double quotes, got through without
blanket `Bash`).

### Bounding the output

The cap goes in the command itself, as a pipe into `head`. That pipe also
guards the exit status - a trailing `head` succeeds even when the command
before it failed - but for the same reason a fallback chained after it never
fires, and the body gets an empty result. Put `grep .` after `head` to turn
empty output into the fallback (it also drops blank lines). Each command also
runs under the Bash tool's default 2-minute timeout:

```text
!`git diff --stat 2>/dev/null | head -40 | grep . || echo "no data: no diff"`
!`gh pr view --json title,body 2>/dev/null | head -c 4000 | grep . || echo "no data: no PR for this branch"`
```

The second needs `allowed-tools: Bash(gh pr view *)`; `git diff`, `head` and
`grep` pass as read-only. Do not put the fallback inside the pipe by wrapping
it in parentheses or braces - `(cmd || echo ...) | head` fails the permission
check unless the skill has blanket `Bash` (all observed on 2.1.295).

## Argument substitutions

| Form | Substitutes |
| --- | --- |
| `$ARGUMENTS` | All arguments as typed |
| `$ARGUMENTS[N]` | The Nth argument, 0-based (`$ARGUMENTS[0]` is the first) |
| `$N` | Shorthand for the same (`$0`, `$1`, ...) |
| `$name` | A named positional declared in `arguments` frontmatter (`arguments: [issue, branch]` or `arguments: issue branch` gives `$issue` and `$branch`) |

If no placeholder of any of these kinds receives an argument, the arguments are
appended to the end as `ARGUMENTS: <value>`.

Indexed arguments use shell-style quoting: `/my-skill "hello world" second`
makes `$0` expand to `hello world`. An indexed placeholder with no argument at
its position stays in the text unchanged (`$3` stayed `$3`, observed); a named
placeholder with no argument becomes an empty string. An argument value that
itself contains `$1` or `$ARGUMENTS` is inserted literally, not expanded again.

## Built-in variables

All six are documented and were also observed expanding on 2.1.295.

| Variable | Expands to | Where |
| --- | --- | --- |
| `${CLAUDE_SESSION_ID}` | The current session id (a UUID) - for logging and session-scoped files | Any skill |
| `${CLAUDE_EFFORT}` | The active effort level: `low`, `medium`, `high`, `xhigh` or `max` - adapt instructions to it | Any skill |
| `${CLAUDE_SKILL_DIR}` | Absolute path of the directory holding this SKILL.md (for a plugin skill, its subdirectory, not the plugin root) | Any skill |
| `${CLAUDE_PROJECT_DIR}` | Absolute path of the project root | Any skill, v2.1.196 or later |
| `${CLAUDE_PLUGIN_ROOT}` | Absolute path of the plugin's installed version; changes on update, so never write state there | Plugin skills only - literal elsewhere |
| `${CLAUDE_PLUGIN_DATA}` | The plugin's persistent data directory, `~/.claude/plugins/data/<id>/`, kept across updates | Plugin skills only - literal elsewhere |

The four path variables are substituted in two places: the body, and Bash rules
in `allowed-tools`. Using the same variable in both is the documented way to run
a bundled script without a prompt:

```text
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/render.sh *)
```

They are text substitutions, not environment variables. Commands Claude runs
later through the Bash tool do not have `CLAUDE_PLUGIN_ROOT` in their
environment, so the body has to carry the expanded path:
`${CLAUDE_PLUGIN_ROOT}/scripts/<tool>` for a plugin's tool,
`${CLAUDE_SKILL_DIR}/scripts/<tool>` for a skill's own.

A plugin with `userConfig` also gets `${user_config.KEY}` substituted in skill
and agent content, non-sensitive values only (plugins reference; not probed).

Typical uses:

```text
allowed-tools: Bash("${CLAUDE_SKILL_DIR}/tools/check.sh")

Run the bundled checker: !`"${CLAUDE_SKILL_DIR}/tools/check.sh" 2>/dev/null || echo "no data: check.sh failed"`
The full reference is at `${CLAUDE_SKILL_DIR}/references/details.md` - Read it when needed.
```

Without the entry the injection aborts the load: a skill's own script is not a
read-only command (observed). The last line is how a skill hands out an
absolute path to its own reference file, which matters when the skill is
preloaded into a subagent whose working directory is the project, not the
skill.

## Escaping - only argument placeholders have one

- **Argument placeholders**: a single backslash directly before the dollar sign
  keeps the token literal and the backslash is dropped - `\$1.00`, `\$ARGUMENTS`,
  `\$0` or `\$issue` for a declared name (docs; observed). A doubled backslash
  does not escape: both stay and the placeholder still expands. A backslash
  before any other dollar sign (`\$HOME`) is left as it is.
- **Braced variables**: no escape. A backslash before one is kept and the
  variable is still substituted (docs; observed).
- **Injection directives**: no documented escape. A backslash before the
  exclamation mark does stop the directive, but the backslash stays visible in
  what the model reads (observed). Gluing the exclamation mark to a preceding
  non-space character also stops it, by the start-of-line-or-whitespace rule
  above.
- Inline code spans and ordinary fenced blocks do not protect anything:
  substitution and execution happen inside them too (observed).

## Injections are permission-checked

Injected commands never prompt. Every part of each command - each stage of a
pipeline, each side of an `||` or `&&` chain - is checked against the
permission rules before the skill loads, and anything short of an allow aborts
the invocation with `Shell command permission check failed for pattern "..."`
(docs; observed headless and interactive; in auto mode the command is handed
to Claude to run first instead).
Recognised read-only commands pass with no entry; anything else, a bundled
script included, needs a narrow `allowed-tools` entry for exactly that
command, never blanket `Bash`. Quote a path the same way in the entry and the
command, as in the checker example above.

Which commands count as read-only, and which shapes abort whatever the entry,
is not worth memorising. The linter gives the verdict for any command, names
the part that fails and prints the entry to add (run it by the path SKILL.md
shows), and rule SK013 runs the same check after every write:

```text
claude-lint check-injection '<command>' [--allowed-tools '<value>'] [--plugin-skill]
```

Two switches turn injection off altogether: `disableSkillShellExecution: true`
in settings replaces each directive with
`[shell command execution disabled by policy]`, and directives in skills synced
from claude.ai never run on the user's machine (v2.1.228 or later).

## At-sign file references

An at-sign immediately followed by a path attaches that file when the skill
loads, as if Claude had read it, together with the CLAUDE.md files of its
directory and parents:

```text
Follow the conventions in @docs/api-conventions.md.
```

Observed on 2.1.295 with a decoy file in the session directory:

| Written in the SKILL.md body | Attached? |
| --- | --- |
| `Follow @decoy.txt` in running text | yes |
| the same line inside a fenced code block | yes |
| a code span that opens with the at-sign: `` `@decoy.txt` `` | no |
| a code span with text before it: `` `import @decoy.txt` `` | yes |

- The path resolves from the **session's working directory**, not the skill
  directory. It suits small, always-relevant project files in a project
  skill; it cannot reach the skill's own
  references - hand those out as `${CLAUDE_SKILL_DIR}/references/<file>` and
  let Claude Read them.
- Nothing escapes it except the leading-backtick form, so a body that shows
  import or mention syntax as an example attaches whatever matching file the
  user's project happens to hold. Keep such examples in a reference file.
- `claude-lint` checks that a reference resolves (SK009) and flags a live one
  that looks unintended (SK015).
