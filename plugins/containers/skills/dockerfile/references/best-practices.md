# Dockerfile Best Practices

## Multi-Target Build Strategy

Every Dockerfile should support multiple build targets for different environments. A single Dockerfile serves CI pipelines, development, and production by using named stages that can be selected with `--target`.

### Standard Targets

| Target | Purpose | Used by |
|--------|---------|---------|
| `deps` / `build` | Install dependencies or compile binaries | Base for other stages |
| `ci` | Run tests, linting, type checking | GitHub Actions (`target: ci`) |
| `dev` | Full dev environment with tools | Devcontainers, local dev |
| `prod` | Minimal runtime image | Deployment (K8s, ECS, etc.) |

### Target Dependency Patterns

**Interpreted languages** (Python, Node): `deps → ci → dev`, `deps → prod`
**Compiled languages** (Go, Rust): `build → prod`, separate `ci` and `dev` from source

### GitHub Actions Integration

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v6
        with:
          target: ci
          cache-from: type=gha
          cache-to: type=gha,mode=max

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v6
        with:
          target: prod
          push: true
          tags: ghcr.io/${{ '{{' }} github.repository {{ '}}' }}:${{ '{{' }} github.sha {{ '}}' }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Devcontainer Integration

```json
// .devcontainer/devcontainer.json
{
  "build": {
    "dockerfile": "../Dockerfile",
    "target": "dev"
  },
  "forwardPorts": [8000]
}
```

## Layer Caching

### Order Instructions by Change Frequency

Place rarely-changing instructions first:

```dockerfile
# 1. Base image (changes rarely)
FROM python:3.14-slim

# 2. System deps (changes rarely)
RUN apt-get update && apt-get install -y ...

# 3. App deps (changes occasionally)
COPY requirements.txt .
RUN pip install -r requirements.txt

# 4. App code (changes frequently)
COPY . .
```

### Use BuildKit Cache Mounts

Cache package manager data between builds:

```dockerfile
# Python/UV
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Python/pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Node/npm
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Node/pnpm
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# Go
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build -o /bin/app .

# Rust (cargo registry)
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    cargo build --release
```

### Use Bind Mounts for Lock Files

Avoid copying files that are only needed during build:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project
```

### .dockerignore

Always create a `.dockerignore` to exclude unnecessary files:

```
.git
.github
.venv
__pycache__
node_modules
target/
*.md
!README.md
.env*
.claude*
```

## Image Size Optimization

### Choose Appropriate Base Images

| Language | Dev/CI base | Prod base |
|----------|------------|-----------|
| Python | `python:X.Y-slim` | `python:X.Y-slim` |
| Node | `node:X-slim` | `node:X-slim` |
| Go | `golang:X` | `scratch` or `gcr.io/distroless/static` |
| Rust | `rust:X-slim` | `scratch` or `gcr.io/distroless/static` |

### Strip Debug Info from Compiled Binaries

```dockerfile
# Go
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /bin/app .

# Rust
RUN cargo build --release
# (release profile already strips by default with strip = true in Cargo.toml)
```

### Combine RUN Commands

Reduce layers by combining related commands:

```dockerfile
# Good: single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Bad: multiple layers, cache not cleaned
RUN apt-get update
RUN apt-get install -y git curl
```
