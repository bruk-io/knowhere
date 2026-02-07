---
name: dockerfile
description: "This skill should be used when the user asks to \"create a Dockerfile\", \"write a Dockerfile\", \"containerize my app\", \"Dockerize my app\", \"review my Dockerfile\", \"optimize my Dockerfile\", \"add Docker support\", \"set up Docker\", \"multi-stage build\", \"devcontainer\", or mentions Dockerfile generation, container images, or Docker best practices. Covers Python, Node.js, Go, and Rust with multi-target builds for CI, dev containers, and production."
---

# Dockerfile Skill

Generate and review Dockerfiles using multi-target build patterns. Every Dockerfile produced by this skill supports three build targets: **CI** (testing in GitHub Actions), **dev** (development container), and **prod** (minimal deploy artifact). All images expose a **standardized entrypoint interface** — the same commands work regardless of language.

## Standardized Entrypoint Interface

Every generated image uses an `entrypoint.sh` that provides a consistent command interface. The entrypoint is a contract — each project fulfills it through its native tooling (package.json scripts, pyproject.toml, cargo commands, etc.).

### Core Commands (all targets, all project types)

| Command | Purpose | Example usage |
|---------|---------|---------------|
| `test` | Run test suite | `docker run myapp:ci test` |
| `lint` | Run linter | `docker run myapp:ci lint` |
| `check` | Run lint + test | `docker run myapp:ci check` |
| `shell` | Interactive shell | `docker run -it myapp:dev shell` |
| (default) | Pass-through exec | `docker run myapp:ci go vet ./specific/pkg` |

### Service Commands (APIs, web apps, workers)

| Command | Purpose | Available in |
|---------|---------|-------------|
| `serve` | Start in production mode | ci, dev, prod (default in prod) |
| `dev` | Start with hot reload | dev (default in dev) |

### Library Commands (packages, SDKs, CLI tools)

| Command | Purpose | Available in |
|---------|---------|-------------|
| `build` | Build/compile the package | ci, dev |
| `bench` | Run benchmarks (Go, Rust) | ci, dev |

### How Each Language Implements the Interface

| Language | test | lint | serve | dev |
|----------|------|------|-------|-----|
| Python | `pytest` | `ruff check .` | `uvicorn <module>` | `uvicorn --reload` |
| Node | `npm run test` | `npm run lint` | `npm run serve` | `npm run dev` |
| Go | `go test -v -race ./...` | `go vet ./...` | `go run .` | `air` |
| Rust | `cargo test` | `cargo clippy -- -D warnings` | `cargo run --release` | `cargo watch -x run` |

Node delegates entirely to package.json scripts — the project defines the implementation. Python uses direct tool invocation. Go and Rust use idiomatic commands.

**Note:** For compiled languages (Go, Rust), the prod target uses a scratch image with the binary as the entrypoint. The entrypoint interface is available in ci and dev targets only.

## Multi-Target Build Philosophy

A single Dockerfile serves all environments by using named stages selected with `--target`:

| Target | Purpose | Consumer |
|--------|---------|----------|
| `ci` | Tests, linting, type checking | GitHub Actions (`target: ci`) |
| `dev` | Full dev environment with tooling | Devcontainers, local dev |
| `prod` | Minimal runtime image | Deployment (K8s, ECS, Fly, etc.) |

Intermediate stages like `deps` (interpreted languages) or `build` (compiled languages) handle dependency installation and compilation.

## Generating a New Dockerfile

### Using Copier Templates

This skill ships copier templates for four languages. Each template generates a Dockerfile and an `entrypoint.sh`. Run copier with the appropriate template and pass configuration via `--data` flags:

```bash
uvx copier copy --trust --defaults \
  --data-file ~/.config/copier/defaults.yml \
  --data app_name="<name>" \
  --data project_type="<service|library>" \
  --data <lang_specific_options> \
  "${CLAUDE_PLUGIN_ROOT}/skills/dockerfile/templates/<language>/" \
  .
```

If `~/.config/copier/defaults.yml` does not exist, omit the `--data-file` flag.

All templates share these common options:
- `app_name` (str) — Application name
- `port` (int) — Exposed port
- `project_type` (str, default: "service") — "service" or "library", determines entrypoint commands

Language-specific options:

**Python** (`templates/python/`):
- `python_version` (str, default: "3.14") — Python version (major.minor only)
- `app_module` (str, default: "app.main:app") — ASGI module:attribute or module path
- `uses_uv` (bool, default: true) — Use UV for package management

**Node** (`templates/node/`):
- `node_version` (str, default: "22") — Node.js major version
- `package_manager` (str, default: "npm") — npm, pnpm, or yarn
- `has_build_step` (bool, default: true) — Whether the project has a build step

**Go** (`templates/go/`):
- `go_version` (str, default: "1.24") — Go version

**Rust** (`templates/rust/`):
- `rust_version` (str, default: "1.84") — Rust version

### Workflow

1. Detect the project language from existing files (pyproject.toml, package.json, go.mod, Cargo.toml)
2. Infer sensible defaults — app name from project config, port from existing code, project type from context
3. Run the copier template to generate the Dockerfile and entrypoint.sh
4. If a Dockerfile already exists, ask before overwriting (add `--overwrite` if confirmed)
5. Review the generated files and customize for project-specific needs
6. Generate a `.dockerignore` if one does not exist

### Writing Dockerfiles Without Templates

When no template fits (other languages, polyglot projects, or custom needs), follow the multi-target pattern manually and implement the entrypoint interface. Consult `references/best-practices.md` for detailed patterns.

## Reviewing an Existing Dockerfile

When reviewing or optimizing a Dockerfile, check against these criteria:

### Structure
- Has named multi-stage targets (ci, dev, prod)?
- Uses the standardized entrypoint interface?
- Production stage uses minimal base image?
- Build/dependency stages separated from runtime?

### Layer Caching
- Instructions ordered by change frequency (least to most frequent)?
- Package manager caches mounted (`--mount=type=cache`)?
- Lock files copied before source code?
- `.dockerignore` exists and excludes `.git`, `node_modules`, `__pycache__`, etc.?

### Security
- Runs as non-root user in production?
- No secrets baked into image layers?
- Pinned base image versions (no `:latest`)?

For detailed security hardening guidance, consult `references/security.md`.

### Performance
- BuildKit syntax directive present (`# syntax=docker/dockerfile:1`)?
- Combined RUN commands to reduce layers?
- `apt-get` caches cleaned (`rm -rf /var/lib/apt/lists/*`)?
- Compiled binaries stripped (`-ldflags="-s -w"` for Go)?

When reviewing, provide specific findings organized by severity (critical / warning / suggestion) with concrete fixes.

## Additional Resources

### Reference Files

For detailed guidance beyond what is in this skill:
- **`references/best-practices.md`** — Multi-target strategy, layer caching, cache mounts, .dockerignore, image size optimization, CI/devcontainer integration
- **`references/security.md`** — Non-root users, secrets handling, vulnerability scanning, health checks, security checklist

### Copier Templates

Working multi-target Dockerfile templates in `templates/`:
- **`templates/python/`** — Python with UV or pip, generates Dockerfile + entrypoint.sh
- **`templates/node/`** — Node.js with npm/pnpm/yarn, delegates to package.json scripts
- **`templates/go/`** — Go with scratch production image, entrypoint in ci/dev only
- **`templates/rust/`** — Rust with cargo-chef caching, entrypoint in ci/dev only
