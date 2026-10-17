#!/bin/bash
set -e
mkdir -p docs/ai src
cat > CLAUDE.md <<'MD'
# shop-api

Node service for the storefront.

## Commands

- Test: `pnpm test`
- Lint: `pnpm lint`

## Guidelines

@docs/ai/index.md
MD
cat > docs/ai/index.md <<'MD'
# Guidelines index

- Use TypeScript strict mode.

@backend.md
MD
cat > docs/ai/backend.md <<'MD'
# Backend guide

- Services live in `src/services/`, one per domain.

@api.md
MD
cat > docs/ai/api.md <<'MD'
# API guide

- Every route validates its input with zod before touching a service.

@handlers.md
MD
cat > docs/ai/handlers.md <<'MD'
# Handler guide

- Handlers return a Result; they never send the response themselves.

@errors.md
MD
cat > docs/ai/errors.md <<'MD'
# Error handling

- Never swallow errors: every catch block rethrows, returns an Err, or logs with the request id.
MD
printf 'export const app = {};\n' > src/index.ts
