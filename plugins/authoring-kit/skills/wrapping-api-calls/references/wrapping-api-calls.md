# Anthropic API features - reference

Behind [SKILL.md](../SKILL.md), for when you're wiring one of these up: what each
feature guarantees, what breaks it, and where its parameters are documented. The
API moves quickly, so request shapes are left to the linked docs (checked
2026-10-09).

## Where this sits on the two axes

Authoring-foundations' rule (`references/minimizing-model-work.md`, "Two axes, not
a ladder") is to prefer the mechanism that makes a property structural over the
one that coaxes it. Between enforcement around the model and the model interpreting
prose sits **model output with a platform-enforced guarantee** - this file. The
bridge (a tool wrapping the call) is the model-orchestrates-code square; the
*payload* is a model call you can trust the shape of.

## Citations - the worked example

**Guarantees** claims grounded to specific spans of the documents you sent, and
never a citation to a document or location you didn't provide ("citations are
guaranteed to contain valid pointers to the provided documents"). In Anthropic's
evaluations it is also significantly more likely to cite the most relevant quotes
than prompt-based "please cite". The agent gets grounding it can trust, not
grounding it must re-verify.

The wrap is a `cite` CLI:

- **Input:** a question plus source paths (or stdin).
- **Body:** sends each source as a `document` block with citations enabled, in its own Messages call.
- **Output (JSON to stdout):** `{ "answer": "...", "citations": [ { "claim": "...", "cited_text": "...", "source": "...", "location": {...} } ] }` - bounded by default, `--full` for everything, plus `--help` and `cite claudemd`.

The outer session calls `cite "<question>" report.pdf notes.md` whenever it needs an auditable, source-grounded answer.

**Gotchas:** text only - image citations aren't supported, so a scanned PDF with no extractable text isn't citable. And citations **cannot** be combined with structured outputs: the request returns a 400, since interleaved citation blocks conflict with a strict schema. So `cite` builds its JSON envelope in code from the returned citation blocks, not by asking the model for JSON.

## Structured outputs

**Guarantees** schema-valid JSON: the schema is compiled into a grammar that
restricts token generation. Two combinable modes - JSON outputs govern the response
shape, strict tool use validates the model's *tool inputs*. The guarantee is about
*shape, not correctness*: the model can still be wrong, just never malformed.

**Gotchas:**

- Incompatible with citations (400) and with message prefilling.
- Two cases still break the shape, so check `stop_reason` before parsing: `refusal` and `max_tokens` (truncated output).
- Enum/const string casing is not guaranteed - compare case-insensitively.
- The grammar has limits (no recursive schemas, a complexity ceiling across strict schemas - "Schema is too complex for compilation"); the docs list them.
- The first use of a schema pays grammar-compilation latency, and the injected format description adds input tokens the docs give no figure for - measure with token counting if it matters.
- The older top-level `output_format` request parameter is deprecated; the GA path is `output_config.format`.

## Search-result grounding

**Guarantees** the same citations for content *your tool* returns at call time -
the dynamic-RAG shape: the tool hits a vector store or internal API, returns
search-result blocks, and the answer comes back attributed. Use it instead of the
document form when retrieval happens at tool-call time rather than ahead of time.

**Gotcha:** it cites whole text blocks, never substrings - split content into
smaller blocks for finer granularity.

## Message Batches and token counting

**Message Batches** process many *independent* requests asynchronously at 50% of
standard prices. Right when the job is "process this whole corpus cheaply" -
classify or transform thousands of files, backfill, large eval runs - and wrong for
an interactive turn (no `stream`). Wrap a script the agent kicks off and polls.

**Token counting** returns a request's input token count before you send it, free.
**Gotchas:** it is an estimate - the real count may differ by a small amount - and
counts are per model, so count against the model you will call.

## Sources

- [Citations](https://platform.claude.com/docs/en/build-with-claude/citations) - grounding answers in source spans; [launch post](https://claude.com/resources/articles/introducing-citations-api)
- [Search results](https://platform.claude.com/docs/en/build-with-claude/search-results) - citations for tool-returned / RAG content
- [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) - schema-constrained JSON and strict tool use
- [Batch processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing) - the Message Batches API
- [Token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)
- Index of every API doc page: <https://platform.claude.com/llms.txt>
