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

Apply Simon Brown's C4 model methodology when helping users design, review, or discuss software architecture. The C4 model is a set of abstractions for describing software architecture at four levels of detail.

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

**Audience:** Everyone - technical and non-technical stakeholders.

**Key question:** "What is the system and who/what interacts with it?"

### Level 2: Container

Zoom into the software system. Shows the high-level technology choices and how responsibilities are distributed.

**A container is:**
- A separately runnable/deployable unit
- Something that executes code or stores data
- Examples: web application, API, database, file system, message queue, serverless function, mobile app, single-page app

**A container is NOT:**
- A Docker container (though it could run in one)
- A class, module, or package
- A logical grouping or namespace

**What belongs here:**
- All containers within the software system boundary
- Relationships between containers
- External people and systems (from Level 1)

**Audience:** Technical people inside and outside the development team.

**Key question:** "What are the high-level technology decisions and how is the system structured at a deployment level?"

### Level 3: Component

Zoom into a single container. Shows the major structural building blocks and their interactions.

**A component is:**
- A grouping of related functionality behind a well-defined interface
- Examples: a set of related controllers, a service layer, a repository layer, a domain module

**A component is NOT:**
- A single class or function
- An implementation detail
- A utility or helper

**What belongs here:**
- Components within a single container
- Relationships between components
- External containers and systems that interact with this container

**Audience:** Software developers and architects working on or with the container.

**Key question:** "What are the major structural building blocks inside this container?"

### Level 4: Code

Zoom into a single component. Shows how the component is implemented (class diagrams, entity-relationship diagrams).

**When to create Level 4 diagrams:**
- Almost never manually. Prefer auto-generation from code.
- Only for the most critical or complex components.
- When onboarding developers to a complex domain model.

**When NOT to create Level 4 diagrams:**
- For simple CRUD components
- For well-understood patterns (MVC, repository, etc.)
- When the code is the documentation

**Audience:** Software developers working directly on the component.

## Decomposition Rules

Follow these rules when deciding how deep to decompose:

1. **Start at Level 1.** Every architecture should have a System Context diagram.
2. **Level 2 is almost always useful.** Create Container diagrams for any non-trivial system.
3. **Level 3 is optional.** Only create Component diagrams when the container's internal structure is complex or non-obvious.
4. **Level 4 is rarely needed.** Prefer auto-generated code diagrams. Only create manually for critical domain models.
5. **Stop when the diagram doesn't add value.** If the audience already understands the structure, don't diagram it.

## Relationship Guidelines

Relationships are the most important part of C4 diagrams. Follow these rules:

### Direction
- Relationships should flow in the direction of dependency or data flow
- "Uses", "calls", "sends data to", "reads from" indicate direction

### Labels
- Every relationship MUST have a label describing what the relationship is
- Use verb phrases: "Makes API calls using", "Reads from and writes to", "Sends notifications via"
- Include the technology/protocol when known: "Makes API calls using JSON/HTTPS"
- Be specific: "Sends order events to" not "Uses"

### What NOT to do
- Never use vague labels like "Uses", "Interacts with", or "Connects to" without more context
- Never create bidirectional relationships. Split into two directed relationships with specific labels.
- Never show relationships that don't exist or are purely aspirational

## Common Mistakes to Avoid

1. **Mixing abstraction levels.** Don't show databases (containers) on a System Context diagram.
2. **Too many elements.** If a diagram has more than 15-20 elements, decompose further or split views.
3. **Missing relationships.** Every element should have at least one relationship. Orphaned elements indicate a modeling error.
4. **Vague naming.** "Service" or "Module" is not a name. Use specific, descriptive names.
5. **Technology-first thinking.** Model the architecture, then assign technologies. Don't let tools drive the model.
6. **Confusing containers with components.** If you can't deploy it independently, it's probably a component, not a container.

## Notation Conventions

When creating C4 models:
- **People:** Use the person shape. Name by role, not individual.
- **Software systems:** Rectangles. Include a brief description of what the system does.
- **Containers:** Rectangles within a system boundary. Include technology choice.
- **Components:** Rectangles within a container boundary. Include technology/pattern.
- **External systems:** Grey or muted color to distinguish from the system in scope.
- **Boundaries:** Use dashed lines to group containers within a system or components within a container.

## References

For detailed guidance on specific topics, see:
- `references/decomposition-decision-tree.md` - When and how to decompose
- `references/relationship-patterns.md` - Common relationship patterns and anti-patterns
