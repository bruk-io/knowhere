---
paths:
  - "**/tests/**/*.py"
  - "**/test/**/*.py"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/conftest.py"
mode: owner
---
# Python tests

Applies when reading or writing Python tests in a repository I own.

## Three layers, defined by where the mocks start

A test's layer is the directory it lives in. Each layer has its own rule, which arrives
the first time a file in that directory is touched.

- `tests/unit/`: one pure function. Nothing is mocked.
- `tests/integration/`: the program's own parts together, with the world faked at its
  edge and nowhere else. The only layer with doubles.
- `tests/e2e/`: the real world, with nothing faked.
- "Functional test" and "adapter test" are retired terms.

## Order

- Work outside-in.
- Test shells lightly.
- How hard a test is to write says something about the code. When a test needs a page
  of setup and a stack of mocks, the code made that choice at writing time.
