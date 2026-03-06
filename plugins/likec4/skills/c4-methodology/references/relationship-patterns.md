# C4 Relationship Patterns

## Good Relationship Labels

Relationships are the connective tissue of C4 diagrams. A good label answers: "What does this connection do and how?"

### Pattern: Verb + Object [+ Technology at Container Level]

Technology is **strongly recommended** at Level 2 (Container) — the book says "I recommend adding the technology details (e.g. primary protocol) to the relationship." Technology is **optional** at Level 3 (Component, since most component-to-component calls are in-process method calls), and **not needed** at Level 1 (Context — describe what happens, not how).

| Example | Level | Has Technology? |
|---------|-------|-----------------|
| "Sends order events using Kafka" | Container | Yes (recommended) |
| "Reads/writes customer data using JDBC" | Container | Yes (recommended) |
| "Makes API calls using JSON/HTTPS" | Container | Yes (recommended) |
| "Delivers email notifications using SMTP" | Container | Yes (recommended) |
| "Fetches product catalog" | Component | No (internal call) |
| "Validates authentication tokens" | Component | No (internal call) |
| "Views account balances and makes payments" | Context | No (omit at this level) |

### Pattern: Action Description (Context Level)

At Level 1, describe what the person/system does, not how:

| Example |
|---------|
| "Views account balances and makes payments" |
| "Sends account activity notifications to" |
| "Gets account information and financial transactions from" |

## Anti-Pattern: Vague Labels

These labels tell you nothing:

| Bad Label | Why | Better |
|-----------|-----|--------|
| "Uses" | Uses how? For what? | "Queries product data using GraphQL" |
| "Connects to" | Everything connects | "Publishes events to" |
| "Interacts with" | How? | "Authenticates users via OAuth2" |
| "Calls" | Calls what? | "Fetches user profiles using REST/JSON" |
| "Data" | What data? Which direction? | "Stores session data in" |

## Relationship Direction

### Convention: Follow the Dependency or Data Flow

The most common convention is to point the arrow from the dependent to the dependency, following the direction of usage or data flow. The C4 model's own examples follow this pattern:
- `Web App -> API` (web app calls the API)
- `API -> Database` (API reads from/writes to the database)
- `User -> Web App` (user uses the web app)

The book's guidance is to use unidirectional arrows with descriptive labels — the specific direction convention is not mandated, but following the dependency/flow direction is the most widely understood approach.

### Rule: Separate Read and Write When It Matters

If reads and writes go through different paths or the distinction matters:
- `API -> Database 'Reads customer records from'`
- `API -> Database 'Writes transaction logs to'`

If not, combine:
- `API -> Database 'Reads from and writes to using SQL'`

### Rule: Prefer Unidirectional Arrows

The book recommends unidirectional arrows at every level. Avoid bidirectional arrows; if two directions serve distinct purposes, use two directed relationships with specific labels:

`Service A -> Service B 'Sends order confirmations to'`
`Service B -> Service A 'Publishes inventory updates to'`

## Relationships by Level

### Level 1 (Context)
- Between people and your system
- Between your system and external systems
- Focus on WHAT, not HOW
- No technology details needed

### Level 2 (Container)
- Between containers within your system
- Between containers and external systems/people
- Include technology/protocol: "using JSON/HTTPS", "via gRPC", "using AMQP"

### Level 3 (Component)
- Between components within a container
- Between components and external containers
- Can omit technology when it's internal method calls
- Focus on purpose: "validates", "transforms", "routes"

## Synchronous vs. Asynchronous

At the Container and Component levels, you can optionally indicate whether an interaction is synchronous or asynchronous using line styles:
- **Solid line** = synchronous (caller waits for response)
- **Dashed line** = asynchronous (fire-and-forget, event-driven, message queue)

This is not required, but adds useful context when a system mixes synchronous and asynchronous communication patterns — particularly at the Container level where async messaging (Kafka, SQS, RabbitMQ) is common alongside synchronous API calls.

## Common Mistakes

1. **Too many relationships.** If every element connects to every other element, your architecture has coupling problems (or your diagram does).
2. **Missing relationships.** Elements with no connections may not belong on the diagram — flag them and use judgment: include elements only when they help tell the story to the intended audience.
3. **Inconsistent granularity.** Don't mix "Makes API calls using JSON/HTTPS" with "Uses" on the same diagram.
4. **Showing infrastructure relationships.** Load balancers, DNS, and network routing are not C4 relationships. Those belong in deployment diagrams.
