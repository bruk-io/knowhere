# Dockerfile Security Hardening

## Run as Non-Root

Never run production containers as root.

```dockerfile
# Create a dedicated system user
RUN groupadd --system app && useradd --system --gid app app

# ... copy files ...

USER app
```

For scratch-based images (Go, Rust), copy passwd file:

```dockerfile
FROM scratch
COPY --from=build /etc/passwd /etc/passwd
COPY --from=build /etc/group /etc/group
USER app
```

## Use Specific Image Tags

Always pin to a specific version, not `latest`:

```dockerfile
# Good
FROM python:3.14-slim
FROM node:22-slim
FROM golang:1.24

# Bad
FROM python:latest
FROM node
FROM golang
```

## Minimize Attack Surface

### Production images should contain only what's needed to run:

- No compilers, package managers, or build tools
- No dev dependencies
- No source code (for compiled languages)
- No shell if possible (scratch images)

### Remove unnecessary packages:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    <only-what-you-need> \
    && rm -rf /var/lib/apt/lists/*
```

## No Secrets in Images

Never copy secrets into the image:

```dockerfile
# BAD: Secret baked into image
COPY .env /app/.env
ENV API_KEY=sk-1234

# GOOD: Secrets injected at runtime
# Use environment variables, mounted secrets, or secret managers
```

For build-time secrets (e.g., private package registries):

```dockerfile
# Use BuildKit secrets — never appear in image layers
RUN --mount=type=secret,id=npm_token \
    NPM_TOKEN=$(cat /run/secrets/npm_token) npm ci
```

## Read-Only Filesystem

Run containers with read-only root filesystem when possible:

```yaml
# docker-compose.yml
services:
  app:
    read_only: true
    tmpfs:
      - /tmp
```

Design the application to write only to specific mounted volumes or tmpfs.

## Health Checks

Include health checks so orchestrators can detect unhealthy containers:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

For scratch images without curl:

```dockerfile
# Build a tiny health check binary in the build stage
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["/healthcheck"]
```

## Scan for Vulnerabilities

Integrate scanning into CI:

```yaml
# GitHub Actions
- uses: docker/scout-action@v1
  with:
    command: cves
    image: ${{ steps.build.outputs.imageid }}
    only-severities: critical,high
```

Or use trivy:

```yaml
- uses: aquasecurity/trivy-action@master
  with:
    image-ref: myapp:latest
    severity: CRITICAL,HIGH
```

## Checklist

- [ ] Non-root user in production
- [ ] Specific image version tags (no `latest`)
- [ ] No secrets in image layers
- [ ] Minimal packages installed
- [ ] Build tools excluded from production image
- [ ] Health check defined
- [ ] `.dockerignore` excludes sensitive files
- [ ] Vulnerability scanning in CI
