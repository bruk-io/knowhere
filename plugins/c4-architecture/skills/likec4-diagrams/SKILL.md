---
name: likec4-diagrams
description: Create C4 architecture diagrams using the LikeC4 DSL while enforcing Simon Brown's orthodox C4 methodology. Use whenever the user asks for an architecture diagram, C4 diagram, system context diagram, container diagram, component diagram, system landscape, dynamic/sequence view of a system, or mentions LikeC4 or .c4 files — whether from a codebase, a verbal description, or an existing design doc. Also use when reviewing or refactoring existing LikeC4 models for C4 correctness.
argument-hint: "[system-or-codebase-to-diagram]"
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "bash -c 'd=\"${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/likec4-diagrams}\"; exec python3 \"${d:-${CLAUDE_SKILL_DIR:-$HOME/.claude/skills/likec4-diagrams}}/tools/lint-hook.py\"'"
          timeout: 60
---

# C4 diagrams with LikeC4 (orthodox C4 enforced)

LikeC4 is deliberately permissive: arbitrary element kinds, unlimited nesting, freeform views. The C4 model is deliberately strict: four abstractions, one zoom level per diagram. This skill produces LikeC4 that a C4 purist would sign off on — LikeC4 syntax, C4 discipline.

Target to diagram (if given): $ARGUMENTS

## Workflow

1. **Inventory before syntax.** From the codebase or description, list:
   - People (human users/roles — not teams, not org units)
   - The software system(s) in scope (heuristic: one system = something a single team builds, owns, and can see inside)
   - External systems (black boxes you integrate with, incl. SaaS)
   - Containers per in-scope system: separately runnable/deployable units — apps, SPAs, mobile apps, databases, queues/topics, blob stores, serverless functions. NOT jars/DLLs/modules.
   - Components per container you'll zoom into: in-process groupings behind an interface. NOT separately deployable. For extraction from a real codebase, invoke the `c4-components` skill — it produces the evidence-backed inventory this step consumes.
   Ask the user for missing pieces only if the model would be guesswork without them.

2. **Scaffold the project:** `python3 <skill-dir>/tools/scaffold.py <target-dir> [--profile layered|hexagonal|cqrs] [--system <name>]...`. One `--system` (kebab, repeatable, idempotent) per software system creates its `models/`, `views/`, and `dynamic_views/` folders in sync; `--profile` adds pattern-role tag fragments (see c4-components heuristics). This produces the only layout (there is no flat mode) — its shape and the file-layout rules live in `references/methodology.md` § File layout. The invariants you must hold while writing: one element per file; a child is added with `extend <parent-FQN> { … }` (extend needs the FULL dotted FQN — no relative form); software systems are declared in their own `models/<system>/<system>.c4`, never in `landscape.c4`; explicit references only (no `it`/`this`). Do not invent element kinds beyond the spec's: `person`, `softwareSystem`, `externalSystem`, `container`, `webapp`, `mobileApp`, `database`, `queue`, `blobStore`, `component`. (The last seven are all Containers or Components semantically — the extra kinds exist only for shape/notation.)

3. **Write the model** into the scaffolded `models/` files, obeying the hard rules below. Syntax: `references/dsl-cheatsheet.md`. Cross-system edges (system→system, black-box) go in `models/landscape.c4`; intra-system edges in `models/<system>/_relationships.c4`.

4. **Write the views** into the scaffolded `views/` (and `dynamic_views/`) files — one zoom level per view (patterns in the cheatsheet). Folder = scope: `views/landscape.c4` = System Landscape (root, spans systems); `views/<system>/context.c4` + `containers.c4` = that system's Context and Container views; add a component view only for containers where it adds value; `dynamic_views/<system>/` for scenarios, deployment views if asked.

