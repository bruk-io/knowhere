---
name: c4-components
description: Extract and define C4 components from a codebase consistently — turn framework stereotypes, directory structure, and interfaces into a defensible component inventory. Use whenever the user asks what the architectural components of a codebase/service/container are, wants to decompose a container, says components are hard to identify, asks "what should be a component here", wants a component inventory or component-level architecture description, or needs the component list feeding a C4 component diagram. Also use to review an existing component list for granularity and consistency. NOT for UI/React/Vue component design or authoring — this is the C4 architecture abstraction, not view-layer widgets.
argument-hint: "[repo-path] [container-scope]"
---

# C4 component extraction (consistent, evidence-based)

Target (if given): $ARGUMENTS

A component is **a grouping of related functionality encapsulated behind a well-defined interface, running in-process** — never separately deployable (that's a container), never a bare class (that's code). Components are where diagramming gets inconsistent because codebases don't label them; this skill makes the call the same way every time: deterministic signals first, then explicit grouping heuristics, then evidence-backed output.

## Workflow

1. **Fix the scope to ONE container.** A component inventory is per-container (one process space). If the repo holds several deployable units, name which one you're decomposing before anything else — mixing them produces container-level things mislabeled as components.

2. **Scan for signals (deterministic):**
   ```
   python3 <skill-dir>/tools/component-signals.py <repo-or-container-dir>
   ```
   Emits JSON: framework stereotypes (controllers, services, repositories, routes, tasks) with file:line evidence and detected language, directory clusters, entry points. This is *candidate evidence*, not the answer — a stereotype hit is one vote, not a component. Detection is done by **ast-grep** (structural AST rules under `<skill-dir>/tools/ast-grep/`, each gated by valid/invalid test cases) — no regex false positives from comments/strings, and multi-line-safe. Stack covered: TypeScript/JavaScript (NestJS, Express), Python (FastAPI/Flask, Django, Celery), Java & Kotlin (Spring incl. Spring Data), Swift (Vapor). Requires ast-grep: `npm i -g @ast-grep/cli` (the scanner falls back to `npx @ast-grep/cli` if it's not on PATH). To add a framework/language, add a rule + a test case and gate it with `python3 <skill-dir>/tools/ast-grep/run-tests.py <a-real-codebase>` — a rule isn't trusted until its tests pass AND you've inspected its matches on real code. Rule id convention: `<c4-kind>__<framework>__<language>`.

3. **Group with the heuristics** in `references/heuristics.md` — the judgment step, and the source of truth for the seeding rules, the four tests, the exclusion list, granularity calibration, and confidence scoring. The shape of the move: seed candidates from the scanner's stereotype clusters (a controller + the services/repositories it drives is usually one capability component, not three), then merge/split/discard against `heuristics.md` until each survivor passes its four tests.

4. **Verify with code, not vibes.** For each candidate, Read its interface surface (the exported/public entry file) and one caller. Confirm the boundary is real — callers actually go through it. Demote candidates you can't evidence.

5. **Deliver the inventory** as a table: Name | Responsibility (one sentence) | Interface (how it's called) | Technology | Evidence (files) | Confidence (per `heuristics.md` § Confidence scoring). State what you excluded and why in one line.

6. **Handoff to diagrams.** If a diagram is wanted, invoke the `likec4-diagrams` skill; each inventory row becomes `component <name> { technology '...' description '...' }` inside the scoped container, relationships from the verified caller evidence. Low-confidence candidates go in tagged `#planned` (declared in the canonical spec) or get flagged to the user, not silently drawn. **If you assigned pattern-role tags** (`#hexagonal-*` etc.), tell likec4-diagrams which pattern you used so it scaffolds with the matching profile (`scaffold.py <dir> --profile <pattern>`) — those tags are undeclared without it and fail the validate gate.

## Consistency rules (same codebase → same components)

- Evidence over intuition: every component names at least one file:line signal or verified boundary; no component exists only because "there's usually an X layer"
- One naming scheme per inventory: name by business capability (`Accounts Summary`, `Payment Authorization`) with the pattern as suffix only when it clarifies (`... Controller`, `... Facade`); never mix capability-names and layer-names in one inventory
- Layers are not components: "the service layer" is not a component; the things *in* it might be
- Shared code used by many components stays code (or becomes one `Common`/named library component only if it has a real interface and owner)
- Same rules on re-runs: if a re-scan produces a different inventory for unchanged code, the grouping step drifted — re-apply the heuristics file, don't improvise

If the user's codebase genuinely resists this (no framework, no structure), say so and fall back to directory-cluster + entry-point grouping with everything marked medium/low confidence — an honest sparse inventory beats an invented tidy one.
