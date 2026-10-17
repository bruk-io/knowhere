# Minimizing model work

_One principle at two scopes, loaded on demand. The **gate** asks whether the model should
touch a behaviour at all (the selector's opening blockquote summarises this). The **seam**
asks, once the model owns a slice, which lines of its body are secretly code. Same two-axis
logic - guaranteed-vs-contingent execution × fixed-vs-sampled result - applied first to the
whole behaviour, then within it._

Every Claude Code artifact - CLAUDE.md, rules, skills, subagents, hooks - is a mechanism for
putting **context in front of the model**, and every line of model-facing prose is work the
model redoes on each run. The discipline is the same at both scopes: push toward
deterministic execution and deterministic results, and let the model own only what genuinely
needs interpretation, judgement, synthesis, or generation.

## The gate - should the model do this at all?

The decision that comes *before* picking an artifact. The moment you reach for one, you've
silently answered "yes, the model should do this." Often that answer is wrong, and a 20-line
tool would be more reliable, testable, and free at runtime. So gate first, then hand back to
the selector ([SKILL.md](../SKILL.md), which cites this) to pick the artifact for
whatever slice the model genuinely owns.

### Ask in this order

1. **Can a local tool or existing command produce the result deterministically?** → write code. The model never enters the picture.
2. **Does something just need to *always happen* around the model?** → a hook, permission rule, or CI gate. The model stays in the loop; the must-happen step is executed by code.
3. **Does the model need to decide *when* to run otherwise-deterministic work?** → a skill or subagent that calls a bundled tool. Determinism lives in the code; the model only picks the moment.
4. **Does the task genuinely need language understanding, judgement, synthesis, or generation?** → now the model interprets context - and the selector takes over to pick the artifact.

Stop at the first "yes." Each later answer hands more to the model, so take the earliest one the task allows; only move on when the answer above genuinely can't do the job.

### Two axes, not a ladder

The question was never code-vs-artifact - good artifacts usually *contain* code. It's two independent properties of whatever you're about to build, and confusing them for a single ladder is how deterministic work ends up parked in a probabilistic mechanism:

- **Execution** - does it run because the harness fires it (*guaranteed*), or because the model chose to engage (*contingent*)?
- **Result** - once it runs, is the outcome *fixed* (a script: same input, same output) or *sampled* (the model: plausible, not identical)?

They're independent, so there are four cases:

| | fixed result | sampled result |
|---|---|---|
| **guaranteed to run** | code the harness runs - a hook, a CI gate, a script. Deterministic, testable, free at runtime. | a hook with a `prompt`/`agent` handler - always fires, judges with variance. |
| **runs only if the model chooses** | the model invoking a bundled tool - deterministic *where the code runs*, contingent on it being called. Tool source never enters context. | the model interpreting prose - CLAUDE.md, a rule, skill prose, an agent prompt. Best-effort on both axes; pays context every session. |

Each step away from the top-left trades a guarantee for flexibility and pays in tokens and variance. The job is to *minimize the distance*: pin execution to guaranteed and results to fixed wherever the task allows, and let the model own only the axis the work genuinely forces.

The bottom-right cell - the model interpreting prose - is the only one whose reliability rests on the model choosing to comply. When it's unavoidable - the model must answer, extract, or generate - you still aren't stuck with best-effort prose: the Anthropic API can enforce a property on the output (grounded citations, a schema-constrained shape), which fixes part of the result axis even when the model is doing the work. Invoke Skill(authoring-kit:wrapping-api-calls) for those patterns and the tool bridge.

### Does the model actually need to touch this?

It earns a place only if the task needs at least one of: open-ended language understanding, judgement under ambiguity, synthesis across sources, adaptation to novel input, or generative output. If you can phrase it as *"given X, deterministically produce Y,"* it's code. The reliable tell you've over-reached is a prompt that says *"use good judgement"* or *"handle edge cases appropriately"* - either the model is genuinely needed, or you haven't finished specifying the problem, and the unspecified part is exactly the code you still owe.

### Why code wins by default

Deterministic (same input, same output - no drift over a long session), testable (you can unit-test a tool, not a prompt), reviewable/versioned (it diffs, gets a PR, has blame), debuggable (a stack trace, not "the model didn't follow the instruction"), and free at runtime (zero tokens; interpreted prose costs tokens every session whether relevant or not). This is the through-line for both scopes.

### When context legitimately wins

Not dogma - reach for the model when the input is open-ended or unstructured, the task needs judgement a spec can't encode, the work must adapt per situation, the output is generative, or encoding the rule as code costs more than tolerating the occasional miss (don't build a parser for a one-off). That last is the pragmatic escape hatch, not a licence to skip the deterministic options for things that recur.

