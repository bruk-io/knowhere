---
name: authoring-skills
description: 'Use when creating or changing a Claude Code skill or slash command, or one triggers wrongly, never triggers, runs in the wrong context or fails to load. Skills have traps Claude gets wrong from memory (descriptions that never fire, forked guideline content that returns nothing, `paths` treated as a guarantee, load-time shell output with no fallback, side-effect commands Claude can run on its own), so load this before writing, reviewing, debugging or advising on any skill or command, even a small one.'
---

# Skills authoring reference

Before authoring, invoke Skill(authoring-kit:choosing-extension-types): it decides whether this is a skill at all, and "The seam - within a model-facing body, code vs prose" in its [minimizing-model-work.md](../choosing-extension-types/references/minimizing-model-work.md) decides what in the body should be code.

Defaults are deliberately good - a skill with nothing but a description
works - and every added field is a deviation to justify.

The field reference is a table, not this page: run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" fields skill` for the type,
default and effect of every field, and read its notes before shipping to
claude.ai. The linter reports mistakes, each with its reason, after every
write. What follows is only the judgement: when to set a field, and its trap.

## Frontmatter

- **`name`** - Leave it out unless the command must differ from the
  directory name; once set, the skill answers to both.
- **`description`** - The triggering mechanism. Claude undertriggers: when
  it believes it knows the topic, it answers from memory and never loads
  the skill. State what the skill does, key use case first (listings
  truncate), then the two things that measurably move it:
  - **When to load, relative to the task**: "load this before writing,
    reviewing, debugging or advising on X, even a small one". Name advice
    and planning as well as edits, or questions answer from memory.
  - **What Claude gets wrong without it**: the specific traps or house
    rules, named. A description that names concrete rules ("uv only",
    "RFC 9457 problem+json") already reads as a reason to load.

  Name the activity, not the file ("before changing project memory", not
  "whenever CLAUDE.md is edited"): file-keyed delivery belongs in a rule or
  hook, "Loading semantics" in Skill(authoring-kit:choosing-extension-types).
  Third person or "Use when", lists of example phrases, and implementation
  detail made no measurable difference. Effort changes firing too, so test
  at the lowest effort users run. Evidence and method:
  `evals/experiments/2026-10-14-hooks-triggers/README.md`.
- **`disable-model-invocation: true`** - For deployments, destructive
  operations, anything that must never fire on Claude's judgement. The
  trap: it takes the skill out of more than the listing - read its effect
  in the table before setting it on a skill something else depends on.
- **`user-invocable: false`** - For background knowledge only Claude
  should pull in.
- **`argument-hint`** - Set whenever the skill takes arguments; costs
  nothing. With `arguments`, prefer named placeholders over numeric ones
  past one argument.
- **`context: fork`** - Fork self-contained work with noisy intermediates
  where the main loop needs only the result. Fork only bodies that are
  explicit tasks: forked guideline content gives the subagent no
  actionable prompt and returns nothing useful, so conventions run inline.
  Despite the name, the fork cannot see the conversation. When the task
  needs the history, split it: an inline step assembles a brief from the
  conversation, a forked step executes it. On the first run, confirm the
  transcript shows the skill running as a subagent; if it ran inline, the
  fork did not take effect.
- **`agent`** - Match the agent type to the job. A read-only type hosting
  write work fails silently.
- **`background`** - Set `false` when the next step needs the fork's
  result, or the fork needs a tool outside the background set.
- **`allowed-tools`** - Prompt-suppression for a known workflow, not a
  sandbox. Scope it to exactly what the procedure needs. A plugin that
  wants claude.ai or Cowork installs keeps its executables out of a
  top-level `bin/` (the linter says why).
- **`disallowed-tools`** - For an autonomous skill that must never do
  something, such as asking the user from a background loop. It is
  per-activation; standing policy belongs on an agent.
- **`model`, `effort`** - Route routine forked work to cheaper models; low
  effort for mechanical procedures, high for real reasoning.
- **`hooks`** - Enforcement that accompanies this procedure specifically;
  global behaviour belongs in settings hooks. They outlive the procedure -
  see "Hooks in skills and agents" in the
  [hooks reference](../authoring-hooks/references/hooks-reference.md).
- **`paths`** - A filter on when the skill is offered automatically (work
  on matching files), not a guarantee that the body loads. Useful for
  keeping a domain skill out of unrelated sessions in a monorepo. For
  constraints that must be present when those files are touched, write a
  rule - see "Loading and scope" in Skill(authoring-kit:authoring-rules).

## Body grammar

A skill body is a template: directives run and placeholders substitute at
load, code spans and fences included. So the exact syntax - injection,
arguments, built-in variables, escaping, at-sign file references - lives in
[references/body-grammar.md](references/body-grammar.md), never in a body,
where a literal would be consumed at load. Read that file before writing any
directive or placeholder; a skill that documents this grammar needs the same
split.

### Dynamic context injection

- **Prefer injection over instructing Claude to run the same command** -
  one deterministic preprocessing step replaces a probabilistic tool call.
- **Always give it a fallback and a narrow `allowed-tools` entry** - a
  failing or unapproved command aborts the whole load, without a prompt.
  The linter checks both after each write, and the same script's
  `check-injection '<command>'` answers for any command before you write
  it.
- **Anchor paths** on the skill-dir or project-dir variable: commands run
  in the session shell's current directory, which moves when Claude runs
  `cd`.
- **Bound the output** - choose what to keep: `head`, `--stat` or a
  summarising tool. The linter flags a command that looks unbounded.
- **Never inject a secret** - the linter catches only the literal-looking
  ones; what a command's output might contain is yours to judge.
- **Do not hang correctness on an injection** - policy or a claude.ai sync
  can switch it off, and the body then arrives without the data.

### Body lifecycle

The rendered body enters the conversation once; the file is not re-read on
later turns, and re-invoking with identical rendered content adds only an
"already loaded" note. So write standing instructions, not one-time steps.
Every body line is a recurring cost, and compaction is not kind to the tail
of a body (the linter's length rule says what survives): put the
instructions that matter first, keep the body lean, push detail to
supporting files and tools.

## Security review rules

Injection directives execute before the model sees the skill, so
model-level prompt-injection defences never engage. A cloned repo can
carry skills in `.claude/skills/` into a session with no install step,
and its `allowed-tools` grants apply without workspace trust. Therefore:

1. Review every inline and fenced injection directive, and the
   `allowed-tools` line that pre-approves it, in third-party or repo-borne
   skills before first use - together they are code execution at skill
   load, with your user's permissions.
2. Treat skill PRs like CI-config PRs: diffs adding or changing injection
   directives get workflow-change scrutiny.
3. Injected output is untrusted model input - a directive fetching remote
   content pastes attacker-controllable text into the prompt; constrain
   and sanitise.
4. Organisation-wide off switch: `disableSkillShellExecution` in managed
   settings.
