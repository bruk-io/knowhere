---
globs: ["**/*.likec4", "**/*.c4"]
---

# C4 Relationship Rules (All Levels)

These rules apply to relationships at every level of the C4 model.

## Every Relationship MUST Have a Label
- No unlabeled arrows. Every `->` needs a description.
- The label answers: "What does this connection do?"

## Label Quality by Level

**Level 1 (Context):** Describe what, not how.
- "Views accounts and makes payments"
- "Sends notification emails to"

**Level 2 (Container):** Include technology/protocol.
- "Makes API calls using JSON/HTTPS"
- "Reads from and writes to using JDBC"
- "Publishes order events using Kafka"

Technology is required at this level because container relationships cross process or network boundaries — this inter-process communication is architecturally significant and must be made explicit.

**Level 3 (Component):** Focus on purpose. Most component-to-component interactions are in-process method/function calls — these do not need technology labels.
- "Validates authentication tokens"
- "Routes order requests to"
- "Transforms and persists"

If a component communicates with an external container or system across a process boundary, include the technology label — the same as you would on the container diagram.

## Anti-Patterns
- "Uses" - uses what? how?
- "Connects to" - everything connects
- "Interacts with" - how?
- "Calls" - calls what?
- "Data" - what data? which direction?
- Bidirectional arrows — prefer two directed relationships with specific labels instead

## Direction
- Arrow points from dependent to dependency
- Follow data flow or control flow direction
- When both read and write exist, combine if same path: "Reads from and writes to using SQL"
- Split into separate relationships if paths differ or distinction matters

## Dynamic View Relationships

In dynamic views (sequence/flow diagrams), relationship labels describe a specific runtime interaction step rather than a general architectural dependency:
- Labels describe the action or message at that step: "POST /login with credentials", "Returns authentication token"
- Steps must reference elements that exist in the static model (systems, containers, or components)
- Technology in the label is optional if already established in the container diagram

## Synchronous vs. Asynchronous

Optionally indicate interaction style using line styles:
- Solid line = synchronous (caller waits for response)
- Dashed line = asynchronous (fire-and-forget, event-driven, message queue)

This applies at Level 2 (Container) and Level 3 (Component). It is not required but adds useful information when a system mixes sync and async communication patterns.
