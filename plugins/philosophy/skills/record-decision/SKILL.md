---
name: record-decision
description: Answer a design question on the board as a decision, worked out with the engineers who will build it and written down as a Backlog.md decision record. Use when an intent or task on the board has a blocking design question, or when choosing between approaches for work on the board.
---

# Record a decision

Follows the design half of Anthropic's "Requirements and design" play. The play has an
agent write requirements and design into one spec for a product owner to approve. Here
the requirements are `philosophy:write-spec`, and design stays with the engineers who
will build it. It is a task like any other, and what it delivers is the decision.

## The task

Create a design task in the work (`type: design`) with the question as its title and
"Decision recorded" as an acceptance criterion. It carries the work's name as a label and
the `slice-n` label of the slice it unblocks (`philosophy:write-plan`). It goes through
the same loop as any other task.

## The decision

- Write it with `backlog decision create`: the context, the decision, and its
  consequences. Point the design task at it through `references`.
- Apply the organisation's policies while deciding, such as security, compliance, and
  UX. Where two policies conflict or one can't be met, record it on the task as an area
  of concern for the policy owner. Don't settle a policy conflict by choosing a side.
- The decision stays `proposed` until the people who own it accept it.

## Back on the intent

A decision answers open questions in `backlog/intents/<name>.md`. Tick each one it
answers in the file, and note any it leaves open.
