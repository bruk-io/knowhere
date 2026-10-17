#!/bin/bash
set -e
cat > AGENTS.md <<'MD'
# Engineering conventions

- TypeScript strict mode everywhere; no `any`.
- Tests live beside the code as `*.test.ts` and run with `pnpm test`.
- Commit messages follow Conventional Commits.
- Never edit files under `generated/`; regenerate with `pnpm codegen`.
MD
mkdir -p src/billing generated
printf 'export const invoice = () => 1;\n' > src/billing/invoice.ts
