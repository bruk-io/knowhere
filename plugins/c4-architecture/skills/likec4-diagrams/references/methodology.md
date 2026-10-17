# Orthodox C4 methodology (condensed from c4model.com + Simon Brown's book/talks)

Source: c4model.com (CC BY 4.0), "The C4 model for visualising software architecture" (Simon Brown), and his slide decks. This file is the rulebook; SKILL.md holds the enforcement summary.

## File layout (the `scaffold.py` convention)

The scaffolder emits one federation-ready shape (there is no flat mode). Rules:

- **Three top-level folders + a shared spec.** `models/` (structure), `views/` (static views), `dynamic_views/` (scenarios), plus `shared/_spec.c4` (the vocabulary, one home) and a `.likec4rc`. LikeC4 merges all `.c4` files recursively regardless of folder, so the split is pure human organization the compiler is indifferent to.
- **One element per file; children via `extend`.** An element is declared in a file; if it has children, a same-named folder holds them, and each child is its own file that does `extend <parent-FQN> { child = … }`. `extend` requires the FULL dotted FQN from the model root — there is no relative or nested `extend` (verified against the compiler). References *inside* a block (relationships, view predicates) may use short bubbled names when unambiguous, so a rename only touches the `extend` headers in that element's subtree, not every reference.
- **Software systems declared in their own folder.** `models/<system>/<system>.c4` declares the top-level system; containers are `extend <system> { … }` in sibling files; components are `extend <system>.<container> { … }` one folder deeper. `landscape.c4` holds only people, external systems, and cross-system edges — never a system declaration.
- **Folder location = scope, for views.** `views/` root = estate-wide (System Landscape, cross-system); `views/<system>/` = scoped to that one system (Context, Container, Component). Same for `dynamic_views/`: `dynamic_views/<system>/` for single-system scenarios, `dynamic_views/cross-system/` for flows spanning systems.
- **Explicit references only.** Name both endpoints; no `it`/`this`, no sourceless `-> x` (c4lint warns).

## Federation-readiness (single project now, per-system projects later)

The layout is built so a software system can be promoted to its own LikeC4 project with ~two edits (add its `.likec4rc` with `include: ["../shared"]`, add an `import` in the landscape) — no restructuring. What keeps that cheap, and must hold from day one:

- **Spec isolated in `shared/`** so a split-out project reaches it via `include`.
- **Black-box boundary rule** (enforced by c4lint): cross-system relationships connect *systems*, never their internals. LikeC4's cross-project `import` exposes only top-level elements, so a container of system A can only ever reference system B as a black box — the tool enforces C4's own rule, and any edge that reaches into another system's internals would break on split. This is why `a.api -> b.db` is a lint error while `a -> b` is fine.
- **No cross-system container-level views** — you can place systems side by side as black boxes across a boundary, but not their containers, so keep cross-system views at the system/landscape zoom level.

Do NOT build federated promotion tooling yet; just keep these three properties true.

## The abstraction hierarchy

> A software system is made up of one or more containers (applications and data stores), each of which contains one or more components, which in turn are implemented by one or more code elements.

**Person** — a human user of your system(s). Roles, actors, personas. Not teams, not departments.

**Software System** — the highest abstraction; delivers value to users. Scoping heuristic: something a single team builds, owns, and can see inside. Bounded contexts, domains, and org structures are NOT systems. Systems you don't own internals of are external systems (black boxes).

**Container** — an application or data store: a runtime boundary that must be running for the system to work, and (usually) a separately deployable unit. Includes: server-side web apps, SPAs, desktop apps, mobile apps, console/batch apps, serverless functions, databases, schemas, file systems, blob stores (an S3 bucket you own is a container), queues and topics, shell scripts. Excludes: JARs, DLLs, assemblies, modules, libraries — those organize code inside a container. Nothing to do with Docker.
- Server-rendered app emitting mostly static HTML = ONE container. Significant client-side JavaScript (SPA) = TWO containers (separate process spaces, remote communication).
- Cloud services you configure and own data in (RDS, S3) are containers of your system.

**Component** — a grouping of related functionality behind a well-defined interface, running IN-PROCESS inside a container. Never separately deployable. If it deploys separately, it's a container. Component ≠ class: a component is typically implemented by multiple classes.

**Code** — classes, interfaces, functions. Don't hand-model; generate from IDE/tooling on demand.

## Diagram types and zoom discipline

