# Quick Start

Get up and running with the philosophy plugin.

## What arrives, and when

- **Every session:** the standing constraints, printed at start, with the repository's
  mode. A repository whose origin is one of mine is in owner mode and gets the full
  standard; any other is in guest mode, where its own style governs.
- **The first time a file is touched:** the rule for it. Code design for a source file,
  the Python dialect for a `.py` file, how to choose a test layer for a test file, and
  that layer's own rule for a file under `tests/unit/`, `tests/integration/` or
  `tests/e2e/`.
- **On demand:** one skill per step of the work loop, from `philosophy:capture-intent`
  to `philosophy:learn-from-work`, and `philosophy:python-idioms` for the full dialect.
- **At close:** the `philosophy:reviewer` agent reviews a finished board task as someone
  who did not do the work, and closes it when every acceptance criterion is met.

## Start a piece of work

```
> Write this down as an intent: <the problem, in your own words>
```

Claude drafts the intent as `backlog/intents/<name>.md` in the repository, and the rest of
the loop picks up from there: size and accept it, write a spec for large work, plan its
slices in `backlog/plans/<name>.md`, and derive the Backlog.md tasks from them.
