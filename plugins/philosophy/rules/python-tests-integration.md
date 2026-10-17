---
paths:
  - "**/tests/integration/**/*.py"
mode: owner
---
# Integration tests

Applies when reading or writing a test under `tests/integration/` in a repository I own.

- An integration test tests the program's own parts working together. It enters
  through a real entry point and runs everything up to the edge of the world for real.
- The world is faked at that edge and nowhere else: processes, files, sockets, the
  clock, networks, databases. Nothing inside the program's own code is mocked or
  patched.
- Doubles are fakes, working stand-ins for the world. The test asserts on the fake's
  state.
- This is the only layer with doubles.
- The integration suite runs twice in one process, to catch state leakage.
- A failing integration test means the parts do not fit or the behaviour is wrong. It
  cannot be the world, because the world was a fake.
