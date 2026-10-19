---
name: capture-intent
description: Write a piece of work down as an intent - the problem, who it affects, the outcome wanted, what must not break, and the open questions, in the requester's own terms - as a draft file at backlog/intents/<name>.md. Use when new work is bigger than a handful of tool calls, when asked to put something on the board or to write down what done looks like, or when an alert, a metric, or a review finding needs to become work.
---

# Capture intent

Follows Anthropic's "Capture as intent.md" play. Here the intent is the file
`backlog/intents/<name>.md`, and the tasks that deliver it are tied to it by the name.

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

## Name it

The work gets a name that every file and task in it will share: lowercase words joined
by hyphens, such as `nux-ep2`, not starting like an id (`task-5`) or a `size-` or
`slice-` label. The name is the file name, the label on every task, and how the spec and
the plan are paired with the intent, so pick one that will still make sense in a year.

## What an intent holds

| Part | Where it goes |
|---|---|
| The problem, as the requester sees it | `## Problem` |
| Who and what it touches | `## Affected users and systems` |
| What is true when it is done | `## Done when`, as unticked checkboxes |
| What must not break | `## Done when`, each written so a reviewer can check it |
| What nobody knows yet | `## Open questions`, as unticked checkboxes |

Write it as `backlog/intents/<name>.md`. The frontmatter holds the title, `status: Draft`,
the assignee (the person with the problem) and, once sized, the `size-n` label, because
the intent has no task to hold them. Backlog.md does not manage the folder, so there is
no CLI for it: edit the file by hand. The tasks come later, from the plan, each labelled
with the name (`philosophy:write-plan`). Real files are in
`${CLAUDE_PLUGIN_ROOT}/docs/board-examples.md`.

```markdown
---
title: <title>
status: Draft
assignee:
  - '@<person with the problem>'
---

## Problem
## Affected users and systems
## Done when
- [ ] <criterion>
## Open questions
- [ ] <question>
```

Stop at the draft. Sizing is `philosophy:size-work` and accepting is
`philosophy:accept-work`.

## From a signal

An alert, a breached metric, or a review finding becomes an intent the same way. The
anomaly and its evidence are the problem, the affected systems are named, the proposed
outcome is what it is done when, and whatever the evidence can't settle is an open
question. It waits as a draft for a person to triage, like any other intent.