| # | Diagram | Scope | Shows | Audience | Recommended? |
|---|---------|-------|-------|----------|--------------|
| 1 | System Context | one system | the system + people + neighboring systems | everybody, incl. non-technical | yes, always |
| 2 | Container | one system | containers inside the system + direct users/neighbors | technical, inside & outside team | yes, always |
| 3 | Component | one container | components inside that container | architects & developers in-team | only where it adds value; consider automating |
| 4 | Code | one component | classes etc. | in-team | generate on demand only |
| + | System Landscape | enterprise/portfolio | people + all systems, no internals | everybody | when >1 system |
| + | Dynamic | one scenario, one level | numbered/ordered interactions for a use case | technical | sparingly |
| + | Deployment | one environment | mapping of containers to infrastructure nodes | technical/ops | when infra questions arise |

Each diagram zooms exactly one level. Mixing levels (a component sitting next to systems) destroys the reader's ability to infer what a box means from its context.

## Notation rules (C4 is notation-independent, but these are mandatory)

Diagrams must stand alone — comprehensible with minimal narration.

- **Title** on every diagram, stating type and scope: "System Context diagram for Internet Banking System".
- **Key/legend** explaining every shape, color, border style, line style, arrow head, icon in use. (In LikeC4: generated from `notation` on kinds — another reason not to invent kinds.)
- **Every element**: name + explicit abstraction type + short "at a glance" description of responsibilities.
- **Every container and component**: explicit technology choice.
- **Every line**: unidirectional, labeled with intent — the description must match the arrow direction. Avoid vague single-word labels ("Uses", "Calls"). Two-way conversations = two lines.
- **Inter-process relationships**: name the protocol/technology, e.g. "JSON/HTTPS", "JDBC", "gRPC".
- **Acronyms**: expand or explain any the whole audience might not know.
- **Colors/shapes**: consistent within and across diagrams; must survive black-and-white printing and color-blindness.

## Messaging: queues and topics

Model queues/topics as data-store containers (queue shape). Two acceptable notations — pick one per model:
1. Explicit box: `producer -> queue 'publishes X to'`, `queue -> consumer 'delivers X to'` (or `consumer -> queue 'subscribes to'`).
2. Collapsed: a direct `producer -> consumer` relationship labeled "sends X to, via Kafka topic Y" when the queue box adds noise.

**Anti-pattern**: one giant "Message Bus" box with every service connected to it — it hides who talks to whom and makes the diagram meaningless. If everything connects to a bus, show the logical producer→consumer flows instead.

## Microservices note

"Is a microservice a system or a container?" — If you own the whole landscape, each microservice is usually a container of one larger system (deployment topology ≠ abstraction level). Treat a microservice as a separate software system only when it's owned by another team / genuinely opaque to you (Conway's Law scoping).

## Where LikeC4 will happily let you violate C4

LikeC4's docs say outright: "LikeC4 does not enforce specific rules, such as a strict number of levels or what should be included." Every one of these compiles fine and is still wrong under C4:

| LikeC4 permits | C4 verdict | This skill's rule |
|---|---|---|
| Arbitrary element kinds (`element pgTable`, `element epic`) | No such abstractions | Only the 10 canonical kinds |
| Any-depth nesting, any kind in any kind | Fixed 3-level containment | system > container > component, nothing else |
| `component` containing `system` | Nonsense hierarchy | Rejected |
| Top-level containers/components | Orphaned abstractions | Containers live in a system; components in a container |
| Children inside an external system | Externals are black boxes | `externalSystem` is always a leaf |
| `a <-> b` in model | Lines are unidirectional | Two `->` relationships |
| Untitled relationships | Every line labeled with intent | Title required |
| Views mixing levels (`include sys.**`) | One zoom level per diagram | Include one level; use navigateTo for drill-down |
| No view title | Title mandatory | Title required |
| Ad-hoc per-element styles | Legend must explain everything | Style via spec kinds only |

## Review checklist (run before delivering any diagram)

Mechanical items (kinds, nesting, descriptions, technology, titles, level-mixing, inter-process protocols) are enforced by `tools/c4lint.py` — run it; don't eyeball them.

Judgment items the linter cannot check:
- Does each relationship title reveal INTENT (what is it used FOR), and does it read correctly in the arrow's direction?
- Are systems scoped by the one-team-owns-it heuristic (not bounded contexts / org units)?
- SPA or heavy client-side JS split into its own container?
- Messaging shown as explicit producer→queue→consumer flows (no "message bus" black hole)?
- Acronyms understandable to the whole intended audience?
- Is each component view actually earning its place (would automation or the container view suffice)?
