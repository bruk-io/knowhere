---
name: pages
description: "This skill should be used when the user asks to \"deploy to GitHub Pages\", \"set up GitHub Pages\", \"add pages deployment\", \"create a pages workflow\", \"deploy docs to GitHub Pages\", \"set up site deployment\", or mentions GitHub Pages deployment, static site deployment, or documentation hosting on GitHub Pages."
---

# GitHub Pages Deployment

Generate GitHub Actions workflows for deploying to GitHub Pages. Supports MkDocs (Material) and static HTML sites using the modern Pages artifact-based deployment (no `gh-pages` branch needed).

## Generating a Pages Workflow

### Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data framework="<mkdocs|static>" \
  --data <options> \
  "${CLAUDE_PLUGIN_ROOT}/skills/pages/templates/pages/" \
  <target-directory>
```

The template renders a `.github/workflows/pages.yml` file inside `<target-directory>`.

### Template Options

**Required:**
- `framework` (str) — `mkdocs` or `static`

**Optional (all frameworks):**
- `build_output_dir` (str, default: "site") — Directory containing built files
- `deploy_branch` (str, default: "main") — Branch that triggers deployment

**MkDocs-specific:**
- `python_version` (str, default: "3.14") — Python version for the build

**Static-specific:**
- `build_command` (str, default: "") — Custom build command (if any)

### Examples

**MkDocs (Material) site:**
```bash
uvx copier copy --trust --defaults \
  --data framework="mkdocs" \
  "${CLAUDE_PLUGIN_ROOT}/skills/pages/templates/pages/" \
  .
```

**Static HTML (pre-built):**
```bash
uvx copier copy --trust --defaults \
  --data framework="static" \
  --data build_output_dir="dist" \
  "${CLAUDE_PLUGIN_ROOT}/skills/pages/templates/pages/" \
  .
```

**Static with build step:**
```bash
uvx copier copy --trust --defaults \
  --data framework="static" \
  --data build_command="npm run build" \
  --data build_output_dir="dist" \
  "${CLAUDE_PLUGIN_ROOT}/skills/pages/templates/pages/" \
  .
```

### Cross-Plugin Usage

Other plugins can reference this template for Pages deployment:

```bash
uvx copier copy --trust --defaults \
  --data framework="mkdocs" \
  "${CLAUDE_PLUGIN_ROOT}/../github/skills/pages/templates/pages/" \
  <target-directory>
```

### Workflow

1. Determine the framework — if `mkdocs.yml` exists, use `mkdocs`; otherwise `static`
2. Gather options (build_output_dir, deploy_branch, etc.)
3. Check if `.github/workflows/pages.yml` already exists — ask before overwriting (add `--overwrite` if confirmed)
4. Run the copier template
5. Remind the user to enable GitHub Pages in repo settings: **Settings > Pages > Source: GitHub Actions**

## Generated Workflow

The workflow uses the modern artifact-based Pages deployment:

1. **Build job** — Checks out code, builds the site, uploads artifact
2. **Deploy job** — Downloads artifact and deploys to GitHub Pages

Key features:
- Triggers on push to the deploy branch and manual `workflow_dispatch`
- Uses `concurrency` to prevent parallel deployments
- Requires `pages: write` and `id-token: write` permissions
- No `gh-pages` branch — uses `actions/upload-pages-artifact` and `actions/deploy-pages`

## Prerequisites

The repository must have GitHub Pages enabled with **Source: GitHub Actions**:
1. Go to **Settings > Pages**
2. Under **Source**, select **GitHub Actions**
