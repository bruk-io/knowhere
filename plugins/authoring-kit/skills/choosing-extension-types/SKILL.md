---
name: choosing-extension-types
description: 'Decides which mechanism a Claude Code behaviour should be: CLAUDE.md, rule, inline or forked skill, subagent, hook, or plain code. Claude picks the wrong one from memory (a skill for a convention that must always hold, a subagent for isolation a forked skill gives, a description keyed on file touches), so load this before adding or moving any convention, constraint, workflow, worker, reviewer or automation, even when the user names no extension type.'
argument-hint: "[what you want Claude to do or know]"
---

# CLAUDE.md vs rule vs skill vs agent vs hook

> **First, the upstream gate.** Every artifact puts context in front of the model,
> so ask the prior question: should the model do this at all, or is it deterministic
> work that should run as code (a tool the model calls) or as enforcement (a hook
> that always fires)? Route below only for what needs the model to interpret, judge,
> synthesise, or generate. The gate, the two axes and the within-body *seam* are in
> [references/minimizing-model-work.md](references/minimizing-model-work.md).

Both references are read on demand, not injected with this skill. Absolute paths
(expanded when this skill loads, so a subagent that preloads it can Read them
directly): `${CLAUDE_SKILL_DIR}/references/minimizing-model-work.md` and
`${CLAUDE_SKILL_DIR}/references/composition.md`.

Do not route on capabilities. Skills carry `allowed-tools`,
`disallowed-tools`, `model`, `effort`, hooks, and `context: fork`; agents
can preload skills; rules can be path-scoped; hooks can run commands.
Capability comparison produces no answer. Route on what the artifact
fundamentally is, and on its loading semantics.

