# Changelog

Versions are the `version` in `.claude-plugin/plugin.json`. Breaking changes are marked.

## 0.7.0 - 2026-10-15

- Skill descriptions now say when to load relative to the task and what Claude gets wrong without the skill. Measured on Haiku, these were the two changes that moved triggering; third person, example-phrase lists and implementation detail made no difference. `authoring-skills` teaches it (the `description` bullet), the `skill-invariants` rule says it, and all seven model-invoked kit skills follow it. The kit's own skills fire far more often (authoring-hooks 2/11 to 11/11), with no new near-miss firing.
- Skills written with the kit fire more often too: 98% of should-fire prompts at default effort, against 86% for skills written without it (low effort: 96% against 71%, with 4 false fires in 80).
- `evals/description_e2e.py`: a two-stage check that has Claude write a skill, with and without the kit, then measures how often the written skill loads on its own trigger prompts and near-misses. Five `description-e2e` cases feed it.
- The description graders in `never-triggers` and the new cases test when to load and why; eight new judge-calibration cases cover them.
- Harder near-misses for hooks (husky, GitHub Actions, webhooks, React and pytest hooks) and memory (CONTRIBUTING.md, an ADR).
- Write-ups with the data: `evals/experiments/2026-10-14-hooks-triggers/` and `evals/experiments/2026-10-15-description-e2e-baseline/`.

## 0.6.0 - 2026-10-14

- An eval suite under `evals/` for `claude plugin eval`: six cases phrased as a user would ask, where the kit's advice should change the result, and one unrelated request where none of its skills may fire. Writes into `.claude/` are refused inside plugin eval, so the file cases grade the Write Claude attempted.
- **Breaking: three skills are renamed** to gerund names specific enough not to collide with other plugins' commands, using the docs' word for these things, "extensions": `design` is `choosing-extension-types`, `review` is `reviewing-extensions`, and `api-features` is `wrapping-api-calls`. The `authoring-*` skills keep their names. Update any `Skill(authoring-kit:...)` pointer or `skills:` preload of your own.
- `choosing-extension-types` no longer claims audits in its description, which left it competing with the auditor agent; whole-artifact reviews are `/authoring-kit:reviewing-extensions`.
- The prose says "extension type" where it said "primitive", matching the docs.
- `reviewing-extensions` with no path audits the working directory and lets the linter decide what counts. From the home directory it asks for a path instead of auditing personal configuration.

## 0.5.1 - 2026-10-14

From running `/authoring-kit:review` on the plugin itself:

- **Breaking: `claude-lint` exits 2 when its paths hold no artifact at all**, and every text-mode run prints one line on stderr, `N artifacts checked: E error, W warn, I info`. `--json` adds `artifacts` to the summary. A clean run and a run against the wrong directory used to look the same: no output, exit 0.
- The auditor's Bash guard fails closed. Once a payload may be the auditor's, a missing linter, a missing `python3` or a crashed linter blocks the call with the reason; every other session's Bash is unaffected.
- `api-features` is described in what a user asks for ("this must always return valid JSON", "make it cite where each answer came from") instead of API terms.

## 0.5.0 - 2026-10-14

