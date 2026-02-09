---
name: ci
description: "This skill should be used when the user asks to \"create a CI workflow\", \"set up CI\", \"add GitHub Actions\", \"create a CI pipeline\", \"add CI/CD\", \"set up GitHub Actions CI\", \"create a test workflow\", \"add linting to CI\", or mentions CI workflow generation, GitHub Actions setup, or continuous integration configuration."
---

# GitHub CI Workflow Generation

Generate language-specific GitHub Actions CI workflows for **Python**, **Node.js**, **Go**, and **Rust** projects. Each workflow includes setup, dependency install, linting, formatting/type checks, and tests.

## Generating a CI Workflow

### Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data language="<python|node|go|rust>" \
  --data <language-specific-options> \
  "${CLAUDE_PLUGIN_ROOT}/skills/ci/templates/ci/" \
  <target-directory>
```

The template renders a `.github/workflows/ci.yml` file inside `<target-directory>`.

### Template Options

**Required:**
- `language` (str) — `python`, `node`, `go`, or `rust`

**Optional (all languages):**
- `project_type` (str, default: "cli") — `cli`, `service`, or `library`

**Python-specific:**
- `package_name` (str, required) — Python package name in snake_case (used as mypy target)
- `python_version` (str, default: "3.14") — Python version

**Node.js-specific:**
- `node_version` (str, default: "22") — Node.js major version
- `package_manager` (str, default: "npm") — `npm`, `pnpm`, or `yarn`

**Go-specific:**
- `go_version` (str, default: "1.24") — Go version

**Rust:** No additional options needed.

### Examples

**Python CI:**
```bash
uvx copier copy --trust --defaults \
  --data language="python" \
  --data package_name="my_tool" \
  --data python_version="3.14" \
  "${CLAUDE_PLUGIN_ROOT}/skills/ci/templates/ci/" \
  .
```

**Node.js CI (pnpm):**
```bash
uvx copier copy --trust --defaults \
  --data language="node" \
  --data node_version="22" \
  --data package_manager="pnpm" \
  "${CLAUDE_PLUGIN_ROOT}/skills/ci/templates/ci/" \
  .
```

**Go CI:**
```bash
uvx copier copy --trust --defaults \
  --data language="go" \
  --data go_version="1.24" \
  "${CLAUDE_PLUGIN_ROOT}/skills/ci/templates/ci/" \
  .
```

**Rust CI:**
```bash
uvx copier copy --trust --defaults \
  --data language="rust" \
  "${CLAUDE_PLUGIN_ROOT}/skills/ci/templates/ci/" \
  .
```

### Cross-Plugin Usage

Other plugins can reference this template for CI generation:

```bash
uvx copier copy --trust --defaults \
  --data language="python" \
  --data package_name="my_pkg" \
  "${CLAUDE_PLUGIN_ROOT}/../github/skills/ci/templates/ci/" \
  <target-directory>
```

### Workflow

1. Determine the project language (infer from context — pyproject.toml → python, package.json → node, go.mod → go, Cargo.toml → rust)
2. Gather language-specific options (package_name for Python, package_manager for Node, etc.)
3. Check if `.github/workflows/ci.yml` already exists — ask before overwriting (add `--overwrite` if confirmed)
4. Run the copier template
5. Verify the generated YAML is valid

## Generated CI Steps by Language

| Language | Setup | Install | Lint | Format | Types | Test |
|----------|-------|---------|------|--------|-------|------|
| **Python** | setup-uv@v4 + uv python install | uv sync | ruff check | ruff format --check | mypy | pytest |
| **Node** | setup-node@v4 | npm ci / pnpm install / yarn install | npm run lint | — | npm run typecheck | npm run test |
| **Go** | setup-go@v5 | go mod download | golangci-lint-action@v6 + go vet | — | — | go test -v -race |
| **Rust** | rust-toolchain@stable | cargo build | cargo clippy -- -D warnings | cargo fmt --check | — | cargo test |
