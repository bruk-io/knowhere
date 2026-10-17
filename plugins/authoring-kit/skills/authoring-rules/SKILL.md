---
name: authoring-rules
description: 'Use when the user wants a convention or constraint Claude always follows, in a directory or everywhere, or a rule is not loading, loads too often or is ignored, or a CLAUDE.md is big enough to split into rules. Rule loading has traps Claude gets wrong from memory (when a scoped rule actually arrives, which file accesses trigger it, and that it is gone after compaction until the next touch), so load this before writing, reviewing, debugging or advising on any rule or always-on convention, even a one-line one.'
---

# Rules authoring reference

Rules are decomposed CLAUDE.md: declarative constraints in
`.claude/rules/**/*.md`, loaded as project memory. They are deliberately
simple - one frontmatter field, plain markdown bodies, no invocation
machinery. Rules are constraints, not procedures.
Before authoring, invoke Skill(authoring-kit:choosing-extension-types): it gates (should the model do this at all?) and routes (is this really a rule?).

## Frontmatter

One field, **`paths`**: glob patterns scoping the rule to matching files.
Without it, the rule loads at launch in every session. With it, the rule
loads unconditionally when a matching file is touched (which touches count:
Loading and scope, below). Its type, and the notes on glob syntax and on keys
other tools put beside it, are a table, not this page: run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" fields rule`.

```yaml
---
paths:
  - "src/api/**/*.ts"
  - "lib/**/*.{ts,tsx}"
---
# API rules
- All endpoints validate input with zod schemas
- Errors return the shared ErrorEnvelope shape
```

The example quotes every glob because the linter's `paths` check (RU006)
fails an unquoted one that would break the frontmatter. The linter reports
after every write, each finding with its reason.

Decision guidance for `paths`:

- Omit it only for genuinely global constraints. Everything
  domain-specific gets path-scoped; unscoped rules tax every session.
- Scope to where the constraint applies, not where work usually happens -
  the rule loads on file touch, not working directory.

## Body conventions

- **A bullet a program could check is a lint rule, not a bullet** - see
  "Before writing a prose rule - ask if it's a linter" in
  [`choosing-extension-types/references/minimizing-model-work.md`](../choosing-extension-types/references/minimizing-model-work.md).
- **One topic per file**, named for it: `api-validation.md`,
  `generated-files.md`. Update one constraint without touching others.
- If a constraint must be mechanically enforced rather than followed, it
  is a hook, not a rule. Rules guide; hooks block.

The shape of the body - declarative, short, its opening line, no skill-body
grammar - is the linter's to assert.

At-sign imports do expand in a rule file, but prefer self-contained rules: an
import pulls in the whole target on every load. Syntax and cost: Skill(authoring-kit:authoring-memory).

## The pointer pattern

A path-scoped rule is the guaranteed carrier for "when you touch these files,
these judgement constraints hold, and this skill has the procedure". It
guarantees loading, not compliance - only a blocking hook is a hard guarantee.
It cannot load a skill, only name it.

A plugin cannot ship rules as a component: it delivers them by hook on first
touch (this plugin does - authoring-hooks, "Delivering a rule on file touch
from a plugin") or with an installer.

## Loading and scope

- **Locations**: project `.claude/rules/` (version-controlled, the
  default), user `~/.claude/rules/` (all your projects). Subdirectories
  work (`rules/frontend/react.md`); circular symlinks are handled.
- **Symlinks**: a link whose target is inside the working directory just
  resolves. One pointing **outside** is treated like an external import -
  it stays unloaded until external imports are approved for the project,
  and even then only if it has no `paths`. Share rules across projects
  through `~/.claude/rules/` instead.
- **Order, not override**: unscoped rules load with the same priority as
  `.claude/CLAUDE.md`, user rules before project rules. Nothing wins a
  conflict - Claude may follow either - so keep the sets consistent.
- **Loading is guaranteed**: at launch (unscoped) or on path match
  (scoped). No judgement, no triggering, no failure-to-load - this is the
  property that distinguishes rules from skills. Choose rules when absence
  during matching work would be a correctness problem.
- **A scoped rule arrives with the tool result** that matched it (observed
  on 2.1.295), including the Write that creates a new matching file - so it
  informs the next step, not the call that triggered it. The documented
  triggers for a scoped rule are Read, Write, and Edit; observed, a Bash
  `cat` of a matching file also triggers, while Grep, Glob, `ls`, and a
  shell redirect that writes the file do not. After compaction a scoped
  rule is gone until the next matching touch; unscoped rules are
  re-injected.
- `--add-dir` directories: rules load only with
  `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`. Project rules are
  skipped when `--setting-sources` excludes `project`.

## Debugging what loaded

`/context` and the `InstructionsLoaded` hook answer for rules as they do for
CLAUDE.md - "Debugging what loaded" in Skill(authoring-kit:authoring-memory).
What is particular to rules:

- A scoped rule listed under **Memory files** before any file was touched
  has broken frontmatter.
- `InstructionsLoaded` reports a scoped rule with `load_reason`
  `path_glob_match` and the file that matched.
- A rule "not working" is usually one of: the glob does not match the
  touched file, the file was reached only by a tool that does not trigger
  loading (Loading and scope, above), the file is past the length the
  linter reports, or the content is
  procedural and belonged in a skill.
