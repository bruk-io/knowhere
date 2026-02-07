---
name: pyproject
description: "This skill should be used when the user asks to \"create a pyproject.toml\", \"scaffold a Python project\", \"set up a Python package\", \"initialize a Python project\", \"create a new Python library\", \"create a CLI tool\", \"create a Python service\", or mentions pyproject.toml generation, Python project setup, or Python package scaffolding."
---

# Python Project Scaffolding

Generate opinionated `pyproject.toml` files for Python 3.14+ projects using UV, Ruff, and Hatchling. Generated projects follow the **standard project interface** — a set of conventional script names (`test`, `lint`, `serve`, etc.) that work the same across all projects and align with the Docker entrypoint interface from the containers plugin.

## Standard Project Interface

Every generated `pyproject.toml` includes `[tool.uv.scripts]` that implement a consistent command interface. These map 1:1 to the Docker entrypoint commands from the containers plugin, so `uv run test` locally and `docker run myapp test` in a container run the same thing.

### Core Scripts (all project types)

| Script | Runs | Purpose |
|--------|------|---------|
| `test` | `pytest` | Run test suite |
| `lint` | `ruff check .` | Run linter |
| `check` | `lint && test` | Run lint + test |

### Service Scripts (APIs, web apps, workers)

| Script | Runs | Purpose |
|--------|------|---------|
| `serve` | `uvicorn <module> --host 0.0.0.0 --port <port>` | Start in production mode |
| `dev` | `uvicorn <module> --reload` | Start with hot reload |

### Library Scripts (packages, SDKs)

| Script | Runs | Purpose |
|--------|------|---------|
| `build` | `uv build` | Build the package |

## Generating a pyproject.toml

### Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data-file ~/.config/copier/defaults.yml \
  --data project_name="<name>" \
  --data project_type="<service|library|cli>" \
  --data <options> \
  "${CLAUDE_PLUGIN_ROOT}/skills/pyproject/templates/pyproject-toml/" \
  .
```

If `~/.config/copier/defaults.yml` does not exist, omit the `--data-file` flag.

### Template Options

- `project_name` (str, required) — Package name (lowercase, hyphens)
- `description` (str, default: "") — Short project description
- `author_name` (str, default: "") — Author name
- `author_email` (str, default: "") — Author email
- `python_version` (str, default: "3.14") — Minimum Python version
- `project_type` (str, default: "service") — "service", "library", or "cli"
- `app_module` (str, default: "<pkg>.main:app") — ASGI module:attribute (services only)
- `port` (int, default: 8000) — Service port (services only)
- `cli_command_name` (str, default: project_name) — CLI command name (CLI tools only)
- `license` (str, default: "MIT") — License (MIT, Apache-2.0, GPL-3.0, BSD-3-Clause)
- `line_length` (int, default: 100) — Ruff/Black line length

### Workflow

1. Detect if `pyproject.toml` already exists — ask before overwriting (add `--overwrite` if confirmed)
2. Infer the project name from the directory name if not provided
3. Determine project type from context (API/web mentions → service, package/SDK → library, CLI → cli)
4. Run the copier template
5. After generation, suggest creating the package directory structure:
   - Flat layout: `project_name/__init__.py` (snake_case package directory)
   - If service: also create `project_name/main.py` with ASGI app stub
   - If CLI: also create `project_name/cli.py` with Click boilerplate

## Generated Output

The template produces a `pyproject.toml` with:

- **Project metadata** — name, version, description, authors, license
- **Python 3.14+** minimum requirement
- **Dependencies** — uvicorn for services, Click for CLI tools, empty for libraries
- **Dev dependencies** — pytest, pytest-cov, ruff, mypy
- **UV scripts** — standard project interface (test, lint, check + type-specific scripts)
- **Ruff config** — line length, target version, double quotes, Black-compatible formatting
- **Hatchling** build system with explicit package discovery

## Conventions

These conventions align with the user's global CLAUDE.md preferences:

- **UV** for package management (always)
- **Flat layout** — `project_name/project_name/` not `project_name/src/project_name/`
- **Ruff** with Black profile for formatting
- **Click** for CLI interfaces
- **Type hints** are mandatory
- **License** defaults to MIT
