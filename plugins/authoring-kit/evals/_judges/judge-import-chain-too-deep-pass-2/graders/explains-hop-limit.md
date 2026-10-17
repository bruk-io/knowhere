---
type: llm
---

PASS if the answer says Claude Code follows @imports only to a limited nesting depth (a hop or depth limit; the exact number does not matter) and that docs/ai/errors.md sits beyond that depth in this chain, so it is never loaded, AND recommends flattening the chain so every guide is imported directly from CLAUDE.md or from the index file, or merging the files, rather than keeping one nested inside the next.
FAIL if it blames a path that does not resolve, a syntax problem in the import lines, context size, or the model's attention, or if the proposed fix keeps the same chain depth (such as rewording errors.md or moving the line further down).
