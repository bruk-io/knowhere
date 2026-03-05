---
globs: ["**/context.likec4", "**/context.c4", "**/views/context/**/*.likec4", "**/views/context/**/*.c4"]
---

# C4 Level 1: System Context Rules

You are editing a System Context level file. This is the highest abstraction level in C4.

## What Is a Software System

A software system is something that delivers value to its users (whether human or not), typically built and owned by a single software development team that has full responsibility for it — the team can see its internal implementation details. Its code typically lives in a single repository. The boundary of a software system usually corresponds to the boundary of a single team.

**Things that are NOT software systems in C4:** product domains, bounded contexts, business capabilities, feature teams, tribes, or squads. If you are trying to model one of these, you are likely at the wrong level of abstraction.

## What Belongs Here
- The software system in scope (one primary system)
- People/actors who use the system (by role, not by name)
- External software systems that interact with the system in scope

## What Does NOT Belong Here
- Containers (databases, APIs, web apps) - those are Level 2
- Components (modules, services) - those are Level 3
- Technologies, protocols, or implementation details
- Infrastructure (servers, Kubernetes, cloud regions)

## Relationship Rules at This Level
- Every relationship arrow must have a label — unlabelled arrows are a diagramming anti-pattern
- Represent relationships as unidirectional arrows showing direction of dependency or data flow
- Describe WHAT the relationship does, not HOW
- Good: "Views accounts and makes payments"
- Bad: "Makes API calls using JSON/HTTPS" (too technical for Level 1)
- Most elements should have at least one relationship — flag elements with no relationships and consider whether they belong on the diagram

## Element Naming
- Name actors by role: "Customer", "Admin", "Support Agent"
- Name systems by purpose: "Online Banking System", "Email Provider"
- External systems should use `style { color muted }` to de-emphasize

## Audience

Everyone — both technical and non-technical people, inside and outside the engineering team. This is the one diagram that should be understandable without any technical background.

## Multiple Versions

Multiple versions of a system context diagram are valid — for example, one focused on functional users and one for system administrators/operational staff — when different audiences need different perspectives.

## Why This Diagram Matters

A system context diagram answers four essential questions:
- What is the software system being built (or already built)?
- Who is using it?
- What are those users doing with it?
- How does it fit into the existing system landscape?

It makes the context and scope of the system explicit, so there are no assumptions. It provides an entry point for new engineers, a shared starting point for technical and non-technical conversations, and a foundation for the more detailed diagrams at Level 2 and beyond.

## Diagram Key

Every diagram must include a key or legend that explains the notation used — shapes, colors, and line styles. The C4 model is notation-independent by design; the key is what makes any notation intelligible to readers.

## Self-Contained Diagrams

Every diagram should be able to stand alone without a verbal walkthrough. A self-contained diagram requires at minimum: a descriptive title, a key/legend, and labelled relationships. If a diagram requires explanation to be understood, it needs better labels, descriptions, or a clearer key. Any narrative should *complement* the diagram, not *explain* it.
