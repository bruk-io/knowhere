---
globs: ["**/components/**/*.likec4", "**/components/**/*.c4", "**/views/components/**/*.likec4", "**/views/components/**/*.c4"]
---

# C4 Level 3: Component Rules

You are editing a Component level file. This level shows the internal structure of a single container.

## What Is a Component
- A grouping of related functionality behind a well-defined interface
- All components within a container run in the same process space and communicate via in-process method/function calls. This is the key distinction from containers: if two things communicate out-of-process (over a network or across OS process boundaries), they are containers, not components.
- Examples: auth module, payment processor, order repository, API controller layer

## What Is NOT a Component
- A single class or function (too granular)
- An implementation detail (internal helper, utility)
- A deployment unit (that's a container)

## What Belongs Here

A component diagram usually includes six element types (per the book):
1. **People** — carried forward from the container diagram
2. **Software systems** — carried forward from the container diagram
3. **Containers** — other containers from the container diagram (not the one being decomposed)
4. **Components** — within the single container being decomposed
5. **Container boundary** — a box drawn around the components
6. **Software system boundary** — optionally drawn around the container boundary for hierarchy clarity

**One diagram per container.** If your system has three application containers, draw three separate component diagrams — one per container. Do not combine the internals of multiple containers onto one diagram; it increases cognitive load and obscures boundaries.

**Reflect the architectural style.** The component diagram should mirror the actual structure of the container's code. If the code is organised in layers (presentation, business logic, data access), show those layers. If the container uses a ports-and-adapters style, reflect that. Imposing a different structure on the diagram creates a misleading picture of how the system is actually built.

## When to Create Component Diagrams

Brown recommends component diagrams "as an optional level of detail to most engineering teams, both for up-front design exercises and for long-lived documentation" — but not to all teams. Create one when:
- You are doing up-front design for a small to medium size application and want to sketch an initial high-level code structure (for larger applications, up-front component diagrams become tedious and time consuming — the book explicitly warns against this)
- You need long-lived documentation of a larger application's internal decomposition, and the benefit justifies the ongoing maintenance cost

A single-endpoint microservice or data store does not warrant a component diagram regardless of team size.

## When NOT to Create Component Diagrams
- The container is a data store (database, file system, blob store, content store) — use entity-relationship diagrams or schema documentation instead
- The container follows a well-known pattern (simple MVC, CRUD API) or is simple in nature (e.g., a single-purpose API endpoint, a thin adapter layer) — complexity justifies the diagram, not team size
- The code itself is the best documentation
- The internals change frequently — component diagrams age rapidly as code evolves; weigh the maintenance cost against the benefit

## Relationship Rules at This Level
- Technology details are optional (internal method calls don't need protocol labels)
- Focus on purpose: "Validates tokens", "Routes requests", "Manages sessions"
- Include technology when a component communicates with an external container or system across a process boundary — same as you would on the container diagram
- Optionally indicate synchronous vs. asynchronous using line styles: solid = synchronous, dashed = asynchronous

## Audience

Technical people within the software engineering team — architects, engineers, third-level support staff, and maintenance engineers. Component diagrams may occasionally be useful for non-technical stakeholders but that is not the intended audience.

## Continuity with Level 2

The containers from the parent container diagram must be visible in component diagrams — typically as external boxes shown interacting with this container's components. This reinforces the hierarchical reading thread: the component diagram tells a more detailed version of the same story shown at Level 2.

Maintain naming consistency: a container called "API Gateway" at Level 2 must appear with that same name at Level 3.

## Diagram Key

Every component diagram must include a key or legend explaining shapes, colors, and line styles used. See the c4-methodology skill for key/legend guidance.

## Element Count
- The book notes diagrams become cluttered "once you have more than a handful of components" — the book gives no numeric definition of "handful." Use it as a prompt to question whether the diagram remains readable, not as a hard limit.
- Most components should have at least one relationship — flag components with no relationships and consider whether they belong on the diagram
