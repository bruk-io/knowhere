# Board examples

Files from a scratch board on Backlog.md 1.53.0, as the tool wrote them. They show one
intent with its spec, a design task, and a leaf under it. The plugin's tests run
`board-check` against these files, so they stay in step with it.

The draft is not ready to accept: `board-check ready` reports its open question until it
is ticked, or carried forward with a reason as the spec does.

## An intent, before anyone has accepted it

In `backlog/drafts/`.

```markdown
---
id: DRAFT-1
title: Claims status self-service
status: Draft
assignee:
  - '@j.ortiz'
created_date: '2026-10-09 20:55'
labels:
  - size-5
dependencies: []
type: intent
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem
Customers phone the contact centre to ask where their claim is. Handlers spend roughly a third of call time on status-only queries.

## Affected users and systems
Customers, claims handlers, the portal team, the claims-core API.

## Open questions
- [ ] Do third-party loss adjusters need access too?
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Customers see claim status, next step and expected date in the portal
- [ ] #2 No new PII in the portal session
- [ ] #3 Existing authentication only
<!-- AC:END -->
```

## The same intent once accepted and linked to its spec

Frontmatter only; the body is unchanged.

```markdown
---
id: TASK-1
title: Claims status self-service
status: To Do
assignee:
  - '@j.ortiz'
created_date: '2026-10-09 20:55'
updated_date: '2026-10-14 15:00'
labels:
  - size-5
dependencies: []
documentation:
  - backlog/docs/specs/doc-1 - Spec-Claims-status-self-service.md
type: intent
---
```

## The spec

In `backlog/docs/specs/`.

```markdown
---
id: doc-1
title: 'Spec: Claims status self-service'
type: specification
created_date: '2026-10-14 15:00'
updated_date: '2026-10-14 15:00'
---
Intent: TASK-1

## Requirements

- R1. A signed-in customer sees each open claim's status, its next step, and the expected date of that step.
- R2. The status shown is no more than 15 minutes old.
- R3. The portal session holds no PII beyond what it holds today.

## Policies applied

- Security: existing authentication only, so no new login path.

## Areas of concern

- None yet.

## Open questions

- [ ] Do third-party loss adjusters need access too? Carried forward: not needed for R1-R3.

## Design questions

- How the portal stays under the claims-core rate limit: TASK-1.1.

## Out of scope

- Notifying customers when a status changes.
```

## A design task under the intent, pointing at its decision

```markdown
---
id: TASK-1.1
title: Decide how the portal stays under the claims-core rate limit
status: To Do
assignee: []
created_date: '2026-10-09 20:55'
labels:
  - size-2
dependencies: []
references:
  - backlog/decisions/decision-1 - Cache-claim-status-in-the-portal.md
parent_task_id: TASK-1
type: design
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Decision recorded
<!-- AC:END -->
```

## A leaf with its plan, blocked on the design task

```markdown
---
id: TASK-1.2
title: Status endpoint behind existing auth
status: To Do
assignee: []
created_date: '2026-10-09 20:55'
updated_date: '2026-10-09 20:55'
labels:
  - size-3
dependencies:
  - TASK-1.1
modified_files:
  - claims-api/routes/status.py
  - claims-api/tests/test_status.py
parent_task_id: TASK-1
type: task
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 test_status.py covers the four claim states (R1)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Add the status endpoint behind existing auth (R1, R3).
2. Cache responses per the decision.

### Risks
The claims-core API rate-limits at 50 rps.

### Proof
test_status.py covers the four claim states.
<!-- SECTION:PLAN:END -->
```

## The decision the design task delivers

```markdown
---
id: decision-1
title: Cache claim status in the portal
date: '2026-10-09 20:55'
status: proposed
---
## Context



## Decision



## Consequences
```