- **Breaking: `authoring-foundations` is renamed `design`.** It is now typed as `/authoring-kit:design`. Evals showed its description almost never loads it - the model answers "which primitive?" itself - so the dependable front door is a command a person types, and that should be short. Update any `Skill(authoring-kit:authoring-foundations)` pointer or agent `skills:` preload of your own. The auditor now preloads it by its qualified name, `authoring-kit:design`, because a bare `design` is easily shadowed by a project skill of the same name.
- New command `/authoring-kit:review [path]`: runs the auditor agent on a path (by default the project's `.claude/` tree, its memory files and, in a plugin, the plugin root) and waits for its report. It is typed only - the model cannot invoke it - so a review no longer depends on the model choosing to delegate.
- A skill that declares `argument-hint` may use `$ARGUMENTS` in its body; the consistency test still rejects a literal placeholder anywhere else. `review` uses it.
- Pointers at the gate and seam reference are now links (`design/references/minimizing-model-work.md`) the linter resolves, instead of prose.
- SK009 (and PL003) now report a link whose target contains a space and does not exist. Such a link renders as plain text, so it was skipped before; the rename above produced one.

## 0.4.1 - 2026-10-14

- The hook is cheaper. The linter is now `scripts/claude_lint.py` and `scripts/claude_lint_gate.py` behind the `scripts/claude-lint` launcher, so Python caches the compiled code, and a touch of a file that is not an artifact imports only the small gate module: about 22 ms instead of 70. Where the plugin directory is read-only the cache goes in a per-user directory only that user can write, never a shared temp directory. The command is unchanged.
- Facts that two files stated now have one home: rule loading and compaction (authoring-rules), what `/context` and `InstructionsLoaded` show (authoring-memory), what a fork cannot see (authoring-skills), how the rule-delivery hook behaves (the hooks reference), and the plugin-agent and preload notes (`claude-lint fields agent`). The consistency test guards two more of them.
- Restored, checked against the docs: to stop an agent invoking skills, deny `Skill`; a `permissions.allow` rule holds for the whole session; a teammate does not get its definition's `skills`; a channel's permission relay lets any allowlisted sender approve tool use; and a check that a `context: fork` skill really forked.

## 0.4.0 - 2026-10-11

The plugin was breaking its own advice in three places. This release moves each to where the philosophy says it belongs.

- **Breaking: `claude-lint stamp` is removed**, along with the version stamp in six skills. `claude-lint drift` replaces it: it compares the linter's and `hooktool`'s tables with the installed Claude Code and lists what it could not check. With the stamps went the `allowed-tools` entries that pre-approved them, so those six skills no longer show a "Use skill?" prompt when the model loads them.
- **Breaking: rule ids SK011 and SK014 are removed.** Drop them from any `claude-lint-disable` comment or script that names them.
- **Breaking: AG001 no longer treats an agent `name` outside lowercase letters, digits and hyphens as an error.** It is a warning. Only what Claude Code actually rejects is an error: a leading hyphen, a colon, or a name that is too long.
- **Breaking: the rule files changed content.** Each is now a few bullets of judgement, the skill to invoke, and one line saying the linter owns the rest. Re-run `install-rules` in a project that has copies; `install-rules --check` reports the stale ones.
- The hook delivers the matching rule file the first time a session, or a subagent, touches an artifact of each kind. It now runs on Read as well as Write and Edit, delivers again after `/clear` or compaction, and stays quiet where `install-rules` has put the rule in the project. `install-rules` remains as the native alternative. The session-start litmus no longer runs in every session: it is delivered once, with the first rule a session receives.
- Every lint finding states its reason. `claude-lint rules` lists each rule with its `why` and is the only place a numeric limit is written down.
- The reference tables live in the tools: `claude-lint fields skill|agent|rule` for frontmatter (`fields <kind> <field>` for one field), `hooktool events` and `hooktool fields` for hooks. `claude-lint check-injection '<command>'` says whether a skill-body injection will load, and which `allowed-tools` entry it needs.
- New lint rules: unknown and mis-valued frontmatter fields in skills and agents, two agents with one name, imports in rule files, and info-level SK016 and AG007 for a file-keyed description.
- Skill and agent descriptions carry intent only - what a user asks for. File-keyed delivery is the hook's job.
- The skills are cut to judgement: review checklists and field-by-field tables are gone, `composition.md` and the API reference are decision tables with links, and each cross-cutting fact has one home that the other files point at.
- The auditor's Bash boundary is enforced: a `PreToolUse` hook blocks any command from that agent other than the linter.
- The consistency tests fail when a prose file states a limit the linter owns, when a second file restates a fact that has an owner, or when a pointer names a section that no longer exists.

## 0.3.0 - 2026-10-09

- **Breaking: executables moved from `bin/` to `scripts/`.** A plugin with a `bin/` directory is not installed by claude.ai or Cowork, so nothing is on PATH any more. The linter is `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint"` (from a shell at the plugin root, `python3 scripts/claude-lint`); `hooktool` is `python3 skills/authoring-hooks/scripts/hooktool.py`. Update any script or permission rule that used the bare names.
- **Breaking: `install-rules` copies by default.** It writes a hash manifest beside the copies, refreshes unedited copies and leaves edited ones alone. There is no symlink mode: linked rules were observed not to load. `--check` reports drift for CI.
- Every skill re-verified against the live docs, the Claude Code 2.1.295 binary and headless probes, and corrected. Among the corrections: AGENTS.md is read directly; path-scoped rules load on Read, Write or Edit; subagents can spawn subagents; a `Bash(...)` specifier in an agent's `tools:` does not restrict Bash; plugin-shipped agents ignore four frontmatter fields; a skill's `name` is its command name; `PermissionRequest` does not honour exit 2.
- `hooktool` knows every hook event, checks handler types per event, validates `if`, `once` and `onFailure`, and has a `--plugin` mode.
- The linter models the pre-load permission check on injections and checks that a version stamp agrees with its fallback text; it lints `AGENTS.md` as memory and warns on a plugin that ships a top-level `bin/`. `python3 scripts/claude-lint rules` lists the rules.
- Every skill that states the version it was written for now carries a code-checked version stamp, and the import syntax moved to `authoring-memory/references/imports.md`.
- The auditor agent finds its standard through the preloaded skill's base directory and runs the linter by explicit path.

## 0.2.0 - 2026-10-09

- **Breaking: renamed from `claude-authoring` to `authoring-kit`.** `claude plugin validate` treats names starting `claude-` as reserved. Components are now `authoring-kit:<name>`. Remove the old plugin, or both load and both `SessionStart` hooks fire; see "Upgrading from claude-authoring" in the [README](README.md).
- The linter, `claude-lint`, exists: lint, `--all`, `rules`, `classify`, `hook`, `stamp` and `install-rules`. `claude-lint rules` is the single source of the rule set and the numeric limits.
- The write-time hook reports findings to the model through `hookSpecificOutput.additionalContext`; before this its output never reached the model.
- Skill bodies no longer corrupt themselves at load: the literal body grammar moved to `authoring-skills/references/body-grammar.md`.
- Stamped skills decide staleness in code (`claude-lint stamp`) and carry a narrow `allowed-tools` entry so the injection passes the pre-load permission check.
- A test suite, including a drift guard between the prose and the linter.

## 0.1.0

- First version: the selector and gate (`authoring-foundations`), one skill per primitive, `api-features`, the `authoring-auditor` agent, the `SessionStart` litmus hook, `hooktool`, and the path-scoped rules. The linter was specified but not built.
