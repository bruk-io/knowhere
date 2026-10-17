---
name: authoring-memory
description: 'Use when improving or debugging project memory (CLAUDE.md, CLAUDE.local.md, AGENTS.md): it is too long, ignored or not loading, or a line may belong in a rule or skill instead. Memory loading has traps Claude gets wrong from memory (a CLAUDE.local.md can silently stop AGENTS.md loading, @imports do not save context, which files are never read), so load this before writing, reviewing, debugging, planning or advising on changes to project memory, even a one-line change. To create one from scratch, run `/init`.'
---

# CLAUDE.md authoring reference

CLAUDE.md is always-loaded project memory: instructions you write, delivered to
every session as context - not enforced configuration (for something that must
happen regardless of what Claude decides, use a hook). A repo's `AGENTS.md` can
fill the same role (AGENTS.md interop, below).
Before authoring, invoke Skill(authoring-kit:choosing-extension-types) - a fact that must hold in **every** session goes in CLAUDE.md; one that applies only in a file domain is a path-scoped **rule**; a procedure with steps is a **skill**.

## `/init` creates; this skill maintains

Don't hand-author a CLAUDE.md from scratch - run `/init` (or set `CLAUDE_CODE_NEW_INIT=1`
for the interactive flow that also offers skills, hooks, and a personal
`CLAUDE.local.md`). It scaffolds from the actual repo and folds in Cursor rules and
Copilot instructions; the interactive flow also reads `AGENTS.md`, `.windsurfrules`,
`.clinerules`, and `.devin/rules/`. Run against an existing file it suggests
improvements rather than overwriting. Treat the output as a first draft. A repo that
already runs on `AGENTS.md` may not need a CLAUDE.md at all - check the interop
section before creating one.

This skill is for everything after - the judgement `/init` can't settle once:

- prune toward the size target (Body conventions, below) as the file accretes;
- catch a section that has drifted into a procedure (→ extract to a skill) or into
  a single file domain (→ a path-scoped rule);
- sharpen vague lines into specific, verifiable ones.

## Where it lives (what matters for maintenance)

`CLAUDE.md` (or `.claude/CLAUDE.md`) and `CLAUDE.local.md` in the working directory
and every directory above it load in full at launch; subdirectory files load on
demand when Claude uses Read, Write, or Edit on a file under them - so anything that
must **always** apply belongs at or above the launch directory, not in a subtree.
Managed-policy, then user (`~/.claude/CLAUDE.md`), then project files are
**concatenated**, broadest first, filesystem root down to the working directory, with
each directory's `CLAUDE.local.md` after its `CLAUDE.md`. Nothing overrides: later
text is merely read last, and on a contradiction Claude may pick either - so the fix
for a line that isn't taking effect is to remove the conflict, not to rely on
position. In a monorepo, drop irrelevant ancestor files (or rules) with
`claudeMdExcludes` (absolute-path globs, any settings layer; managed files cannot be
excluded). Full path list: the memory docs.

## Body conventions

