---
name: modeling-c4-architecture
description: >
  Provides Simon Brown's C4 model methodology for software architecture modeling.
  Covers the four abstraction levels (System Context, Container, Component, Code),
  decomposition rules, relationship semantics, and audience guidance. Use when
  discussing C4 architecture, system context diagrams, container diagrams, component
  diagrams, architecture abstractions, decomposition decisions, or modeling
  software architecture using the C4 approach.
---

# C4 Architecture Methodology

Apply Simon Brown's C4 model methodology when helping users design, review, or discuss software architecture. The C4 model is a set of hierarchical diagrams for describing the static structure of a software system at various levels of abstraction. It is **not a software design process** — you can use it to describe an existing system or to think through a new one, but it does not prescribe how design decisions are made.

## Core Abstractions

The C4 model is built on a set of hierarchical abstractions that form a shared vocabulary for describing software systems. The "four" in "C4" refers to the four diagram types (System Context, Containers, Components, Code) — not the number of abstractions. There are five:

- **Person** — one of the human users (actors, roles, personas, or named individuals) of your software system
- **Software System** — the highest level of abstraction; something that delivers value to its users, whether human or not
- **Container** — a runtime concept; a separately deployable/runnable unit that needs to be running for the software system to work (application or data store)
- **Component** — a grouping of related functionality encapsulated behind a well-defined interface, running inside a container
- **Code** — the internal building blocks of a component: classes, interfaces, enums, functions, objects (the lowest abstraction level)

"Containers contain components" is another way to remember this, and helps to explain where the "container" name came from — all components inside a container run in the same process space and communicate via in-process method calls. The name "container" was also chosen because it doesn't imply anything about the physical nature of how that container is executed or deployed.

## The Four Abstraction Levels

### Level 1: System Context

The highest level. Shows the software system in scope and its relationships with users and other systems.

**What belongs here:**
- The software system being described (one per diagram)
- People (users, actors, roles) who interact with it
- External software systems the system depends on or that depend on it

**What does NOT belong here:**
- Internal structure of any system
- Technologies, protocols, or implementation details
- Databases, message queues, or infrastructure

**Audience:** Everyone — both technical and non-technical people, inside and outside the engineering team. This is the one diagram that should be understandable without any technical background.

**Additional use:** System context diagrams are also valuable during requirements gathering — drawing one in a workshop ensures everyone agrees on the system boundary and what is in or out of scope.

**Key question:** "What is the system and who/what interacts with it?"

### Level 2: Container

Zoom into the software system. Shows the high-level technology choices and how responsibilities are distributed.

**A container is:**
- A runtime concept — something that needs to be running for the overall software system to work
- A separately deployable/runnable unit representing a boundary around code being executed or data being stored
- Isolated from other containers — communication between containers crosses a process or network boundary (out-of-process call), which is why technology/protocol labels are required on container relationships
- Examples: web application, API, database, file system, message queue, serverless function, mobile app, single-page app, shell script, console application

**A container is NOT:**
- A Docker container (though it could run in one)
- A class, module, or package
- A logical grouping or namespace

**What belongs here:**
- All containers within the software system boundary
- Relationships between containers
- External people and systems (from Level 1)

**Audience:** Software architects and engineers building or maintaining the software are the primary audience. Container diagrams are also useful for: operations and support staff who need to understand what they are running; QA engineers performing technical testing; compliance teams and architecture review boards conducting risk reviews or threat modelling; and non-technical product owners verifying which containers are affected by a planned feature.

**Key question:** "What applications and data stores make up the system, what are their responsibilities, and what are the key technology choices?"

**Critical:** Container diagrams should say very little — ideally nothing — about deployment (cloud environments, servers, Kubernetes, load balancers, firewalls). Deployment details vary across environments and belong in deployment diagrams.

### Level 3: Component

Zoom into a single container. Shows the major structural building blocks and their interactions.

**A component is:**
- A grouping of related functionality behind a well-defined interface
- All components inside a container execute in the same process space and communicate via in-process method/function calls — this is the key contrast with containers, which communicate out-of-process
- Examples: a set of related controllers, a service layer, a repository layer, a domain module

