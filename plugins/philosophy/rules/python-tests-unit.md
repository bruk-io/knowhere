---
paths:
  - "**/tests/unit/**/*.py"
mode: owner
---
# Unit tests

Applies when reading or writing a test under `tests/unit/` in a repository I own.

- A unit test tests the smallest unit: one function, not a module or a class.
- The function is pure. The test calls it with plain data and checks the value it
  returns.
- Nothing is mocked. Pure functions it calls run for real; mocking them would test the
  mock.
- Time, randomness and anything else from outside arrive as arguments, never by
  patching.
- A unit test that needs a mock says the code is not pure yet. The fix is in the code:
  split the decision out into a pure function and test that.
- A failing unit test means that function's logic is wrong.
