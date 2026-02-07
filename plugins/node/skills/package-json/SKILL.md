---
name: package-json
description: "This skill should be used when the user asks to \"create a package.json\", \"scaffold a Node project\", \"set up a Node.js package\", \"initialize a TypeScript project\", \"create a new npm package\", or mentions package.json generation, Node.js project setup, or TypeScript project scaffolding."
---

# Node.js Project Scaffolding

Generate opinionated `package.json` files for Node.js/TypeScript projects. Generated projects follow the **standard project interface** — a set of conventional script names (`test`, `lint`, `serve`, etc.) that work the same across all projects and align with the Docker entrypoint interface from the containers plugin.

## Standard Project Interface

Every generated `package.json` includes `"scripts"` that implement a consistent command interface. These map 1:1 to the Docker entrypoint commands, so `npm run test` locally and `docker run myapp test` in a container run the same thing.

### Core Scripts (all project types)

| Script | Runs | Purpose |
|--------|------|---------|
| `test` | `vitest run` | Run test suite |
| `lint` | `eslint .` | Run linter |
| `check` | `lint && test` | Run lint + test |
| `typecheck` | `tsc --noEmit` | Type checking |

### Service Scripts (APIs, web apps, workers)

| Script | Runs | Purpose |
|--------|------|---------|
| `serve` | `node dist/index.js` | Start in production mode |
| `dev` | `tsx watch src/index.ts` | Start with hot reload |

### Library Scripts (packages, SDKs)

| Script | Runs | Purpose |
|--------|------|---------|
| `build` | `tsc` | Compile TypeScript |

## Generating a package.json

### Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data-file ~/.config/copier/defaults.yml \
  --data project_name="<name>" \
  --data project_type="<service|library>" \
  --data <options> \
  "${CLAUDE_PLUGIN_ROOT}/skills/package-json/templates/package-json/" \
  .
```

If `~/.config/copier/defaults.yml` does not exist, omit the `--data-file` flag.

### Template Options

- `project_name` (str, required) — Package name (lowercase, hyphens)
- `description` (str, default: "") — Short project description
- `author_name` (str, default: "") — Author name
- `license` (str, default: "MIT") — License
- `project_type` (str, default: "service") — "service" or "library"
- `package_manager` (str, default: "npm") — npm, pnpm, or yarn
- `node_version` (str, default: "22") — Minimum Node.js version
- `port` (int, default: 3000) — Service port (services only)

### Workflow

1. Detect if `package.json` already exists — ask before overwriting (add `--overwrite` if confirmed)
2. Infer the project name from the directory name if not provided
3. Determine project type from context
4. Run the copier template
5. After generation, run the package manager install and suggest creating `src/index.ts`
