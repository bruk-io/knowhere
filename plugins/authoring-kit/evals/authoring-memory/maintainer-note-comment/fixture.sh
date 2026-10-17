#!/bin/bash
set -e
cat > CLAUDE.md <<'MD'
# tally

CLI that counts lines of code by language.

## Commands

- Build: `pnpm build`
- Test: `pnpm test`
- Lint: `pnpm lint`

## Conventions

- Use pnpm, never npm or yarn.
- Source in `src/`, one module per language parser under `src/langs/`.
- Errors are returned, not thrown, from parser functions.
MD
mkdir -p src/langs
printf 'export const parse = () => [];\n' > src/langs/ts.ts
