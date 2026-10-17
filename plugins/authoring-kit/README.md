# authoring-kit

A Claude Code plugin for authoring Claude Code extensions: deciding **which extension type** a thing should be (CLAUDE.md, rule, skill, subagent, hook), **how to author** each, and **how to keep** a growing set honest - with a linter, a hook and a test suite that hold the plugin to its own advice. [PHILOSOPHY.md](PHILOSOPHY.md) is the why, [CHANGELOG.md](CHANGELOG.md) is what changed, and this page is the map.

> **This README is for people, not the agent.** Claude Code does not load a plugin's README into context - it is the detail page for someone browsing or installing. People start from two commands: `/authoring-kit:choosing-extension-types` to decide which extension type something should be, and `/authoring-kit:reviewing-extensions [path]` to audit what exists. The agent reaches the same skills by description and, more dependably, through the rule the hook delivers when it first touches an artifact.

## Structure

```
authoring-kit/
├── .claude-plugin/plugin.json   # manifest
├── skills/                      # judgement and procedure, one skill per extension type
│   ├── choosing-extension-types/ # gate, then selector; + two references
│   ├── reviewing-extensions/    # /authoring-kit:reviewing-extensions: runs the auditor on a path
│   ├── authoring-memory/        # CLAUDE.md and AGENTS.md; + references/imports.md
│   ├── authoring-rules/
│   ├── authoring-skills/        # + references/body-grammar.md
│   ├── authoring-agents/
│   ├── authoring-hooks/         # + scripts/hooktool.py, references/hooks-reference.md
│   └── wrapping-api-calls/      # reaching API guarantees through a tool
├── agents/authoring-auditor.md  # read-only judgement review; runs the linter for the rest
├── scripts/claude-lint          # lint rules, reference tables, hook mode; one stdlib Python file
├── hooks/
│   ├── hooks.json
│   ├── lint-on-write.sh         # PostToolUse: thin shim in front of `claude-lint hook`
│   ├── auditor-bash-guard.sh    # PreToolUse: holds the auditor's Bash to the linter
│   └── reset-rule-delivery.sh   # SessionStart: forget what was delivered; prints nothing
├── rules/                       # one short rule file per artifact kind, delivered by the hook
├── tests/                       # stdlib unittest: linter, hooktool, consistency guard
└── tools/claude-lint/           # design notes for the linter
```