### Before writing a prose rule - ask if it's a linter

**Prose rules are probabilistic; linters are deterministic.** Before encoding a constraint as a `.claude/rules/*.md` entry, ask: *can this be expressed as an AST or pattern match?* If yes, it's a guaranteed check - implement it as a linter rule wired to a `PostToolUse` hook, and skip the prose entirely (or reduce it to a one-line pointer).

**[ast-grep](https://ast-grep.github.io)** is particularly useful here. It understands real language ASTs (TypeScript, Python, CSS, etc.), runs from a `sgconfig.yml` in the project or plugin, and can be wired to a hook in seconds. (Its short alias is `sg`, but on Linux `sg` is already a system command - use the full name there.)

```bash
# Check for hardcoded hex colors in Lit static styles after every Write/Edit
ast-grep scan --config marketplace/plugins/lit-docs/sgconfig.yml packages/docs-ui/src/
```

With a `languageInjections` entry in `sgconfig.yml`, it even parses tagged template literals (e.g., css`...` inside TypeScript) as their embedded language, enabling CSS-AST rules on `static styles` content.

**Decision flow for any constraint you're about to write as prose:**

1. Can you express it as a grep or regex? → write a CI check or hook script (guaranteed to run, fixed result).
2. Can you express it as an AST pattern (kind, has, not, inside)? → write an ast-grep rule + `PostToolUse` hook (same).
3. Does the constraint require judgement about intent or context? → now it's a prose rule (the model interprets it). Keep it short; it pays context tax every session.

A prose rule for something a linter could check is interpreted prose doing a guaranteed check's job - it will drift, be forgotten, and fail silently.

**The same question applies to each bullet inside an existing rule file, and to every review checklist item.** A bullet a program could check is a lint rule, and its reason travels with the check - in the linter's message, shown at the moment it fails - not with a prose copy that drifts from it. The rule file keeps the judgement and one line pointing at the linter.

## The seam - within a model-facing body, code vs prose

The gate has said the model owns this slice; now the same discipline applies line by line.
Prose in a skill or agent is interpreted probabilistically on every run: the model re-reads
it, re-decides what it means, and executes it with variance, paying tokens and reasoning each
time. Every line of prose that could have been code pays interpretation tax for no benefit,
and converts a pass^k = 1.0 operation into a probabilistic one. The question is which of
*these lines* is secretly code.

### The litmus test

**If you could write an assertion for it, write code. If you would need a rubric, write prose.**

This is the same boundary as deterministic checks vs human judgement calls.

| Code (tools/) | Prose (SKILL.md body) |
| --- | --- |
| Parsing, extraction, regex | When to run a tool, with what parameters |
| Validation, format checks | How to interpret tool output |
| Multi-step shell sequences | Judgement calls, tradeoffs |
| Arithmetic, counting, sorting | Adapting to what is actually in front of you |
| File transforms, templating | Taste, tone, style decisions |
| API calls with known shapes | Escalation criteria |
| Environment setup, bootstrap | What "done" means when it is contextual |

### The structure this produces

The skill body becomes a thin judgement shell routing into deterministic machinery:

```text
my-skill/
├── SKILL.md          # when to run what, parameters, interpreting results
└── tools/
    ├── check.sh      # deterministic core, structured output
    └── transform.py
```

Rules for the seam between shell and core:

- **Tools take clean parameters.** Judgement lives in choosing them; the tool does not guess.
- **Tools emit structured, parseable output** (JSON or stable line format) and meaningful exit codes. The model should interpret results, never re-parse messy text the tool could have structured.
- **Tools fail loudly and specifically.** A precise error is judgement fuel; a silent fallback hides the decision the model needed to make.
- **Tools get unit tests.** The deterministic core is graded by tests; only the judgement shell needs trial-based evaluation.

That covers the *seam*. For the tool's external shape - CLI conventions, JSON output contracts, self-documenting `--help`, MCP-vs-CLI - see *Designing tools the model calls* below.

### The rewrite move

When authoring or reviewing, scan for procedure narration - prose that walks through steps with a right answer:

> "Run the build, then look for lines containing ERROR, extract the module name, and check whether it appears in the manifest."

That is a tool pretending to be instructions. Every run re-derives the parsing logic, sometimes differently. Replace with one tool call plus one line of prose about when to call it and what the result means.

Other signals a rewrite is due:

- Numbered step lists where no step requires judgement
- Regex or matching rules described in English
- Arithmetic or threshold rules in prose ("if more than half...")
- Output format specifications longer than a template file would be
- The same procedure narrated in more than one skill or agent prompt
- A skill that behaves differently between runs on identical inputs

### The harvest corollary

When an agent or forked skill discovers a working procedure (a bootstrap sequence, a parsing approach, a fix-verification flow), harvest it as a committed tool, not as prose describing what worked. Prose harvests decay back into interpretation tax; tool harvests make the next run deterministic.

### The caveat

Code is brittle where inputs vary wildly. The move is not "code everything" - it is **code the invariant core, prose the adaptive shell**, with clean parameters as the seam.

Branch count is not the tripwire - branchy code with mechanically decidable conditions (file type, exit code, schema, platform) is just code, however large. The tripwire is **decidability of the branch condition**: can a program decide which branch applies, or does deciding require understanding intent and context? When a tool feels overgrown:

1. Conditions mechanically decidable → keep it all in code; manage the complexity normally.
2. Selection is judgement but branch bodies are deterministic → lift the decision into prose, keep the work as code: branches become parameters (`--mode=...`) or separate tools the shell chooses between.
3. Branch bodies are themselves judgement → that part was never tool material; prose it and narrow the tool to the invariant remainder.

Reverting deterministic work to prose because the code got complicated reintroduces interpretation tax on work that still has right answers - the worst of both worlds.

## Shared: building the code path

### Anti-patterns - context where code belongs

All share the shape of parking a deterministic need in a probabilistic mechanism:

| Symptom | What's really happening | Move it to |
|---|---|---|
| "Always run prettier after edits" in CLAUDE.md | Enforcement parked in skippable guidance | A `PostToolUse` hook (guaranteed to run) |
| A skill that's a runbook of shell commands | Code in a prose costume | A tool the skill calls (deterministic where it runs) |
| Asking the model to parse a file or do arithmetic in-context | Determinism handed to a probabilistic engine | A tool (deterministic, model-free) |
| A subagent that "verifies" something checkable | Judgement where a check exists | A test or CI gate (guaranteed) |
| "Use good judgement / handle edge cases" in a prompt | An unfinished spec - or genuine model work | Finish the spec (→ code), or own that it's best-effort |
| A prose rule like "don't use hardcoded hex colors" | A checkable pattern encoded as guidance | An ast-grep rule + `PostToolUse` hook (guaranteed) |
| A skill description that says "use whenever editing any SKILL.md" | A path match left to the model's judgement | A path-scoped rule or a hook (guaranteed to run); the description keeps what users ask for |
| A rule bullet or checklist item restating a limit or format a linter asserts | One check kept twice, the prose copy drifting | The lint rule alone, reason in its message; the prose keeps a pointer |

### Designing tools the model calls

A tool the model calls is an interface between deterministic code and a probabilistic caller. The model is a competent Unix user with strong priors about CLI behaviour, but no memory of *your* tool, and every token it emits competes for context. Design for a smart stranger who knows the conventions but not your code.

**Prefer a local CLI over an MCP server.** A CLI costs nothing until called, then contributes only its output; it pipes, filters and composes in one Bash call; it is testable outside a session; and there is no server to run or connect. The old context argument is weaker than it was: MCP tool search is on by default, so only tool names and server instructions load at session start and schemas are fetched when Claude searches for them. Definitions still load upfront where tool search is off (a non-first-party `ANTHROPIC_BASE_URL`, `ENABLE_TOOL_SEARCH=false`, some third-party-cloud deployments) or a server sets `alwaysLoad`. Reach for MCP only for a stateful/authenticated external connection, event push, or a non-Bash surface.

- **Output structured data (JSON)** with a stable schema on stdout; logs and diagnostics to stderr; gate the structured form behind `--json` where a human also reads it.
- **Bound the output; make detail opt-in** - default to a summary/top-N, offer `--full` / `--page` / `get <id>` for more. Verbose-by-default tools quietly burn context.
- **Self-document** with a complete `--help`; the model reflexively tries it, so usage needn't live in context. Pair with actionable stderr and meaningful exit codes so it can self-correct.
- **Follow Unix conventions** - stdin→stdout, diagnostics→stderr, `0`/non-zero exit, standard flags, one job done well, no ANSI when piped. A conventional tool needs almost no explanation.
- **Consider a `<tool> claudemd` subcommand** that emits the tool's own concise, model-optimised docs for injection via `` !`tool claudemd` `` in the skill that drives it, with a fallback and an `allowed-tools` entry so the load cannot abort (or a `SessionStart` hook; CLAUDE.md and rules do not run commands). The tool becomes the single source of truth for how to drive it - docs regenerate each time they load and never drift.

### The handoff

Once the task genuinely needs the model to interpret, judge, synthesise, or generate - and you've pushed everything deterministic into code around it - *then* the selector picks the mechanism for the slice the model owns, and the seam above keeps that slice's body as thin as the work allows. Skipping the gate is how you end up with an elaborate skill for something a tool would have done correctly, every time, for free.
