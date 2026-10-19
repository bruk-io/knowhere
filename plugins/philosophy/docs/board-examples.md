# Board examples

One piece of work, `claims-status`, as it sits on a board. Its intent, spec and plan are
files named alike in three folders, and its tasks are Backlog.md tasks labelled with the
same name. The tasks are as Backlog.md 1.53.0 wrote them. The intent, spec and plan are
plain markdown: Backlog.md does not manage `intents/`, `specs/` or `plans/`, so they get
no ids and no CLI, and it never rewrites them. The plugin's tests run `board-check`
against these files, so they stay in step with it.

```
backlog/
  intents/claims-status.md     the problem and when it is done
  specs/claims-status.md       the requirements, numbered
  plans/claims-status.md       the slices, in the order they land
  tasks/                       task-1 ... labelled claims-status and slice-n
  decisions/                   decision-1
```

The draft is not ready to accept: `board-check ready claims-status` reports its open
question until it is ticked, or carried forward with a reason as the spec does.

## An intent, before anyone has accepted it

`backlog/intents/claims-status.md`. The frontmatter is the only structured part: the
status, the size label and the assignee are read from it, because the intent has no task
to hold them.

```markdown
---
title: Claims status self-service
status: Draft
assignee:
  - '@j.ortiz'
labels:
  - size-5
---

## Problem
Customers phone the contact centre to ask where their claim is. Handlers spend roughly a third of call time on status-only queries.

## Affected users and systems
Customers, claims handlers, the portal team, the claims-core API.

## Done when
- [ ] Customers see claim status, next step and expected date in the portal
- [ ] No new PII in the portal session
- [ ] Existing authentication only

## Open questions
- [ ] Do third-party loss adjusters need access too?
```

## The same intent once accepted

Frontmatter only; the body is unchanged. Accepting is a commit that changes `status`
from `Draft` to `To Do`.

```markdown
---
title: Claims status self-service
status: To Do
assignee:
  - '@j.ortiz'
labels:
  - size-5
---
```

## The spec

`backlog/specs/claims-status.md`. The name pairs it with the intent. There is no `Intent:`
line and no link from the intent.

```markdown
---
title: 'Spec: Claims status self-service'
---

## Requirements

- R1. A signed-in customer sees each open claim's status, its next step, and the expected date of that step.
- R2. The customer can list all of their open claims at once.
- R3. The portal session holds no PII beyond what it holds today.

## Policies applied

- Security: existing authentication only, so no new login path.

## Areas of concern

- None yet.

## Open questions

- [ ] Do third-party loss adjusters need access too? Carried forward: not needed for R1-R3.

## Design questions

- How the portal stays under the claims-core rate limit: TASK-1.

## Out of scope

- Notifying customers when a status changes.
```

## The plan

`backlog/plans/claims-status.md`. The slices, in the order they land, and what each depends
on. The tasks are derived from it, and each names its slice with a `slice-n` label.

```markdown
---
title: 'Plan: Claims status self-service'
---

## Slices

1. **One claim.** A customer opens a claim and sees its status, next step and expected date.
   Tester sees: the three fields for a claim in each of its four states.
   Depends on: none.
2. **All open claims.** A customer lists every open claim.
   Tester sees: a customer with three open claims sees all three, newest first.
   Depends on: slice 1.
```

## A design task in the work

`backlog/tasks/`. The `claims-status` label puts it in the work, `slice-1` names the slice
it comes from, and `references` points at the decision and, for a reader, at the intent.

```markdown
---
id: TASK-1
title: Decide how the portal stays under the claims-core rate limit
status: To Do
assignee: []
created_date: '2026-10-09 20:55'
labels:
  - size-2
  - claims-status
  - slice-1
dependencies: []
references:
  - backlog/intents/claims-status.md
  - backlog/decisions/decision-1 - Cache-claim-status-in-the-portal.md
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
id: TASK-2
title: Status endpoint behind existing auth
status: To Do
assignee: []
created_date: '2026-10-09 20:55'
updated_date: '2026-10-09 20:55'
labels:
  - size-3
  - claims-status
  - slice-1
dependencies:
  - TASK-1
references:
  - backlog/intents/claims-status.md
modified_files:
  - claims-api/routes/status.py
  - claims-api/tests/test_status.py
type: task
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 test_status.py covers the four claim states (R1, R3)
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

## A leaf for the second slice

```markdown
---
id: TASK-3
title: List a customer's open claims
status: To Do
assignee: []
created_date: '2026-10-09 20:55'
labels:
  - size-2
  - claims-status
  - slice-2
dependencies:
  - TASK-2
references:
  - backlog/intents/claims-status.md
type: task
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A customer with three open claims sees all three (R2)
<!-- AC:END -->
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
