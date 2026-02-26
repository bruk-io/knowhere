---
name: docs
description: "This skill should be used when the user asks to \"create documentation\", \"set up MkDocs\", \"scaffold docs\", \"add project docs\", \"create a docs site\", \"set up mkdocs-material\", \"add API documentation\", \"create mkdocs.yml\", or mentions MkDocs setup, documentation scaffolding, or mkdocs-material configuration for Python projects."
---

# MkDocs Material Documentation Scaffolding

Generate complete MkDocs Material documentation sites for Python projects. Includes theme configuration, navigation, markdown extensions, and optional API reference (mkdocstrings) and blog support.

## Generating a Docs Site

### Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data project_name="<name>" \
  --data description="<description>" \
  --data <options> \
  "${CLAUDE_PLUGIN_ROOT}/skills/docs/templates/docs/" \
  <target-directory>
```

The template renders `mkdocs.yml`, `pyproject.toml`, and a `docs/` directory inside `<target-directory>`.

### Template Options

**Required:**
- `project_name` (str) — Project name (used in site title)

**Optional:**
- `description` (str, default: "") — Short project description
- `repo_url` (str, default: "") — GitHub repo URL (enables edit links)
- `author` (str, default: "Bruk Habtu") — Author name
- `nav_style` (str, default: "tabs") — `tabs` or `sections`
- `enable_blog` (bool, default: false) — Enable blog plugin
- `enable_api_docs` (bool, default: false) — Enable mkdocstrings API reference
- `package_name` (str) — Python package name for API docs (required when `enable_api_docs=true`)

### Examples

**Basic docs site:**
```bash
uvx copier copy --trust --defaults \
  --data project_name="my-tool" \
  --data description="A useful CLI tool" \
  "${CLAUDE_PLUGIN_ROOT}/skills/docs/templates/docs/" \
  .
```

**Docs with API reference:**
```bash
uvx copier copy --trust --defaults \
  --data project_name="my-library" \
  --data description="A Python library" \
  --data repo_url="https://github.com/bruk-io/my-library" \
  --data enable_api_docs=true \
  --data package_name="my_library" \
  "${CLAUDE_PLUGIN_ROOT}/skills/docs/templates/docs/" \
  .
```

**Docs with blog:**
```bash
uvx copier copy --trust --defaults \
  --data project_name="my-project" \
  --data description="Project with blog" \
  --data enable_blog=true \
  "${CLAUDE_PLUGIN_ROOT}/skills/docs/templates/docs/" \
  .
```

### Cross-Plugin Usage

Other plugins can reference this template:

```bash
uvx copier copy --trust --defaults \
  --data project_name="my-pkg" \
  --data description="Package docs" \
  "${CLAUDE_PLUGIN_ROOT}/../mkdocs/skills/docs/templates/docs/" \
  <target-directory>
```

### Workflow

1. Determine project name (infer from `pyproject.toml`, `package.json`, or ask)
2. Check if `mkdocs.yml` already exists — ask before overwriting (add `--overwrite` if confirmed)
3. Run the copier template
4. If this is a standalone docs site (not inside an existing Python project):
   - Run `uv sync` to install docs dependencies
5. Generate GitHub Pages deployment using the github plugin's pages template:
   ```bash
   uvx copier copy --trust --defaults \
     --data framework="mkdocs" \
     "${CLAUDE_PLUGIN_ROOT}/../github/skills/pages/templates/pages/" \
     <target-directory>
   ```
6. Verify with `uv run mkdocs serve` for local preview

## Generated Structure

```
<target-directory>/
├── mkdocs.yml              # MkDocs Material configuration
├── pyproject.toml           # Docs dependencies (mkdocs-material, etc.)
├── docs/
│   ├── index.md             # Home page
│   ├── getting-started/
│   │   ├── installation.md  # Installation guide
│   │   └── quickstart.md    # Quick start guide
│   ├── api/                 # (if API docs enabled)
│   │   └── index.md         # mkdocstrings entry point
│   └── blog/                # (if blog enabled)
│       └── index.md         # Blog index
```

## Local Development

```bash
uv sync                     # Install dependencies
uv run mkdocs serve          # Start dev server at http://127.0.0.1:8000
uv run mkdocs build --strict # Build for production
```

## Standalone vs Integrated

**Standalone docs site** (separate from the Python project):
- The template generates its own `pyproject.toml` with docs dependencies
- Run `uv sync` in the docs directory

**Integrated into existing Python project:**
- Add docs dependencies to the existing `pyproject.toml` under `[project.optional-dependencies]`:
  ```toml
  [project.optional-dependencies]
  docs = [
      "mkdocs-material>=9.6",
      "mkdocstrings[python]>=0.29",
  ]
  ```
- Delete the generated `pyproject.toml` from the docs template
- Run `uv sync --extra docs`

## Theme Features

The generated configuration includes:
- **Light/dark mode** toggle
- **Code highlighting** with copy button and annotations
- **Tabbed content** support
- **Admonitions** (note, warning, tip, etc.)
- **Search** with suggestions and highlighting
- **Navigation tabs** or expandable sections
- **Edit on GitHub** links (when repo_url provided)
