---
name: makefile
description: "This skill should be used when the user asks to \"create a Makefile for Go\", \"scaffold a Go project\", \"set up a Go project\", \"initialize a Go project\", \"add a Makefile\", or mentions Go project setup, Go Makefile generation, or Go project scaffolding."
---

# Go Project Scaffolding

Generate opinionated `Makefile` files for Go projects. Generated Makefiles follow the **standard project interface** — a set of conventional target names (`test`, `lint`, `serve`, etc.) that work the same across all projects and align with the Docker entrypoint interface from the containers plugin.

## Standard Project Interface

Every generated `Makefile` includes targets that implement a consistent command interface. These map 1:1 to the Docker entrypoint commands, so `make test` locally and `docker run myapp test` in a container run the same thing.

### Core Targets (all project types)

| Target | Runs | Purpose |
|--------|------|---------|
| `test` | `go test -v -race ./...` | Run test suite |
| `lint` | `go vet ./...` | Run linter |
| `check` | `lint + test` | Run lint + test |

### Service Targets (APIs, web apps, workers)

| Target | Runs | Purpose |
|--------|------|---------|
| `build` | `go build -ldflags="-s -w"` | Compile the binary |
| `serve` | `build + ./bin/<name>` | Start in production mode |
| `dev` | `air` | Start with hot reload |

### Library Targets (packages, SDKs)

| Target | Runs | Purpose |
|--------|------|---------|
| `build` | `go build ./...` | Compile the library |
| `bench` | `go test -bench=. -benchmem ./...` | Run benchmarks |

## Generating a Makefile

### Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data-file ~/.config/copier/defaults.yml \
  --data app_name="<name>" \
  --data project_type="<service|library>" \
  "${CLAUDE_PLUGIN_ROOT}/skills/makefile/templates/makefile/" \
  .
```

If `~/.config/copier/defaults.yml` does not exist, omit the `--data-file` flag.

### Template Options

- `app_name` (str, required) — Binary name
- `project_type` (str, default: "service") — "service" or "library"
- `port` (int, default: 8080) — Service port (services only)

### Workflow

1. Detect if `Makefile` already exists — ask before overwriting (add `--overwrite` if confirmed)
2. Infer app name from `go.mod` module path if not provided
3. Determine project type from context
4. Run the copier template
