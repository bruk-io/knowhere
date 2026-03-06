---
globs: ["**/container.likec4", "**/container.c4", "**/containers/**/*.likec4", "**/containers/**/*.c4"]
---

# C4 Level 2: Container Rules

You are editing a Container level file. This level shows the high-level technology decisions and how responsibilities are distributed across deployable units within a system.

## What Is a Container
- An application or a data store — a separately runnable/deployable unit
- A runtime concept: something that needs to be running for the overall software system to work
- Containers are isolated from one another — communication between containers usually crosses a process or network boundary (out-of-process call). This is why container-to-container relationships require technology/protocol labels: there is no shared in-process call.
- Examples: web application, single-page app, API server, database, file system, message queue, serverless function, mobile app, shell script, console application

## What Is NOT a Container
- A Docker container (though it may run in one)
- A class, module, or package (those are components)
- A logical grouping (use views/groups for that)

## What Belongs Here

A container diagram usually includes four types of elements:
1. **People** — users, actors, roles who interact with the system (shown outside the boundary)
2. **Software systems** — external systems the system depends on or that depend on it (shown outside the boundary)
3. **Containers** — the applications and data stores that make up the software system (shown inside the boundary)
4. **Software system boundary** — the box enclosing all containers

Relationships between these elements are also shown, labelled with description and technology/protocol (see Relationship Rules below).

A container diagram also answers: *As a software engineer, where do I write code to add a feature?*

## What Does NOT Belong Here
- Deployment details: cloud environments, servers, Kubernetes clusters, Docker runtime details, load balancers, firewalls, application gateways, failover topology
- These vary across deployment environments (dev vs staging vs production) and belong in deployment diagrams

## Containers vs. External Systems

Not every third-party service you interact with needs to be modelled as a container. Use this rule:
- **Your containers:** Deployable units you build and own — model them as containers inside your system boundary
- **External systems:** Services you use but don't own (Stripe, SendGrid, Auth0, GitHub) — model them as external software systems outside the boundary

An exception: if you own a managed data store (e.g., a hosted PostgreSQL database, an AWS S3 bucket holding your data) that forms an integral part of your system and you have complete control and responsibility for its contents, model it as a container (storage shape) within your system boundary — you own the data even if you don't own the infrastructure.

Services you merely call but don't own — AWS SES, AWS SQS, Confluent Cloud Kafka — remain external software systems regardless of who hosts them.

## Relationship Rules at This Level

Container relationships represent inter-process communication — the interaction crosses a process or network boundary. This is why technology labels are required: they capture meaningful architectural decisions that affect deployment, security, and performance.

Container relationship labels have two components (both required):
- **Description:** what the relationship does — "reads data from", "makes API requests to"
- **Technology:** the primary protocol — "JSON/HTTPS", "gRPC/TLS", "JDBC", "AMQP"

Combined examples:
- Good: "Makes API calls using JSON/HTTPS"
- Good: "Reads from and writes to using JDBC"
- Good: "Publishes order events using Kafka"
- Bad: "Uses" (no description, no technology)
- Bad: "Makes API calls" (missing technology)
- Bad: "JSON/HTTPS" (missing description)

Optionally indicate interaction style using line styles (solid = synchronous, dashed = asynchronous). Note: Brown's own example diagrams use dashed lines for all container relationships regardless of interaction style — solid/dashed for sync/async is a common LikeC4 convention. Either is valid provided the diagram key explains the notation used.

## Technology Annotations
- Every container must have a `technology` property — technology decisions are architectural decisions
- Every container must include a description summarising its responsibilities (for applications) or what data it stores (for data stores)
- Use `icon tech:<name>` for visual clarity
- Use appropriate shapes: `storage` for databases and object stores, `queue` for message queues, `browser` for web apps and single-page apps, `mobile` for mobile apps

## Design-Time Use

Container diagrams are also valuable during up-front design. Adding technology choices forces a reality check: a design showing a UI querying a database may seem fine until you annotate "React" and "MySQL" and realise the browser cannot connect directly to the database. Technology annotations are what make this check possible — they are not optional.

## Audience

Container diagrams are reasonably technical. The primary audience is software architects and engineers building or maintaining the software. Container diagrams are also useful for: operations and support staff who need to understand what they are running (the container diagram bridges the Dev/Ops gap — best paired with deployment diagrams); QA engineers performing technical testing; compliance teams and architecture review boards conducting risk reviews or threat modelling; and non-technical product owners verifying which containers are affected by a planned feature.

Multiple versions of a container diagram may be appropriate for different audiences.

## Continuity with Level 1

The people and external systems from the system context diagram must reappear on the container diagram. This is the continuity principle: each level is a more detailed version of the same story. An actor or external system that appears at Level 1 but vanishes at Level 2 breaks the hierarchical reading thread.

Also maintain naming consistency: a system called "Payments Service" at Level 1 must appear with that same name at Level 2. Renaming elements between levels creates ambiguity about whether they represent the same thing.

## Diagram Key

Every container diagram must include a key or legend explaining shapes, colors, and line styles used. Without a key, readers cannot interpret what the visual elements mean, especially in teams where not everyone is familiar with the notation.

## Decomposition Check
- If a container has complex internals, create a `components/` subdirectory
- If a container is simple (e.g., a database), no further decomposition is needed
- As a rough heuristic, most systems have fewer than 15 containers. If you have significantly more, consider whether the system should be split — but treat this as a conversation starter, not a hard rule.
