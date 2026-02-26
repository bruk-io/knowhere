---
name: project-setup
description: "This skill should be used when the user asks to \"create an obsidian plugin\", \"scaffold an obsidian plugin\", \"new obsidian plugin\", \"set up obsidian plugin project\", \"initialize obsidian plugin\", \"start an obsidian plugin\", \"bootstrap obsidian plugin\", \"obsidian plugin template\", \"obsidian plugin boilerplate\", or mentions Obsidian plugin scaffolding, plugin project setup, or starting a new Obsidian plugin from scratch."
---

# Obsidian Plugin Project Setup

Scaffold a new Obsidian plugin project with TypeScript, esbuild, and the official sample plugin structure.

## Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data plugin_id="<id>" \
  --data plugin_name="<Name>" \
  --data description="<description>" \
  --data author="<author>" \
  --data author_url="<url>" \
  --data min_app_version="0.15.0" \
  --data is_desktop_only=false \
  "${CLAUDE_PLUGIN_ROOT}/skills/project-setup/templates/obsidian-plugin/" \
  .
```

### Template Options

- `plugin_id` (str, required) — Unique kebab-case identifier (must match folder name and community-plugins.json entry)
- `plugin_name` (str, required) — Display name shown in Obsidian settings
- `description` (str, default: "") — Short plugin description
- `author` (str, default: "") — Author name
- `author_url` (str, default: "") — Author URL (e.g. GitHub profile)
- `min_app_version` (str, default: "0.15.0") — Minimum Obsidian version required
- `is_desktop_only` (bool, default: false) — Set true if using Node.js or Electron APIs

### Workflow

1. Infer the plugin ID and name from user context if not provided
2. Run the copier template to generate all project files
3. Run `npm install` to install dependencies
4. Suggest cloning into `.obsidian/plugins/<plugin-id>/` inside a dev vault
5. Suggest running `npm run dev` for watch mode after setting up the dev vault
6. Suggest installing the Hot-Reload community plugin for automatic reloading
7. Remind: develop in a separate vault, never the primary vault

## Generated Output

The template produces:

- **`manifest.json`** — Plugin metadata (id, name, version, minAppVersion, author)
- **`versions.json`** — Version compatibility mapping
- **`package.json`** — npm dependencies and scripts (includes `builtin-modules`, `esbuild`, `typescript`, `eslint`)
- **`tsconfig.json`** — TypeScript configuration (strict mode, ES2016 target)
- **`esbuild.config.mjs`** — Build configuration (CJS output, externals for obsidian/electron/codemirror)
- **`version-bump.mjs`** — Version sync script for manifest.json and versions.json (see `publishing` skill)
- **`src/main.ts`** — Plugin entry point with settings handling and a starter command
- **`.eslintrc`** — ESLint config with TypeScript and Obsidian rules
- **`.gitignore`** — Ignores main.js, node_modules, IDE files

## manifest.json Fields

- `id` — Unique kebab-case identifier (must match folder name and community-plugins.json entry)
- `name` — Display name shown in settings
- `version` — Semantic version (must match GitHub release tag)
- `minAppVersion` — Minimum Obsidian version required
- `isDesktopOnly` — Set `true` if using Node.js or Electron APIs

## Development Tips

- Clone into `.obsidian/plugins/<plugin-id>/` inside a dev vault
- Enable community plugins in Settings > Community plugins
- Use `npm run dev` for watch mode (auto-rebuilds on save)
- Reload plugin via Command Palette: "Reload app without saving" or use Hot-Reload plugin
- Use `console.log()` sparingly; prefer `Notice` for user-facing messages
- Run `npm run build` for production builds (minified, no sourcemaps)
