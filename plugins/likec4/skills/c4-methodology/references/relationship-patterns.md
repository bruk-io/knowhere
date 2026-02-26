# C4 Relationship Patterns

## Good Relationship Labels

Relationships are the connective tissue of C4 diagrams. A good label answers: "What does this connection do and how?"

### Pattern: Verb + Object + Technology

| Example | Level |
|---------|-------|
| "Sends order events using Kafka" | Container |
| "Reads/writes customer data using JDBC" | Container |
| "Makes API calls using JSON/HTTPS" | Container |
| "Delivers email notifications using SMTP" | Container |
| "Fetches product catalog" | Component |
| "Validates authentication tokens" | Component |
| "Views account balances and makes payments" | Context |

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

### Rule: Follow the Dependency

The arrow points from the dependent to the dependency:
- `Web App -> API` (web app depends on API)
- `API -> Database` (API depends on database)
- `User -> Web App` (user depends on web app)

### Rule: Separate Read and Write When It Matters

If reads and writes go through different paths or the distinction matters:
- `API -> Database 'Reads customer records from'`
- `API -> Database 'Writes transaction logs to'`

If not, combine:
- `API -> Database 'Reads from and writes to using SQL'`

### Rule: No Bidirectional Arrows

Never use `<->`. Split into two relationships:

Bad: `Service A <-> Service B`

Good:
- `Service A -> Service B 'Sends order confirmations to'`
- `Service B -> Service A 'Publishes inventory updates to'`

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

## Common Mistakes

1. **Too many relationships.** If every element connects to every other element, your architecture has coupling problems (or your diagram does).
2. **Missing relationships.** Orphaned elements with no connections shouldn't be on the diagram.
3. **Inconsistent granularity.** Don't mix "Makes API calls using JSON/HTTPS" with "Uses" on the same diagram.
4. **Showing infrastructure relationships.** Load balancers, DNS, and network routing are not C4 relationships. Those belong in deployment diagrams.
