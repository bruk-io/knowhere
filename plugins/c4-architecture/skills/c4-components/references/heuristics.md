# Component identification heuristics

Grounded in Simon Brown's definition and his Spring PetClinic worked method (c4model.com/abstractions/component, CC BY 4.0): start from all classes → remove domain/utility noise → group what remains into units of related functionality → name the groupings. This file is the grouping step made explicit.

## The four tests (a candidate must pass all)

1. **Interface test** — callers interact with it through a describable surface (an exported class/module, a registered route set, a listener). If you can't say *how it's called*, it's not a component.
2. **In-process test** — it runs inside the container being decomposed. Separately deployable → it's a container; promote it and tell the user.
3. **Responsibility test** — its purpose fits one sentence without "and". Two sentences = two components (or a merge done wrong).
4. **Drawability test** — a developer would point at it when whiteboarding this container. If it only exists to make the diagram symmetrical, drop it.

## Seeding: from signals to candidates

From `component-signals.py` output, in order of reliability:

1. **Stereotype clusters (strongest).** The scanner's `candidateClusters.stereotypeClusters` already stem-groups by business noun (`OrdersController` + `OrdersService` + `OrderFacade` → one `Order` cluster) — start from those, don't re-derive them. Default convention (fixed, so re-runs converge): **merge controllers into their capability component; keep a controller standalone only when it holds real logic beyond routing** — deviate only if the user asks for PetClinic-style separate controllers, and note the deviation in the inventory. A `@Module`/`@Configuration` hit marks a boundary, not a component.
2. **Repository / interface seams.** A repository (Spring `@Repository`, Spring Data / Kotlin `interface … : JpaRepository`, or a `*Repository` type) names a deliberate data-access seam — a strong candidate-member; the scanner folds these into the stem clusters (`OwnerRepository` joins `Owner`).
3. **Route groups.** `candidateClusters.routeGroups` prefix-groups the routes (`/invoices/*`, 2 routes) — each group implies a component even in frameworks without class stereotypes (Express, Vapor). Your judgment: name it and check it against the four tests, not re-count the routes.
4. **Directory clusters (weakest alone).** A directory = a candidate only when it also shows an interface (barrel export, package surface). Folders are packaging, not components — but folder-per-capability codebases often map 1:1; verify, don't assume.
5. **Async surfaces.** Task/consumer registrations (Celery tasks, queue handlers) seed worker components — often missed because they have no HTTP route.

## Always exclude

Domain models / entities / DTOs / value objects; utils, helpers, common string/date/etc. code; configuration and wiring (DI modules, Startup, AppModule); generated code and migrations; test code; thin mappers/adapters with no logic; frameworks themselves (Spring is not a component of your app).

Shared code exception: a shared library becomes a component only when it has a named owner-surface (e.g. a `Pricing Engine` used via one interface by three components) — then it's drawn once with fan-in, not duplicated.

## Granularity calibration

- Container view target: **5–15 components.** Above ~20 → you've listed classes or sub-capabilities; merge along business capabilities. Below 3 → question whether the component diagram earns its place at all (Brown: optional, only-if-value, consider automating).
- Merge direction is capability-first: merge `InvoicePdfRenderer` into `Invoicing`, not into `Renderers`. Technical-layer groupings ("Repositories") are the classic failure — they restate the framework, not the architecture.
- Keep separate when: different business capability, different interface consumers, or different change cadence/ownership. Otherwise default to merging.

## Naming

- Business capability first: `Accounts Summary`, `Payment Authorization`, `Notification Dispatch`
- Pattern suffix only when it aids the reader: `Mainframe Banking System Facade`, `Sign-In Controller`
- Never name a component after a package (`com.x.y.z`), a layer (`Service Layer`), or a class you happen to like
- One convention per inventory — consistency across the diagram beats local precision

## Pattern-role tags (optional annotation layer)

When the container demonstrably follows a named pattern, tag each component with its role using the namespaced vocabulary from likec4-diagrams' `references/profiles/` (`#layered-presentation|application|domain|infrastructure`, `#hexagonal-core|port|driving-adapter|driven-adapter`, `#cqrs-command|query`). Rules:

- **Tags annotate, names structure.** `#layered-infrastructure Mainframe Facade` is right; `component InfrastructureLayer` stays banned. The tag carries the pattern role so the name can carry the capability.
- **One structural pattern per container** (layered OR hexagonal; cqrs marks the read/write axis and may overlay). Evidence-based: apply a profile only when the codebase actually exhibits it — don't tag a big-ball-of-mud as hexagonal aspirationally.
- **Mapping hints from scanner kinds:** controller/http-route → `layered-presentation` / `hexagonal-driving-adapter`; service → `layered-application` (or `hexagonal-core` when it holds the business rules); repository → `layered-infrastructure` / `hexagonal-driven-adapter`; task/consumer → driving side.
- Tags feed filtered views (`exclude * where tag is #layered-infrastructure`) and the legend via profile colors — no enforcement is attached to them.
- **Profile tags must be declared before use.** These role tags exist only in the profile fragments — so if you apply them, the diagram project MUST be scaffolded with the matching profile (`scaffold.py <dir> --profile hexagonal`), or `likec4 validate` fails on the undeclared tag. Carry the chosen pattern name into the handoff (step 6) so likec4-diagrams scaffolds with it.
- **Tags are pattern-role only — never language/framework-prefixed.** Language and framework live in the `technology` property (mandatory, rendered on the element) and, if machine-queryable filtering is genuinely needed (polyglot container), in `metadata { framework '...' }`. The language→framework hierarchy governs how a role is *derived* (scanner detector tables → stereotype → role mapping above), not how the tag is named: `hexagonal-core` must mean the same thing in Spring, Vapor, and NestJS so roles stay comparable across the whole estate.

## Confidence scoring (report per component)

- **High** — framework stereotype(s) + verified interface boundary (you read the surface and a caller)
- **Medium** — structural inference (directory + exports) without stereotype confirmation, or stereotype without boundary verification
- **Low** — naming convention only, or the user asserted it exists but code evidence is thin

Low-confidence components don't go into diagrams silently: flag them, tag them `#planned` (a declared tag in the canonical spec), or ask. Don't invent tags like `#unverified` — LikeC4 rejects undeclared tags at the `validate` gate.

## Cross-checks before delivering

- Sum test: do the components cover the container's main responsibilities? Something users depend on but no component owns → you missed one (often the async/worker path).
- Overlap test: no responsibility claimed by two components; if it is, the boundary is wrong.
- Re-run test: applying this file to the same signals again should yield the same inventory; if a judgment call was a coin-flip, record which way you flipped it and why in the exclusions line.
