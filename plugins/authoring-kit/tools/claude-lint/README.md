# claude-lint

The tool half of this plugin: every invariant that can be asserted, with its
reason, and the reference data the skills point at. It lives at
[`scripts/claude-lint`](../../scripts/claude-lint), a launcher for
`claude_lint.py` and `claude_lint_gate.py` beside it: Python 3,
standard library only.

## Where it lives, and how to run it

It is in `scripts/` on purpose (rule PL007 says why there is no `bin/`).
Nothing is on `PATH`, so the linter is always run by path:

```sh
python3 scripts/claude-lint --all .                                # from the plugin root
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" --all .        # from this plugin's skills, agents and hooks
```

`claude-lint` below is short for one of those two forms. A message that tells
you to run something spells the command out in full.

## Subcommands

| command | what it does |
| --- | --- |
| `claude-lint <path>...` | Lint files or directories. One finding per line, `path:line: SEV ID message`; `--json` for a structured report. Exit 1 on any error, 2 on a usage error or when the paths hold no artifact at all. Findings go to stdout; one line on stderr says how many artifacts were checked, so a clean run is told apart from one that matched nothing. |
| `claude-lint --all [ROOT]` | Lint every artifact under ROOT (default: cwd). |
| `claude-lint rules [--json]` | Every rule - id, severity, artifact kind, check and `why` - plus the numeric limits and, per kind, the rule file and skill that go with it. The source of truth for the rule set. |
| `claude-lint fields <skill\|agent\|rule> [FIELD] [--full] [--json]` | The frontmatter reference for one kind: a line per field (type or allowed values, default, effect cut to about 110 characters), then the kind-level notes, one per line. `FIELD` prints one field with each attribute on its own line; `--full` prints every effect whole. The only place the plugin states what a field is. |
| `claude-lint check-injection '<command>' [--allowed-tools '<value>'] [--plugin-skill] [--json]` | Would this injection pass the check Claude Code runs before a skill loads? Prints `loads` or `aborts`, each failing part with its reason, and the `Bash(...)` entry to add. Exit 0 loads, 1 aborts. |
| `claude-lint drift [--json]` | Compare the tables with the installed Claude Code. Exit 0 for no drift or nothing to compare, 1 for drift. |
| `claude-lint classify <path>` | Print the artifact kind, or exit 1. The same function decides what lint and hook mode look at. `classify --extensions` prints the file-name suffixes an artifact can have. |
| `claude-lint hook` | Hook mode, below. Exits 0, except for the auditor guard's block (2). |
| `claude-lint install-rules [--target DIR] [--dry-run] [--check]` | Copy the plugin's `rules/*.md` into `DIR/.claude/rules/` as `<plugin-name>-<rule>.md`. |

Every finding says what is wrong (with the measured value where there is one),
why the rule exists and what to do, so no rule file or skill has to be opened.
A markdown artifact opts out of named rules with
`<!-- claude-lint-disable RU005 SK012 -->`. Hook configs are validated by
`skills/authoring-hooks/scripts/hooktool.py validate`; `HK001` relays its verdict.

## drift

`drift` replaces a version stamp in each skill. It reads the installed build
(`claude` on `PATH`, symlinks resolved; a JavaScript bundle, or a binary with
the JavaScript inside) and compares the hook event names with
`hooktool events --json`, the skill and agent frontmatter schemas with the
`fields` tables in both directions, and the value sets the build keeps as
distinct lists (effort levels, permission modes, model aliases).

The first line is `tables verified against <v>; running <v>`; then the drift
or `no drift found`; then a list headed `NOT checked`. A schema is found by
the keys it holds, not by a minified name, and one that cannot be found is
reported as not checked, never as clean. After re-verifying, update the
tables and `TABLES_VERIFIED_AGAINST` in the script.

## Hook mode

`hooks/hooks.json` sends three events to `claude-lint hook`, each through a
shim that exits before Python starts unless the raw event could matter.

- **PostToolUse on `Read`, `Write`, `Edit`** (`lint-on-write.sh`, gated on the
  `classify --extensions` suffixes). It delivers the kind's rule file on first
  touch, as the worked example in the
  [hooks reference](../../skills/authoring-hooks/references/hooks-reference.md#worked-example---delivering-a-rule-on-first-touch)
  describes. A `Write` or `Edit` is then linted: at most 20 findings, and
  over 1 MiB one info line instead; both go out in one `additionalContext`.
  A `.py` Read costs 5 ms, a non-artifact `.md` or `.json` about 22 ms (the
  launcher imports only `claude_lint_gate`), an artifact Read or Edit about
  75 ms (means of 20 runs, 2026-10-14).
- **SessionStart, source `startup`, `clear` or `compact`**
  (`reset-rule-delivery.sh`). A delivery is a marker file per session, agent
  and kind under `<tmp>/claude-<plugin>-plugin/`. The reset removes one
  session's markers - on `startup` too, since a new session can arrive with an
  id that already has some - and prunes sessions unused for seven days. An id
  that is not one directory name (`..`, empty) gets nothing delivered or
  removed. Unwritable markers mean a rule every time, not never.
- **PreToolUse on `Bash`** (`auditor-bash-guard.sh`, gated on the agent's
  name). For the plugin's auditor agent alone, a command that is not exactly
  `python3 "<this script>" <args>` - no shell operators, no substitution, no
  `install-rules` that writes - is blocked: exit 2, the reason and the allowed
  form on stderr. Once a payload may be the auditor's, the shim fails closed: no
  linter, no `python3` or a crashed linter blocks the call, with the reason. An
  event that cannot be parsed blocks nothing. Any other Bash
  call costs 4 ms, a shell start being 3 (costs: means of 20 runs, 2026-10-11).

## install-rules

Copying is the only mode: a rule file that is a symlink to a target outside
the project is treated as an external import and a path-scoped one never
loads, so `--link` exits 2 and says why. A manifest of content hashes
(`.<plugin-name>-rules.json`, beside the copies) makes re-running safe:

- an unedited copy is refreshed when the plugin's rule changes;
- an edited copy, and a file `claude-lint` did not create, is left alone and
  reported, and the command exits 1;
- files left by a run under an earlier plugin name, and symlinks left by an
  earlier version, are replaced by copies.

`--check` changes nothing and exits 1 if any installed copy is missing, out of
date, modified or still a symlink - a project can assert it in CI. `--dry-run`
prints what a real run would do. The file prefix is the `name` in the plugin's
own `plugin.json`. Installing is optional: without it the hook delivers the
same rules.

## Tests

```sh
python3 -m unittest discover -s tests
```

`tests/test_claude_lint.py` covers the linter and the shims, and holds as data
what was observed of Claude Code where the docs are silent: the injection
permission probes, at-sign references, memory imports, and the descriptions
the file-keyed trigger check was tuned on. `drift` is tested on fixture
strings, and once against the installed `claude` when there is one.
