---
name: capture-intent
description: Write a piece of work down as an intent - the problem, who it affects, the outcome wanted, what must not break, and the open questions, in the requester's own terms - as a draft root task. Use when new work is bigger than a handful of tool calls, when asked to put something on the board or to write down what done looks like, or when an alert, a metric, or a review finding needs to become work.
---

# Capture intent

Follows Anthropic's "Capture as intent.md" play. Here the intent is the root task on the
board, not a separate file.

**Understand before doing.** Work is easier when we can say what finished looks like.
If that's hard to write down, that's a signal to investigate first, and the
investigation is worthwhile work in its own right.

At the top of a piece of work, the person who has the problem writes it down in their
own terms. That is the intent. The same things get answered again at each level below
it, down to the plan for a single change.

## Interview first

When someone describes a problem rather than handing over a finished intent, ask the
questions an analyst would ask until the answers are concrete: the scope, the users, the
constraints, and what success looks like. Keep their words; don't translate the problem
into engineering terms. Show them the draft and let them correct it before it goes on
the board.

## What an intent holds

| Part | Where it goes |
|---|---|
| The problem, as the requester sees it | `## Problem` in the description |
| Who and what it touches | `## Affected users and systems` in the description |
| What is true when it is done | Acceptance criteria |
| What must not break | Acceptance criteria, each written so a reviewer can check it |
| What nobody knows yet | `## Open questions` in the description, as unticked checkboxes |

```sh
backlog task create --draft "<title>" --type intent -a "@<person with the problem>" \
  -d "<description>" --ac "<criterion>" --ac "<criterion>"
```

Stop at the draft. Sizing is `philosophy:size-work` and accepting is
`philosophy:accept-work`.

## From a signal

An alert, a breached metric, or a review finding becomes an intent the same way. The
anomaly and its evidence are the problem, the affected systems are named, the proposed
outcome is the acceptance criteria, and whatever the evidence can't settle is an open
question. It waits as a draft for a person to triage, like any other intent.