- **Size: the linter states the target and why** (CM001 in
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" rules`).
  Claude Code itself warns at startup and in `/status` when an instruction file (or
  the combined set) is over its recommended size. When it grows, decompose - domain
  constraints become path-scoped rules, procedures become skills (the same
  heuristic as the anti-patterns in Skill(authoring-kit:choosing-extension-types): "a rule containing numbered
  steps"). Cut what Claude can derive from the codebase (directory layouts,
  dependency lists); keep pitfalls, rationale, and conventions that differ from tool
  defaults - plain `/doctor` proposes exactly these trims.
- **Declarative facts and standing instructions**, not procedures with a right
  answer (those are skills - see "The seam" in [`choosing-extension-types/references/minimizing-model-work.md`](../choosing-extension-types/references/minimizing-model-work.md)). Build/test commands, conventions,
  project layout, "always do X" rules. A line a program could check is a hook's or
  a linter's job, not memory's.
- **Be specific and verifiable.** "Use 2-space indentation" beats "format code
  properly"; "Run `npm test` before committing" beats "test your changes". Vague
  instructions are followed inconsistently.
- **Structure with headers and bullets** - Claude scans structure the way readers
  do; grouped sections beat dense paragraphs.
- **Block-level HTML comments are stripped** before injection - use
  `<!-- maintainer note -->` on its own line for human-only notes without spending
  context. Comments inside code blocks, and comments inline within a line of text
  (observed on 2.1.295), are preserved.

## Imports

An import is an at-sign immediately followed by a file path, anywhere in the file;
the target is expanded inline at launch. Literal examples - escaping, and what
stays literal - live in `references/imports.md`, not here: a SKILL.md body attaches
any at-sign path that resolves from the working directory when the skill loads,
fenced or not (observed on 2.1.295). What breaks an import is the linter's (CM002).

- Relative paths resolve against the **importing file**, not the working directory;
  absolute and home-relative paths work too.
- Imports **load at launch and consume context** like inline content - splitting
  into imports aids organisation, it does not save tokens.
- An import in a **project-level** file whose target is outside the working
  directory is *external*: the first one prompts an approval dialog, and declining
  disables them silently thereafter. Imports in user-scope files
  (`~/.claude/CLAUDE.md`, `~/.claude/rules/`) load without the dialog.
- Imports also expand in `.claude/rules/` files and in a directly-read `AGENTS.md`.

## AGENTS.md interop

Since v2.1.277 Claude Code reads `AGENTS.md` (and `.claude/AGENTS.md`) directly -
but by default only as a **stand-in**: when no `CLAUDE.md`, `.claude/CLAUDE.md`, or
`CLAUDE.local.md` exists in the working directory or above it. With one present,
Claude reads the CLAUDE.md files only. `~/.claude/CLAUDE.md`, a managed CLAUDE.md,
and `.claude/rules/` don't count for that check and load alongside either way.

- **The `CLAUDE.local.md` trap**: adding a personal `CLAUDE.local.md` to a repo that
  relies on `AGENTS.md` silently stops `AGENTS.md` loading for you (observed on
  2.1.295: only the local file's content arrives). So does `/init` writing a
  CLAUDE.md that does not import it.
- **The setting**: `/config` → **Project instructions**, stored as `instructionFiles`
  under `pluginConfigs` for the built-in plugin (user, `--settings`, or managed
  settings only - ignored in project and local settings; JSON in
  `references/imports.md`). Values: `claude-md-or-agents-md` (default),
  `claude-md-and-agents-md` (both, each directory's CLAUDE.md first; an AGENTS.md
  already imported or symlinked is not read twice), `claude-md`, `managed-only`.
- **Subdirectories**: a nested `AGENTS.md` loads when Claude uses Read on a file
  there and that directory has no CLAUDE.md file of its own. `AGENTS.local.md`,
  `AGENTS.override.md`, and `.agents/` are never read.
- **Differences from CLAUDE.md** when read directly: `InstructionsLoaded` hooks
  don't fire for it, `--add-dir` directories don't contribute theirs, and external
  imports inside it never prompt (they load only if already approved).
- **Importing is still the right bridge** when the repo needs both files: a
  CLAUDE.md that opens by importing `AGENTS.md`, with Claude-specific notes below.
  A project setting can't turn on "both" for the team, and the import also covers
  sessions that can't read AGENTS.md directly (older versions, the built-in plugin
  disabled). A symlink works when there is no Claude-only content, but Edit and
  Write refuse to write through it and Windows clones may get a one-line text file.
  A CLAUDE.md that merely *tells* Claude to go read AGENTS.md is not a bridge.
- Other tools read `AGENTS.md` too: keep Claude-only syntax and instructions
  (imports, plan-mode or skill references) in CLAUDE.md, shared facts in AGENTS.md.

## CLAUDE.md vs auto memory

A distinct system worth knowing: **auto memory** is notes Claude writes itself
(your preferences, corrections, project context it can't derive from the code),
stored per-repo under `~/.claude/projects/<project>/memory/` as one topic file per
memory plus an index; the head of that `MEMORY.md` loads each session, topic files
on demand. You author CLAUDE.md; Claude maintains auto memory.
`/memory` toggles it and opens both. "Remember X" usually lands in auto memory; to
put something in CLAUDE.md, say "add this to CLAUDE.md" or edit it directly.

## Debugging what loaded

- **`/context`** lists what loaded at launch under **Memory files** - the first
  check when an instruction is ignored or over-applied. If a file isn't listed,
  Claude can't see it. Subdirectory files never appear there; a `Loaded` line with
  the path prints when one loads on demand. **`/memory`** lists the file locations
  (including a directly-read `AGENTS.md`), opens them for editing, and toggles auto
  memory.
- **AGENTS.md not loading?** Look for a CLAUDE.md or `CLAUDE.local.md` at or above
  the working directory, then the version, then the **Project instructions** value.
- **Not being followed?** CLAUDE.md is delivered as a user message **after** the
  system prompt - guidance, not strict compliance. Make it more specific, resolve
  contradictions across files, or, if it must run at a fixed point, move it to a
  hook. For genuine system-prompt-level text, `--append-system-prompt` (every
  invocation - better for scripts than interactive use).
- **`InstructionsLoaded`** hook logs exactly which instruction files loaded, when,
  and why (a `load_reason` per file; the values: `hooktool.py events`) - the
  mechanical answer for nested or lazy-loaded files (the prefer-code principle:
  log it, don't guess).
- **Compaction**: the project-root CLAUDE.md is re-read from disk and re-injected
  after `/compact`; a nested subdirectory file is **not**, until Claude next
  touches a file under it (rules: "Loading and scope" in
  Skill(authoring-kit:authoring-rules)). Anything that must survive a long session
  belongs in the root, not a subtree file.
- **`/doctor prompt-audit`** (v2.1.283+) has Claude review CLAUDE.md, AGENTS.md,
  rules, skills, commands, and subagents for stale or contradictory instructions
  and propose edits. It is model judgement like this plugin's auditor agent, with a
  broader default scope; `claude-lint` remains the mechanical, repeatable check.