5. **Lint mechanically.** `npx likec4 validate .` must pass, then run the bundled linter — it enforces every assertable rule below (kinds, nesting, titles, technology, level-mixing):
   ```
   python3 <skill-dir>/tools/c4lint.py <project-dir>
   ```
   Fix every ERROR and re-run until clean. (A PostToolUse hook also auto-lints after every `.c4` write while this skill is active — treat its ERROR feedback as blocking. It skips silently while the project is mid-scaffold and doesn't parse yet.) Then self-review the judgment items the linter can't check (§ Review checklist in `references/methodology.md`): intent-revealing labels, arrow direction matches title, system-scoping heuristic, message-bus anti-pattern.

6. **Render.** If the user wants images: `npx likec4 export png -o ./diagrams` (or `npx likec4 start` for interactive preview).

## Hard rules (violations = bugs, even though LikeC4 accepts them)

<!-- Write-time mirror of tools/c4lint.py: the linter is the source of truth
     for the assertable subset — if you change a rule here, change the linter
     (and its fixture test) in the same edit. -->

**Nesting** — the only legal containment chain is `softwareSystem > container-kinds > component`:
- `person` and `softwareSystem` are top-level only; never nested inside anything
- `externalSystem` never has children — it's a black box by definition
- container kinds live directly inside a `softwareSystem`, never at top level, never inside another container
- `component` lives directly inside a container kind; never nest component in component (if tempted, the inner things are code elements — don't model them)

**Relationships:**
- Model relationships are unidirectional: never `<->` in `model` (fine in view predicates). If A and B call each other, write two relationships.
- **Black-box boundary (also the federation hinge):** never reach into another software system's internals. A relationship may reference another system only as a black box (`systemA -> systemB`), or a person may use a container. Reaching from/into a container/component of a *different* software system (`a.api -> b.db`) is a bug — it violates C4's system-as-black-box rule and breaks any future split into per-system projects. Cross-system wiring lives in `models/landscape.c4`, endpoints are the systems themselves.
- **Explicit references (house style):** name both endpoints; do not use `it`/`this` or sourceless `-> x`. (c4lint warns on these.)
- Every relationship gets a title with intent — a verb phrase like `'sends invoices to'`, never bare `'uses'` or `'calls'`
- Relationships **from a container/component** that cross a process boundary (container→container, container→another system/external, component→…) state technology/protocol via a nested `technology 'JSON/HTTPS'` property. Context-level system→system edges and person→container UI edges don't need one. SYNTAX TRAP: in `a -> b 'x' 'y'` the second string is the *description*, not technology.
- Point the arrow in the direction of intent and make the title match it. For messaging, show the flow explicitly: `orders -> queue 'publishes OrderPlaced to'` and `queue -> billing 'delivers OrderPlaced to'` (or `billing -> queue 'subscribes to'` — pick one convention per model and keep it).

**Descriptions & technology:**
- Every element has a `description` (or one-line `summary`) — "at a glance" responsibility
- Every container and component states `technology`; systems and people don't need one
- A server-rendered app is one container; add a significant SPA and it becomes two (separate process spaces)
- Queues/topics are `queue` containers (or, when noise-reducing, a labeled relationship) — never one giant "message bus" box hiding who talks to whom

**Views:**
- Every view has a `title` naming type and scope: `title 'System Context — Internet Banking System'`
- One abstraction level per view. Never `include` a component into a context/container view or vice versa. Dynamic views also stick to a single level (usually containers).
- The legend is generated from the `notation` property on kinds in the canonical spec — that's why kinds must not be invented ad hoc; a new kind without `notation` breaks the self-describing-diagram rule.

If the user explicitly asks to break a rule (e.g. deeper nesting for a huge estate), comply, but say which C4 rule is being bent and why it usually bites (readers can no longer infer the abstraction level from the diagram).

## Reviewing an existing LikeC4 model

Diff it against the hard rules above plus `references/methodology.md`; report violations grouped as: illegal abstractions/kinds, illegal nesting, unlabeled/vague/bidirectional relationships, missing tech/descriptions, level-mixing in views, missing titles/legend. Propose the minimal edit for each.