Below, `claude-lint` means `python3 scripts/claude-lint` from the plugin root (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint"` inside a session) and `hooktool` means `python3 skills/authoring-hooks/scripts/hooktool.py`.

### Works on

Claude Code (CLI) and claude.ai / Cowork. That is why there is no top-level `bin/` directory: the plugin docs say claude.ai and Cowork don't install a plugin that has one. The executables live in `scripts/` and inside the hooks skill instead, nothing is on PATH, and everything calls them by path.

## Division of labour

The plugin's own litmus - if you could write an assertion for it, write code; if you would need a rubric, write prose - decides where everything lives. **The tools assert and tabulate**: `claude-lint` holds every assertable invariant with its reason and its limit (`rules`), the frontmatter reference (`fields`), whether an injection will load (`check-injection`) and whether any of that has gone stale (`drift`); `hooktool` holds the hook event and handler tables (`events`, `fields`). **Rule files and skills carry judgement**: a rule file is a few bullets, the skill to invoke and one line handing the rest to the linter; a skill says when to set a field and what the trap is, never what the field is. **The hooks deliver and enforce** (next section). **Descriptions match intent**: what a user asks for, never which file is being touched. Each fact has one home, and everything else points at it.

## What the agent actually reads

- **skills/** - descriptions are always in context; a body loads when its description matches the request. Each `skills/<name>/` is `authoring-kit:<name>`. `reviewing-extensions` is typed only: its description is not in context and the model cannot invoke it. One body, authoring-hooks, injects `hooktool`'s own documentation at load, and it is the only skill with an `allowed-tools` entry.
- **hooks/** - registered when the plugin is enabled. `PostToolUse` on Read, Write and Edit passes anything that could be an artifact to `claude-lint hook`, which delivers the kind's rule file on first touch (per session and per subagent, again after `/clear` or compaction) and lints on Write and Edit. The prefer-code litmus no longer runs in every session: it arrives once, with the first rule a session receives. `PreToolUse` blocks any Bash command from the auditor other than the linter. `claude-lint classify <path>` says what counts as an artifact.
- **rules/** - not a plugin component, so Claude Code never loads it from here. The hook delivers these files; `install-rules` (below) is the native alternative.
- **agents/** - the auditor's description is in context and its body loads on dispatch. It preloads `choosing-extension-types` and reads that skill's reference before judging.
- **scripts/** - never context. The linter and `hooktool` are commands run by path.
- **Never loaded**: this page, PHILOSOPHY.md, CHANGELOG.md, `tools/claude-lint/` and `tests/`. A skill's `references/` are read only when its SKILL.md sends the agent there.

## Install

From a marketplace (Claude Code 2.1.275 or later):

```
/plugin install authoring-kit --marketplace bruk-io/knowhere
```

Local development, from the directory that holds the checkout, then from the plugin's root:

```
claude --plugin-dir ./authoring-kit        # load it for one session
/reload-plugins                            # pick up edits in-session
claude plugin validate ./authoring-kit     # the authority on the manifest

python3 -m unittest discover -s tests      # linter, hooktool and the consistency guard
python3 scripts/claude-lint --all .        # the plugin lints itself; stderr says how many artifacts it checked
python3 scripts/claude-lint rules          # every rule with its reason, and the limits
python3 scripts/claude-lint fields skill   # the frontmatter reference (also: agent, rule; add a field name for one field)
python3 scripts/claude-lint drift          # compare the tables with the installed Claude Code
```

### Installing the rules into a project

Optional: without it the hook delivers the same files. Installing copies them into the project's `.claude/rules/` as native path-scoped rules, and the hook then stays quiet where a copy applies. Re-running is safe; [tools/claude-lint/README.md](tools/claude-lint/README.md) says what it refreshes, what it leaves alone and why it never links. From the project's root, with `LINT` set to the path of `scripts/claude-lint`:

```
python3 "$LINT" install-rules --dry-run    # show what would be written
python3 "$LINT" install-rules              # copy rules/*.md in as authoring-kit-<rule>.md
python3 "$LINT" install-rules --check      # change nothing; exit 1 if a copy is missing, stale or edited
```

### Upgrading from claude-authoring

The plugin was renamed from `claude-authoring` in 0.2.0, because `claude plugin validate` reserves names that start `claude-`. Coming from 0.3.0 instead, the breaking changes are marked in the [CHANGELOG](CHANGELOG.md).

- **Remove the old plugin.** Claude Code still loads it, so with both installed both sets of skills load and both sets of hooks fire.
- **Cross-references changed prefix.** Your own pointers at the old namespace need `authoring-kit:`, as in `Skill(authoring-kit:authoring-skills)`.
- **Re-run `install-rules`** in each project: files left under the old name are recognised and replaced.
- **Nothing is on PATH.** A script or permission rule that called the linter or `hooktool` by bare name needs the full path.

## Status

`v0.7.0` - the plugin passes its own checks, and its tables were verified against Claude Code 2.1.296. `claude-lint drift` says whether that still holds for the build you run.

Still open:

1. **One container, two versions, one small model.** Verified headless and interactively through tmux in one Linux container, on 2.1.295 and 2.1.296, with a small model driving. Not verified: a real claude.ai or Cowork install.
2. **Hook latency.** A Read or Write of a `.md` or `.json` file that is not an artifact costs about 22 ms (Python start-up and a small gate module), an artifact about 75 ms. A `.py` costs about 5 ms, because the shell shim exits first. Where the plugin directory is read-only, compiled code is cached in a private per-user directory under `~/.cache` (or `$XDG_CACHE_HOME`), or not at all.
3. **`drift` cannot check everything**, and says so in its own output: types, defaults, effects, the limits and the injection permission model have nothing in the build to compare against.
4. **The `fields` tables' effects are prose** from the docs as of 2.1.296. `drift` catches a field that appears or disappears, not one whose behaviour changes.
5. **Two plugins, two rules.** With the owner's `philosophy` plugin also enabled, one file touch gets a rule from each plugin.
6. **`choosing-extension-types` rarely loads by itself.** In evals on 2.1.296 (as `authoring-foundations`), "which extension type should this be" questions loaded it in 0 of 16 small-model runs and about a quarter of mid-model runs; the model answers directly. Three rewritten descriptions did not beat that on held-out prompts. So the front door is a typed command, `/authoring-kit:choosing-extension-types`, and once a file exists the delivered rule names the right skill. The per-extension type skills trigger well on a mid-size model and poorly on a small one.
7. **Some prose still mirrors a table cell.** The single-owner test guards nine facts, not all of them; the rest are held by review.