**A component is NOT:**
- An individual class or function without a well-defined interface encapsulating related logic
- An implementation detail (internal helper, utility)
- A deployment unit (that's a container)

**What belongs here:**
- Components within a single container
- Relationships between components
- External containers and systems that interact with this container

**One diagram per container.** Each component diagram is scoped to exactly one container. If your system has three application containers, draw three separate component diagrams — one per container. Do not combine the internals of multiple containers onto one diagram; it increases cognitive load and obscures process boundaries.

**Reflect the architectural style.** The component diagram should mirror the actual structure of the container's code. If the code is organised in architectural layers (presentation, business logic, data access), the diagram should show those layers. If the container uses a ports-and-adapters or hexagonal style, the diagram should reflect that too. Imposing a different structure on the diagram than the code actually uses is misleading.

**Audience:** Technical people within the software engineering team — architects, engineers, third-level support staff, and maintenance engineers. Component diagrams may occasionally be useful for non-technical stakeholders but that is not the intended audience.

**Key question:** "What are the major structural building blocks inside this container?"

### Level 4: Code

Zoom into a single component. Shows how the component is implemented using the basic building blocks of the programming language — classes, interfaces, enums, functions, objects — often visualised as a UML class diagram.

**When to create Level 4 diagrams:**
- Almost never manually. Prefer auto-generation from code (IDEs can produce these on demand).
- Only for the most critical or complex components — when the component is large and complicated enough that a visual summary adds clarity beyond reading the code.
- To illustrate how a particular design pattern works within a component.

**When NOT to create Level 4 diagrams:**
- For simple CRUD components
- For well-understood patterns (MVC, repository, etc.)
- When the code is the documentation

**Audience:** Engineers building or maintaining the software.

## Supporting Views

Beyond the four static structure levels, the C4 model defines three supporting view types:

**System Landscape**
A map of all software systems within a chosen scope (e.g. organisation, group, department, business function). Shows every system and how they relate — use it to provide orientation before zooming into individual system context diagrams. Every system you own should also have its own system context diagram. Audience: everyone, including senior stakeholders wanting the full picture.

**Dynamic Diagram**
Shows how elements in the static model (software systems, containers, components, or code elements) collaborate at runtime to implement a specific user story, use case, or feature. The most common form is a UML sequence diagram. Use for critical user journeys, complex multi-service interactions, and async workflows. Audience: same as the level at which the view is drawn.

**Deployment Diagram**
Shows how instances of software systems and/or containers are deployed onto infrastructure in a given deployment environment. Create one per unique deployment environment (production, staging, dev). Audience: developers and infrastructure/operations staff.

## Decomposition Rules

Follow these rules when deciding how deep to decompose:

1. **Start at Level 1.** Every architecture should have a System Context diagram.
2. **Level 2 is recommended for all teams.** Create a Container diagram for every software system — it is the primary way to show how a system has been decomposed into applications and data stores.
3. **Level 3 is optional.** Brown recommends component diagrams "as an optional level of detail to most engineering teams, both for up-front design exercises and for long-lived documentation" — but would not mandate them for all teams. For up-front design, component diagrams work well for small to medium size applications — for larger applications, they become tedious and time consuming (the book explicitly warns against this). For long-lived documentation of larger applications, create them when the benefit justifies the ongoing maintenance cost. Component diagrams age rapidly as code changes.
4. **Level 4 is rarely needed.** Prefer auto-generated code diagrams from IDEs. Only create manually for the most important or complicated components — where a visual summary adds clarity beyond reading the code.
5. **Use only diagram types that add value.** The system context and container diagrams are sufficient for most software development teams. Weigh the benefit of Levels 3 and 4 against the cost of keeping them accurate over time.
6. **Continuity between levels.** Each child diagram tells a more detailed version of the same story as its parent. The people and software systems from a context diagram must reappear on the container diagram. The containers surrounding a component diagram must reappear on that diagram. This continuity is what makes the reading order (context → container → component) coherent.

## Relationship Guidelines

Follow these rules:

### Direction
- Relationships should flow in the direction of dependency or data flow
- "Uses", "calls", "sends data to", "reads from" indicate direction

### Labels
- Every relationship MUST have a label describing what the relationship is
- Use verb phrases: "Makes API calls using", "Reads from and writes to", "Sends notifications via"
- Technology/protocol inclusion depends on the abstraction level:
  - **Level 1 (Context):** omit technology — describe what happens, not how
  - **Level 2 (Container):** required — include the primary protocol (e.g., "JSON/HTTPS", "gRPC/TLS", "JDBC")
  - **Level 3 (Component):** omit for internal method calls; include only if applicable for cross-container relationships
- Be specific: "Sends order events to" not "Uses"

### Synchronous vs. Asynchronous

At container level and below, you may optionally indicate interaction style using line styles:
- Solid line = synchronous (caller waits for response)
- Dashed line = asynchronous (fire-and-forget, event-driven, message queue)

This is not required but adds useful information when a system mixes synchronous and asynchronous communication patterns.

### What NOT to do
- Never use vague labels like "Uses", "Interacts with", or "Connects to" without more context
- Prefer unidirectional relationships. When both directions exist, split into two directed relationships with specific labels — this often reveals the two directions serve different purposes.
- Never show relationships that don't exist or are purely aspirational

## Common Mistakes to Avoid

1. **Mixing abstraction levels.** Don't show databases (containers) on a System Context diagram.
2. **Too many elements.** Component diagrams become cluttered quickly — even a handful of components with crossing relationships reduces clarity. Context and container diagrams can handle more elements, but there is no universal safe threshold. Prefer multiple focused diagrams over one crowded diagram.
3. **Missing relationships.** Most elements should have at least one relationship. If an element has no relationships, question whether it belongs on the diagram — but use judgment: include elements only when they help tell the story to the intended audience.
4. **Vague naming.** "Service" or "Module" is not a name. Use specific, descriptive names.
5. **Technology-first thinking.** Model the architecture, then assign technologies. Don't let tools drive the model.
6. **Confusing containers with components.** If you can't deploy it independently, it's probably a component, not a container.
7. **Omitting technology choices.** Technology decisions are architectural decisions — they are expensive to change and must be shown. "We don't want to constrain developers" is not a reason to omit them; include developers in the design process instead.
8. **Deployment details in container diagrams.** Load balancers, Kubernetes, cloud regions, and firewalls do not belong on container diagrams. They belong in deployment diagrams.
9. **Component diagrams for data stores.** Don't create component diagrams for databases, file systems, or content stores — they are better documented using entity relationship diagrams.
10. **Unexplained acronyms and abbreviations.** "CRM", "SOR", "ERP" mean different things in different organisations. Every acronym must be spelled out in full or explained in the diagram's key/legend. Never assume shared vocabulary.
11. **Inconsistent naming across levels.** An element called "Core Banking System" at Level 1 must appear with the same name at Level 2 and Level 3. Renaming elements between levels breaks the hierarchical reading thread and creates ambiguity about whether they represent the same thing.
12. **Diagrams that require explanation.** A diagram that needs a verbal walkthrough to be understood has limited value, especially as long-lived documentation. Any narrative should *complement* the diagram, not *explain* it. Test your diagram: give it to somebody unfamiliar with the system — if they cannot interpret it, it needs better labels, descriptions, or a clearer key.
13. **Ambiguous diagrams create divergent interpretations.** Diagram ambiguity causes team members to form different — and incompatible — mental models of the same architecture. An unlabelled box that one person reads as a microservice another reads as a module inside a monolith. Ambiguity is not an aesthetic problem; it is a communication failure.

## Notation Conventions

The C4 model is notation-independent — it does not prescribe specific shapes, colors, or line styles. The conventions below are LikeC4 defaults and common C4 practice; any notation is valid provided every diagram includes a key/legend explaining what the visual elements mean.

When creating C4 models:
- **Diagram titles:** Every diagram must have a descriptive title identifying the software system, the diagram type (System Context / Container / Component / Code), and where relevant the element being decomposed (e.g. "Internet Banking System — API Application — Components").
- **People:** Use the person shape. Name by role, not individual.
- **Software systems:** Rectangles with rounded corners (per the book's notation convention). Include a brief description of what the system does.
- **Containers:** Rectangles within a system boundary. Include technology choice.
- **Components:** Rectangles within a container boundary. Include technology/pattern.
- **External systems:** Grey or muted color to distinguish from the system in scope.
- **Boundaries:** Use dashed lines to group containers within a system or components within a container.
- **Diagram key/legend:** Every diagram must include a key or legend explaining the notation used — shapes, colors, and line styles. Think of C4 diagrams like maps: maps show the same abstractions (roads, rivers, towns) using varying notation across publishers, and what makes any map readable is its key. The same principle applies here — the key is what makes a C4 diagram self-explanatory regardless of what tool or visual style was used. Never assume the reader already knows what the visual elements mean.
- **Cross-diagram notation consistency.** The same element type should use the same visual style across all diagrams. A person shape at Level 1 should not become a plain box at Level 2.

## Diagram Volatility

Diagrams age at different rates by level. System context and container diagrams tend to be stable and change infrequently. Component and code diagrams are significantly more volatile and will change rapidly as code evolves. Factor this maintenance cost into the decision to create and maintain diagrams at Levels 3 and 4.

## When C4 Is Not the Right Tool

The C4 model works well for custom-built, bespoke software systems using general-purpose programming languages. It is less suited to:
- Embedded systems and firmware
- Heavy platform customisation (e.g., SAP, Salesforce) where you configure rather than build
- Libraries, frameworks, and SDKs

Even in these cases, system context and container diagrams may still provide value. All of these may be better described using UML, for example.

## Complementary Diagram Types

C4 is not a replacement for all diagram types. Use these alongside C4 diagrams when appropriate:
- **UML activity diagrams** — for business processes and workflows
- **UML state charts** — for state machines
- **UML class diagrams** — for domain models
- **Entity relationship diagrams** — for relational data models
- **ArchiMate diagrams** — for enterprise architecture layers

Dynamic C4 views show runtime collaboration between architectural elements. They do not replace activity diagrams for modelling business workflows or state charts for modelling state machines.

## References

For detailed guidance on specific topics, see:
- `references/decomposition-decision-tree.md` - When and how to decompose (includes System Landscape guidance)
- `references/relationship-patterns.md` - Common relationship patterns and anti-patterns
