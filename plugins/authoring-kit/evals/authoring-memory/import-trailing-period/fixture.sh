#!/bin/bash
set -e
mkdir -p docs src
cat > CLAUDE.md <<'MD'
# tally

CLI that counts lines of code by language.

## Commands

- Build: `pnpm build`
- Test: `pnpm test`

Follow the project conventions in @docs/conventions.md.
MD
cat > docs/conventions.md <<'MD'
# Conventions

- Use pnpm, never npm or yarn.
- Errors are returned, not thrown, from parser functions.
- One module per language parser under `src/langs/`.
MD
printf 'export const parse = () => [];\n' > src/index.ts