CLAUDE.md is the fifth extension type, with the shortest branch: `/init` creates it and
Skill(authoring-kit:authoring-memory) maintains it - including a repository that
already has an `AGENTS.md` (that skill's "AGENTS.md interop").

## The model

- **CLAUDE.md is always-on memory.** Project-wide facts and standing
  instructions every session needs: build and test commands, layout,
  global conventions.
- **A rule is a constraint.** Declarative facts that must hold:
  conventions, prohibitions, invariants. `.claude/rules/*.md`, plain
  markdown, optionally path-scoped with `paths` frontmatter.
- **A skill is a procedure.** "How we do X" - structured (SKILL.md spec),
  with supporting files, tools, invocation control, and a choice of
  execution context.
- **An agent (authored artifact) is an execution boundary with identity.**
  A definition file with a system prompt, standing tool policy, model, and
  preloaded skills. Distinct from the runtime fork mechanism, which any
  skill gets with `context: fork` - isolation is never a reason to author
  an agent.
- **A hook is event-driven enforcement or injection.** JSON configuration
  that runs a handler on lifecycle or tool events regardless of whether the
  model remembered to do it.

## Loading semantics - the axis that decides rule vs skill

| | Loading | Cost | Failure mode |
| --- | --- | --- | --- |
| CLAUDE.md (root) | always, at launch | every session | none - but global tax |
| Rule (no paths) | always, at launch | every session | none - but global tax |
| Rule (paths) | unconditional once Claude uses Read, Write, or Edit on a matching file (a Write that creates the file gets it one step late, with the tool result) | every session that touches the domain | none - but domain tax |
| Skill | judged: description match (plus `paths` gate if set) | description always, body on trigger | may fail to trigger |
| Hook | unconditional on event match | every matching event | handler may fail, but execution is not optional |

**Guaranteed-and-taxed vs cheap-and-probabilistic. Choose by which failure
you cannot afford.** If Claude touching certain files without this content
in context is a correctness problem, it is a rule. If the content is only
needed when actually performing the task, it is a skill.

**A description matches intent; file-keyed delivery needs a guarantee.** A
description is the only thing that can catch "create a skill" before any file
exists, so it names the activity and when to load relative to it. "Whenever editing any
SKILL.md" in a description is a path match left to judgement, when the model
reading or writing a kind of file is exactly what a path-scoped rule or a hook
matches unconditionally. The test is who the subject is: "when the user mentions
a .pdf" is still intent.

What such a rule holds, what it cannot guarantee, and what a plugin does in
place of shipping one: "The pointer pattern" in Skill(authoring-kit:authoring-rules).
A skill's own `paths` field is a filter on when the skill is offered, not a
substitute for a rule.

## The decision

1. **Must it happen on an event with zero judgement?** → Hook. Use it for
   blocking a tool call, formatting after edits, injecting startup context,
   or keeping work going until a check passes.
2. **Is it a project-wide fact or standing instruction every session
   needs?** → CLAUDE.md. A global constraint that deserves its own topic
   file is an unscoped rule instead - same loading, split out.
3. **Is it a constraint that must always hold (globally or in a file
   domain)?** → Rule. Path-scope it whenever it is domain-specific; keep it
   short and declarative (long rules pay unconditional context tax and
   reduce adherence).
4. **Is it a procedure - steps, tool calls, judgement about how?** → Skill.
   Then choose where it runs:
   - Inline (default): the work must see the conversation - conventions
     applied while writing, reference knowledge.
   - `context: fork`: self-contained work that need not see the
     conversation, with noisy intermediates the main loop does not need.
5. **Is it judgement dispatch - a worker handed open-ended tasks?** → Agent.

Next step for the branch you land on: hook → Skill(authoring-kit:authoring-hooks);
CLAUDE.md → Skill(authoring-kit:authoring-memory); rule →
Skill(authoring-kit:authoring-rules); skill → Skill(authoring-kit:authoring-skills);
agent → Skill(authoring-kit:authoring-agents).

When two of these are genuinely defensible for the same artifact, don't guess -
use **AskUserQuestion** to put the contending extension types to the user (one
question, 2-3 options), then route on their answer. Subagents never have that
tool: inside one, report both options and the deciding question instead.

Access to an external system is a tool boundary, not an extension type of its own.
Prefer a local CLI first: no context cost until called, composable, structured
and bounded output. MCP tool search (the default) now defers schemas, loading
only tool names and server instructions at launch, but MCP still means a server
to run - reach for it only for a stateful/authenticated connection, event push,
or a non-shell surface. Skills and agents decide when to use the tool; they do
not compete with it.

## The four functional differences that justify an authored agent

If none apply, it is a skill (or a rule):

1. **Open task parameter.** Agents accept arbitrary work matching their
   description; a forked skill executes only its own body.
2. **Boundary-scoped policy.** An agent's tool policy binds to everything
   it is asked to do, including skills firing inside it. A skill's policy
   binds per-activation. "Reviewer cannot edit" is a worker property, not
   a work property.
3. **Deterministic startup context.** Preloaded skills inject in full at
   startup; the agent's prompt sits in the system position.
4. **Parallel dispatch.** Spawning N workers over a task list is the agent
   extension type.

## Anti-patterns

- **A rule containing numbered steps**: a procedure paying unconditional
  context tax - extract to a skill (same heuristic as oversized
  CLAUDE.md sections).
- **A convention encoded as a skill**: may fail to trigger exactly when it
  matters - if it must always hold in a domain, make it a path-scoped rule.
- **The same convention in both a rule and a skill**: one source; the rule
  states the constraint, the skill (if any) holds the procedure for
  satisfying it.
- An agent whose system prompt is mostly a procedure: extract to a skill,
  preload it; delete the agent if nothing remains.
- An agent created only for one workflow's isolation or tool limits: a
  skill with `context: fork` and frontmatter tools does that.
- Reference knowledge behind `context: fork` (why it fails:
  Skill(authoring-kit:authoring-skills), `context: fork`).
- **File-keyed triggers in a description** ("use whenever editing any
  SKILL.md"): a path match left to the model's judgement - move it to a
  path-scoped rule or a hook, and keep the description to what users ask for.
- **A rule bullet or checklist item a program could check**: a lint rule in a
  prose costume - "Before writing a prose rule - ask if it's a linter" in
  `references/minimizing-model-work.md`.

## Worked examples

- "All endpoints under src/api/** must validate input" → rule with
  `paths: src/api/**`.
- "Never edit files under generated/" → rule (or a hook if it must be
  mechanically blocked).
- "Run prettier after every edit" → `PostToolUse` hook; "block Bash
  commands matching a dangerous pattern" → `PreToolUse` hook.
- Apply team API conventions while writing endpoints → inline skill (the
  judgement of application), referencing the rule (the constraint itself).
- "API handlers validate input with zod", one behaviour split three ways: a
  lint rule (ast-grep + `PostToolUse` hook) asserts what is checkable - every
  handler parses its input through a schema; a rule with `paths: src/api/**`
  carries the judgement left over (what counts as a boundary, when a shared
  schema beats a local one) and names the skill; the skill's description lists
  only what users ask for ("add an endpoint", "validate this payload").
- Dig through CI logs, report the failing test → skill, `context: fork`.
- Production deploy, never auto-triggered, restricted commands → skill,
  fork, `disable-model-invocation: true`, scoped `allowed-tools`.
- Parallel implementation workers holding team conventions → agents
  preloading the conventions skill (differences 1, 3, 4).
- Reviewer that must not edit or review its own work → agent
  (difference 2).

## Beyond the five extension types - composing them

Running several agents at once, keeping a session working on its own, or
letting external events drive it is composition, not selection - see
[references/composition.md](references/composition.md) for the higher-order
features (parallel subagents, dynamic workflows, agent teams; `/goal`, `/loop`;
channels) and which extension types each is built from.
