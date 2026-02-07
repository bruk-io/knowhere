---
name: makefile
description: "This skill should be used when the user asks to \"create a Makefile for Rust\", \"scaffold a Rust project\", \"set up a Rust project\", \"initialize a Rust project\", \"add a Makefile\", or mentions Rust project setup, Rust Makefile generation, or Rust project scaffolding."
---

# Rust Project Scaffolding

Generate opinionated `Makefile` files for Rust projects. Generated Makefiles follow the **standard project interface** — a set of conventional target names (`test`, `lint`, `serve`, etc.) that work the same across all projects and align with the Docker entrypoint interface from the containers plugin.

## Standard Project Interface

Every generated `Makefile` includes targets that implement a consistent command interface. These map 1:1 to the Docker entrypoint commands, so `make test` locally and `docker run myapp test` in a container run the same thing.

### Core Targets (all project types)

| Target | Runs | Purpose |
|--------|------|---------|
| `test` | `cargo test` | Run test suite |
| `lint` | `cargo clippy -- -D warnings` | Run clippy |
| `check` | `lint + test` | Run lint + test |

### Service Targets (APIs, web apps, workers)

| Target | Runs | Purpose |
|--------|------|---------|
| `build` | `cargo build --release` | Compile release binary |
| `serve` | `build + ./target/release/<name>` | Start in production mode |
| `dev` | `cargo watch -x run` | Start with hot reload |

### Library Targets (crates, SDKs)

| Target | Runs | Purpose |
|--------|------|---------|
| `build` | `cargo build --release` | Build the library |
| `bench` | `cargo bench` | Run benchmarks |

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

- `app_name` (str, required) — Binary/crate name
- `project_type` (str, default: "service") — "service" or "library"
- `port` (int, default: 8080) — Service port (services only)

### Workflow

1. Detect if `Makefile` already exists — ask before overwriting (add `--overwrite` if confirmed)
2. Infer app name from `Cargo.toml` package name if not provided
3. Determine project type from context
4. Run the copier template
