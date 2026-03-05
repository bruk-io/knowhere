---
globs: ["**/code/**/*.likec4", "**/code/**/*.c4"]
---

# C4 Level 4: Code Rules

You are editing a Code level file. This is the most detailed abstraction level in C4.

## What Is a Code Diagram

A code diagram zooms into a single component and shows how it is implemented — typically as a UML class diagram or similar code-level representation. A code diagram helps answer: "How is a component decomposed into code-level building blocks?", "Which of these building blocks are publicly exported by the component, and which are internal implementation details?", and "How large and complicated is this component?"

**This level is almost never needed.** These questions can usually be answered by reading the code directly. IDEs can generate code diagrams on demand; manually maintained code diagrams age rapidly as code changes.

## When to Create Code Diagrams

Code diagrams are useful in two situations (per the book's Motivation section):
- To summarise a large and complicated component
- To illustrate how a particular design pattern or pattern of implementation works within a component

The book's explicit recommendation: "I wouldn't recommend diagrams at this level of detail for anything but the most important or complicated components." Create Level 4 only when one of the two criteria above clearly applies.

Before creating a code diagram, ask: "Can this question be answered by reading the code instead?" If yes, skip the diagram.

## When NOT to Create Code Diagrams

- For most components — Level 3 is usually sufficient
- For simple CRUD components, MVC layers, or well-understood patterns
- When the code is self-documenting
- When the component changes frequently (the diagram will be out of date immediately)
- For data store containers (databases, file systems) — use entity-relationship diagrams or schema documentation instead

## What Belongs Here

- Code-level building blocks supported by the programming language (e.g., classes and interfaces in packages and namespaces for Java/C#)
- Relationships between them (inheritance, composition, dependency)
- Only as much method/property detail as needed to tell the story — resist the temptation to include every property and method

## What Does NOT Belong Here

- Implementation details that don't affect the design (private helpers, formatting)
- Every single class in the codebase — focus on the key abstractions
- Elements from other components or containers (scope is a single component)

## Relationship with Other Levels

The component whose internals you are showing must appear as a named element at Level 3. Code diagrams are the deepest zoom — they do not have child diagrams.

## Diagram Key

Code diagrams should include a key or legend explaining shapes and notation used, consistent with the notation-independence principle that applies across all C4 levels. This is especially important if using a non-standard notation.

## Prefer Auto-Generation

Rather than maintaining code diagrams manually, prefer:
- IDE-generated class diagrams (IntelliJ, Visual Studio, etc.)
- Documentation tools that generate diagrams from code annotations
- Code comments or prose documentation for capturing key design decisions

## Audience

Engineers building or maintaining the software. This level of detail is typically far too much for other audiences (architects, product owners, business stakeholders).
