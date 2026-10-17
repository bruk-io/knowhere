---
paths: src/**/*.test.ts
---

# Testing

Applies when editing test files under src/.

Before you add or change a test:

1. Run `npm test -- --findRelatedTests <file>` to see the current state.
2. Read the module under test and list its public exports.
3. Write one `describe` block per export, with the happy path first.
4. Run the tests again and paste the failing output into your reply.
5. Fix the test, not the module, unless the user says otherwise.

Tests use vitest. Never mock the database layer; use the in-memory adapter.
