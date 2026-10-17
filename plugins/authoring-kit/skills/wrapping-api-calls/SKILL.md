---
name: wrapping-api-calls
description: 'Use when a tool, skill or agent needs a guarantee a prompt cannot give: output that is always valid JSON, answers that cite exactly where they came from, thousands of items processed cheaply overnight, or an exact token count. Claude reaches for prompt wording where only an Anthropic API feature gives the guarantee, so load this before building or advising on anything that needs guaranteed output shape, citations, bulk processing or token counts.'
---

# Leveraging the Anthropic API

This picks up where the **choosing-extension-types** skill bottoms out. That gate pushes work *up*
toward deterministic code; this skill handles the case where the model genuinely
*is* the escalation - it must answer, extract, or generate. Even there - the
weakest cell of the two-axes table in [`choosing-extension-types/references/minimizing-model-work.md`](../choosing-extension-types/references/minimizing-model-work.md) - you don't settle for best-effort prompting:
the API can enforce a property on the model's output.

## The constraint: the harness owns the request

Claude Code is a *consumer* of the Messages API, and the harness controls every
request it sends: there's no knob to set `citations` on the documents a session
reads, constrain an interactive turn to a schema, or turn it into a batch. The one
exception is headless: `claude -p --json-schema '<schema>'` returns validated JSON
for a whole print-mode run, so when the "tool" can be a nested `claude -p` call,
try that before hand-rolling an API client.

## The bridge: wrap the API call as a tool

Make the API call yourself, inside a tool the agent invokes: a small local CLI
sends a Messages request with the feature enabled and returns a structured result;
the outer session calls it like any tool, and the guarantee lives in the sub-call.
Because you own that inner request, wrapping buys everything else it controls too -
a cheap model for a classification step, `temperature`, a tight system prompt,
thinking and effort settings, cache breakpoints.

Build it to the tool conventions in [`choosing-extension-types/references/minimizing-model-work.md`](../choosing-extension-types/references/minimizing-model-work.md), "Designing tools the model calls".

## The catalog

| Capability | What it gives you | Reach for it when |
|---|---|---|
| **Citations** | Claims grounded to exact source spans; won't cite sources you didn't provide | The agent must answer from documents and you need verifiable receipts |
| **Search-result grounding** | The same span-level citations for content a tool fetches | Dynamic RAG - your tool retrieves, then answers with attribution |
| **Structured outputs** | Output constrained to a JSON schema by grammar - schema-valid unless the model refuses or hits `max_tokens` | You feed model output into code and can't tolerate malformed JSON |
| **Message Batches** | Many independent prompts processed async at 50% of standard price | Bulk/offline work - transforming thousands of items, not an interactive turn |
| **Token counting** | A free, close estimate of a request's input tokens before sending | Cost estimates or budget gates around model calls |

## When not to reach for the API

Only when **the model must be involved *and* you need a property enforced on its
output.** If local code or the model's native ability already does the job,
wrapping a call just adds a network hop, latency, cost, and another moving part.
Don't cite a task that consumes no documents, don't force a schema where free text
is fine, don't batch an interactive turn. Same discipline as everywhere else in
the toolkit: the most structural mechanism the situation needs, and no more.

## Per-feature detail

What each feature guarantees, what it cannot be combined with, the worked `cite`
CLI, and the doc links are in [references/wrapping-api-calls.md](references/wrapping-api-calls.md).
Parameters live in the linked docs, not here - the API moves quickly.
