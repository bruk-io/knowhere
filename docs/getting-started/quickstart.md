# Quick Start

Get up and running with the philosophy plugin.

## What arrives, and when

- **Every session and subagent:** the standing constraints, with the repository's
  mode. A repository whose origin is one of mine is in owner mode and gets the full
  standard; any other is in guest mode, where its own style governs.
- **The first time a file is touched:** the rule for it. Code design for a source file,
  the Python dialect for a `.py` file, how to choose a test layer for a test file, and
  that layer's own rule for a file under `tests/unit/`, `tests/integration/` or
  `tests/e2e/`.
- **When you or a workflow run it:** one command per play of the loop,
  `/philosophy:intent`, `/philosophy:spec`, `/philosophy:build` and
  `/philosophy:review`. `philosophy:python-idioms` holds the full dialect, on demand.
- **When an intent, spec or plan is written:** `artefact-check` reports anything out of
  shape.

## Start a piece of work

```
> /philosophy:intent <slug>
```

Claude interviews you, writes `intent/<slug>/intent.md` in your words, and opens it as a
PR. Merging it accepts the intent; the spec, the builds and the reviews follow from
there, each as a PR of its own.
