# c4-architecture

Three complementary skills for producing software architecture diagrams that follow Simon Brown's C4 model faithfully — using the LikeC4 DSL, which is powerful but permissive, with orthodox-C4 discipline enforced on top.

## What's inside

**`c4-components`** — extracts a defensible component inventory from a real codebase. Detection is **ast-grep** (structural AST rules, each gated by valid/invalid tests) across the stack — TypeScript/JavaScript (NestJS, Express), Python (FastAPI/Flask, Django, Celery), Java & Kotlin (Spring incl. Spring Data), Swift (Vapor) — and the scanner pre-clusters matches by capability; explicit heuristics then group, exclude, and score them into an inventory with per-component confidence and file:line evidence. Use it when "what are the components of this service?" is the hard part.

**`likec4-diagrams`** — turns a C4 model (from the inventory above, a description, or an existing design) into orthodox-C4-correct LikeC4. It ships a canonical specification (the only allowed element kinds), a linter (`c4lint`) that mechanically enforces the assertable C4 rules LikeC4 doesn't — legal containment, one zoom level per view, labelled inter-process relationships, and more — wired to a PostToolUse hook so violations surface on every `.c4` edit, plus optional pattern-role tag profiles (layered / hexagonal / CQRS).

**`likec4-publish`** — publishes a LikeC4 model as an interactive Claude artifact: the full LikeC4 viewer (view list, drill-down, dynamic views, search, dark mode) at one private, shareable URL that survives republishing. Its `build-artifact.py` runs `likec4 build --output-single-file`, splits the bundle into the page plus `app.js`/`app.css` (the form the Artifact tool accepts), escapes the characters the validator rejects, and with `--verify` loads the page in headless Chromium to assert the app mounted and its stylesheet applied.

The three are designed to hand off to each other: extract components, diagram them, then publish the viewer. Bundling them as one plugin makes that handoff — and the shared C4 vocabulary — a guaranteed internal dependency rather than a coincidence of co-installation.

## Install

From the knowhere marketplace (Claude Code 2.1.275 or later):

```
/plugin install c4-architecture --marketplace bruk-io/knowhere
```

## Requirements

Python 3.9+ (all bundled tools — linter, scanner, scaffolder, hook, test suites — are stdlib-only Python), plus Node.js and `npx` for the two third-party CLIs the tools invoke: `likec4` (validation, JSON export, rendering) and `@ast-grep/cli` (structural code detection; `npm i -g @ast-grep/cli`, with an npx fallback). PNG export, and `likec4-publish --verify`, additionally need a Chromium available to Playwright.

## Tests

Each skill's tools carry a regression suite:

```
python3 skills/likec4-diagrams/tools/test-c4lint.py
python3 skills/c4-components/tools/test-signals.py
python3 skills/c4-components/tools/ast-grep/run-tests.py [real-codebase-dir]
```

## Parked (deliberate future work)

- **Quantitative extraction benchmark** against the microservice ground-truth dataset (Zenodo DOI `10.5281/zenodo.14179612`, CC-BY-4.0): 17 real Spring apps with hand-verified component/connector decompositions. Would yield precision/recall for the scanner + clustering layer and act as a regression benchmark for heuristic changes. Caveat: its granularity maps to containers/services more than in-process components.
- **Federated promotion tooling** (system → own LikeC4 project). The layout is already federation-ready (black-box rule linted, spec isolated in `shared/`); only the promotion mechanics are deferred.
