---
paths:
  - "**/tests/e2e/**/*.py"
mode: owner
---
# End-to-end tests

Applies when reading or writing a test under `tests/e2e/` in a repository I own.

- An end-to-end test runs against the real world, with nothing faked and nothing
  patched.
- It is either the whole program, driven from its entry point as its user would, or one
  gateway against the real thing it wraps.
- It runs only where the real thing exists. Anywhere else it is reported as not run,
  never counted as a pass.
- A failing end-to-end test means a promise does not hold on this host: the code is
  wrong, or the world changed under it.
