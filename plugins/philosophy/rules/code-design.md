---
paths:
  - "**/*.py"
  - "**/*.pyi"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.mjs"
  - "**/*.go"
  - "**/*.rs"
  - "**/*.swift"
  - "**/*.kt"
  - "**/*.java"
  - "**/*.rb"
  - "**/*.ex"
  - "**/*.exs"
  - "**/*.c"
  - "**/*.h"
  - "**/*.cpp"
  - "**/*.cs"
mode: owner
---

# Every choice tells the reader something

Applies when reading or writing source code in a repository I own.

- What the code says must be true. A mutable collection says the data will change, and
  a public name says it has callers elsewhere, so everything starts private.
- Inheritance claims one thing is a kind of another, and few designs truly have that
  relationship. Build from plain data and functions.
- Functional core, imperative shell. Logic takes data and returns data, and the work
  that can fail (files, networks, databases) stays at the edges.
- A module boundary is a statement that one piece of code does not depend on another.
  Enforce it with import rules.
- The readers decide what is readable, and the readers include AI agents. The shared
  style of a language's community outranks my private preferences when they disagree.
- Exceptions are for exceptional situations, never for ordinary control flow. Handle
  errors the way the language's community does, and document what a function can throw.
