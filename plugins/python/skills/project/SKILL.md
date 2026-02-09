---
name: project
description: "This skill should be used when the user asks to \"create a project\", \"scaffold a Python project\", \"initialize a Python project\", \"create a pyproject.toml\", \"set up a Python package\", \"create a CLI tool\", \"create a Python service\", \"create an MCP server\", or mentions Python project scaffolding, project setup, or package initialization."
---

# Python Project Scaffolding

Generate complete Python 3.14+ projects with the **three-layer architecture** (domain/infrastructure/presentation), opinionated tooling (UV, Ruff, mypy, pytest), and a **standard project interface** that works the same locally and in containers.

Every generated project includes:
- **Domain layer** — Pure functions, TypedDict types, no I/O
- **Infrastructure layer** — External system adapters
- **Presentation layer** — CLI (always) + optional MCP server and/or TUI
- **pyproject.toml** — Full config with ruff lint rules, mypy strict, pytest config
- **CLAUDE.md** — Per-project development guide with architecture docs
- **CI** — GitHub Actions workflow via the `github` plugin (lint, format, typecheck, test)
- **Tests** — Basic passing tests for domain operations
- **LICENSE** — MIT

## Standard Commands

Every generated project uses the same commands via `uv run`:

| Command | Purpose |
|---------|---------|
| `uv run pytest` | Run test suite |
| `uv run ruff check .` | Run linter |
| `uv run ruff format .` | Format code |
| `uv run mypy <pkg>/` | Type check |
| `uv run python -m <pkg>.presentation.mcp` | Start MCP server (if MCP enabled) |
| `uv build` | Build package (libraries) |

## Generating a Project

### Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data project_name="<name>" \
  --data description="<description>" \
  --data project_type="<cli|service|library>" \
  --data <options> \
  "${CLAUDE_PLUGIN_ROOT}/skills/project/templates/project/" \
  <target-directory>
```

The template renders a `{{ project_name }}` directory inside `<target-directory>`, so use `.` if you want `./my-project/`.

### Template Options

**Required:**
- `project_name` (str) — Package name (lowercase, hyphens)
- `description` (str) — Short project description

**Optional:**
- `author_name` (str, default: "Bruk Habtu") — Author name
- `python_version` (str, default: "3.14") — Minimum Python version
- `project_type` (str, default: "cli") — "cli", "service", or "library"
- `has_mcp` (bool, default: false) — Add MCP server (shown when project_type != "service")
- `has_tui` (bool, default: false) — Add Textual TUI
- `is_async` (bool, default: false) — Use async infrastructure (shown when MCP enabled)
- `line_length` (int, default: 100) — Ruff line length

**Notes:**
- `project_type=service` automatically enables MCP (no need to set `has_mcp`)
- `project_type=cli` with `has_mcp=true` gives you CLI + MCP server
- `has_tui=true` adds a Textual TUI with a `tui` CLI subcommand

### Examples

**CLI-only tool:**
```bash
uvx copier copy --trust --defaults \
  --data project_name="my-tool" \
  --data description="A useful CLI tool" \
  --data project_type="cli" \
  "${CLAUDE_PLUGIN_ROOT}/skills/project/templates/project/" \
  .
```

**Service (CLI + MCP server):**
```bash
uvx copier copy --trust --defaults \
  --data project_name="my-service" \
  --data description="An MCP service" \
  --data project_type="service" \
  --data is_async=true \
  "${CLAUDE_PLUGIN_ROOT}/skills/project/templates/project/" \
  .
```

**CLI + MCP + TUI:**
```bash
uvx copier copy --trust --defaults \
  --data project_name="my-app" \
  --data description="Full-featured app" \
  --data project_type="cli" \
  --data has_mcp=true \
  --data has_tui=true \
  "${CLAUDE_PLUGIN_ROOT}/skills/project/templates/project/" \
  .
```

### Workflow

1. Determine project name (infer from context or ask)
2. Determine project type from context (MCP mentions → service, package/SDK → library, default → cli)
3. Check if target directory exists — ask before overwriting (add `--overwrite` if confirmed)
4. Run the copier template
5. Generate CI workflow using the github plugin's ci template:
   ```bash
   uvx copier copy --trust --defaults \
     --data language="python" \
     --data package_name="<package_name>" \
     --data python_version="<python_version>" \
     "${CLAUDE_PLUGIN_ROOT}/../github/skills/ci/templates/ci/" \
     <target-directory>/<project_name>
   ```
6. After generation, suggest: `cd <project_name> && uv sync && uv run pytest`

## Generated Project Structure

```
<project_name>/
├── pyproject.toml          # Full config (ruff, mypy, pytest)
├── README.md               # Setup and usage docs
├── CLAUDE.md               # Development guide for Claude
├── LICENSE                  # MIT license
├── .python-version         # Python version
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml          # From github plugin (lint, format, typecheck, test)
├── <package_name>/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── types.py        # TypedDict definitions
│   │   └── operations.py   # Pure functions, business logic
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   └── client.py       # External system adapter
│   └── presentation/
│       ├── __init__.py
│       ├── __main__.py     # Module entry point
│       ├── cli/
│       │   ├── __init__.py
│       │   └── commands.py # Click CLI commands
│       ├── mcp/            # (if MCP enabled)
│       │   ├── __init__.py
│       │   ├── __main__.py # MCP entry point
│       │   ├── server.py   # FastMCP setup + tool registration
│       │   └── tools.py    # Async tools with Annotated params
│       └── tui/            # (if TUI enabled)
│           ├── __init__.py
│           └── app.py      # Textual App scaffold
├── tests/
│   ├── __init__.py
│   └── test_operations.py  # Domain operation tests
├── .claude/
│   └── rules/
│       ├── unit-tests.md        # Unit test boundaries + examples
│       ├── integration-tests.md # Integration test patterns
│       └── e2e-tests.md         # E2E test guidelines
└── .claude-plugin/         # (if MCP enabled)
    ├── plugin.json         # Plugin metadata
    └── mcp.json            # MCP server config
```

## Architecture Principles

- **Domain layer** is pure — no I/O, no side effects, TypedDict for types
- **Infrastructure layer** wraps external systems — HTTP, DB, CLI, filesystem
- **Presentation layer** is thin — delegates to domain, handles I/O formatting
- **Functional over OOP** — prefer pure functions, use classes only when needed
- **Type hints mandatory** — mypy strict mode enforced
- **Flat layout** — `project_name/project_name/` not `project_name/src/project_name/`

## Conventions

These conventions align with the user's global CLAUDE.md preferences:

- **UV** for package management (always)
- **Ruff** with lint rules: E, F, I, N, W, B, C4, UP
- **mypy** strict mode
- **Click** for CLI interfaces
- **FastMCP** for MCP servers
- **Textual** for TUI applications
- **License** defaults to MIT
