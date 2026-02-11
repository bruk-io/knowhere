---
name: evaluate-library
description: This skill should be used when the user asks to "evaluate a library", "compare libraries", "check if this package is safe", "analyze dependencies", "is this library maintained", "should I use X or Y", "find alternatives to", "check library health", "review package security", "check license compatibility", "find similar libraries", or wants help choosing between technologies. Provides comprehensive library evaluation using GitHub stats, package registries, ThoughtWorks Tech Radar, security scanning (OSV, Snyk, Socket), license checking, and dependency analysis across npm, PyPI, crates.io, Maven, RubyGems, NuGet, and Go.
version: 2.0.0
---

# Library Evaluation Skill

Evaluate libraries and packages for health, security, community activity, license compatibility, and dependency burden to make informed technology decisions.

## Supported Ecosystems

| Ecosystem | Script | Registry |
|-----------|--------|----------|
| npm | `npm-package-info.sh` | npmjs.com |
| Python/pip | `pypi-package-info.sh` | pypi.org |
| Rust/Cargo | `crates-package-info.sh` | crates.io |
| Java/Maven | `maven-package-info.sh` | Maven Central |
| Ruby | `rubygems-package-info.sh` | rubygems.org |
| .NET/NuGet | `nuget-package-info.sh` | nuget.org |
| Go | via `gh-repo-stats.sh` | pkg.go.dev |

## Quick Start

For a full evaluation, run these in sequence:

```bash
# 1. Package info
${CLAUDE_PLUGIN_ROOT}/scripts/<ecosystem>-package-info.sh <package>

# 2. GitHub stats (if applicable)
${CLAUDE_PLUGIN_ROOT}/scripts/gh-repo-stats.sh owner/repo

# 3. Security check
${CLAUDE_PLUGIN_ROOT}/scripts/security-check.sh <ecosystem> <package>

# 4. License check
${CLAUDE_PLUGIN_ROOT}/scripts/check-license.sh <ecosystem> <package> [allowed-licenses]

# 5. Dependency analysis
${CLAUDE_PLUGIN_ROOT}/scripts/analyze-deps.sh <ecosystem> <package>

# 6. Find alternatives (optional)
${CLAUDE_PLUGIN_ROOT}/scripts/find-alternatives.sh <ecosystem> <package>
```

## Evaluation Process

### Step 1: Gather Package Information

Run the appropriate package info script:

```bash
# npm
${CLAUDE_PLUGIN_ROOT}/scripts/npm-package-info.sh lodash

# Python
${CLAUDE_PLUGIN_ROOT}/scripts/pypi-package-info.sh requests

# Rust
${CLAUDE_PLUGIN_ROOT}/scripts/crates-package-info.sh serde

# Java (use groupId:artifactId)
${CLAUDE_PLUGIN_ROOT}/scripts/maven-package-info.sh com.google.guava:guava

# Ruby
${CLAUDE_PLUGIN_ROOT}/scripts/rubygems-package-info.sh rails

# .NET
${CLAUDE_PLUGIN_ROOT}/scripts/nuget-package-info.sh Newtonsoft.Json
```

### Step 2: Check GitHub Repository

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh-repo-stats.sh owner/repo
```

Provides: stars, forks, contributors, commit activity, releases, issues, PRs.

### Step 3: Security Analysis

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/security-check.sh <ecosystem> <package>
```

Checks:
- **OSV Database** (osv.dev) - Open Source Vulnerabilities
- **GitHub Security Advisories** - CVEs and security alerts
- **Snyk** - Vulnerability database links
- **Socket.dev** - Supply chain security (npm)
- **deps.dev** - Google's dependency insights

### Step 4: License Compatibility

```bash
# Use default allowed licenses (permissive)
${CLAUDE_PLUGIN_ROOT}/scripts/check-license.sh npm lodash

# Specify allowed licenses
${CLAUDE_PLUGIN_ROOT}/scripts/check-license.sh npm lodash "MIT,Apache-2.0,BSD-3-Clause"
```

Default allowed: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, Unlicense

See `references/license-config.md` for preset configurations.

### Step 5: Dependency Analysis

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/analyze-deps.sh <ecosystem> <package>
# ecosystem: npm, pip, cargo, go
```

Shows: dependency tree, transitive dependency count, potential duplicates, security audit.

### Step 6: Check ThoughtWorks Tech Radar

Search the [ThoughtWorks Technology Radar](https://www.thoughtworks.com/radar):

- **Adopt** - Ready for broad use
- **Trial** - Worth pursuing with manageable risk
- **Assess** - Worth exploring
- **Hold** - Proceed with caution

Use WebSearch: `site:thoughtworks.com/radar {technology}`

### Step 7: Find Alternatives

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/find-alternatives.sh <ecosystem> <package> [category]
```

Searches: Libraries.io, npm trends, awesome lists, ecosystem-specific tools.

## Scoring Framework

| Category | Weight | Criteria |
|----------|--------|----------|
| Activity & Maintenance | 25% | Last commit, release cadence, issue response |
| Community & Support | 20% | Contributors, documentation, support channels |
| Dependencies | 20% | Direct count, transitive count, quality |
| Security | 15% | CVEs, audit results, security policy |
| Documentation | 10% | README, API docs, examples |
| Performance | 10% | Bundle size, benchmarks |

| Score | Recommendation |
|-------|----------------|
| 4.5+ | Excellent, low risk |
| 3.5-4.4 | Good, acceptable risk |
| 2.5-3.4 | Caution advised |
| < 2.5 | Consider alternatives |

## Red Flags

Stop and reconsider if:
- No releases in 18+ months
- Single quiet maintainer
- Critical CVEs unpatched
- On Tech Radar "Hold" ring
- 200+ transitive dependencies
- License incompatible or missing
- Supply chain concerns (Socket.dev alerts)

## Output Format

```markdown
# Library Evaluation: {name}

## Summary
- **Recommendation:** [Use / Consider / Avoid]
- **Score:** X.X/5.0
- **Tech Radar:** [Ring] or Not listed
- **License:** [License] - [Compatible/Incompatible]

## Key Findings
- [Most important point]
- [Second point]
- [Third point]

## Metrics
| Metric | Value | Assessment |
|--------|-------|------------|
| Last Release | X ago | [Good/Warning/Concern] |
| Maintainers | N | [Healthy/Risk] |
| Dependencies | N direct, M transitive | [Low/Moderate/High] |
| Security | X issues | [Clean/Concerns] |

## Security
[Results from security-check.sh]

## License
[Results from check-license.sh]

## Alternatives
[If applicable, from find-alternatives.sh]
```

## Scripts Reference

| Script | Purpose | Usage |
|--------|---------|-------|
| `gh-repo-stats.sh` | GitHub repo analysis | `gh-repo-stats.sh owner/repo` |
| `npm-package-info.sh` | npm package info | `npm-package-info.sh pkg` |
| `pypi-package-info.sh` | PyPI package info | `pypi-package-info.sh pkg` |
| `crates-package-info.sh` | crates.io info | `crates-package-info.sh crate` |
| `maven-package-info.sh` | Maven Central info | `maven-package-info.sh group:artifact` |
| `rubygems-package-info.sh` | RubyGems info | `rubygems-package-info.sh gem` |
| `nuget-package-info.sh` | NuGet info | `nuget-package-info.sh pkg` |
| `security-check.sh` | Security analysis | `security-check.sh ecosystem pkg` |
| `check-license.sh` | License compatibility | `check-license.sh ecosystem pkg [allowed]` |
| `analyze-deps.sh` | Dependency tree | `analyze-deps.sh ecosystem pkg` |
| `find-alternatives.sh` | Find alternatives | `find-alternatives.sh ecosystem pkg` |

## References

- **`references/evaluation-criteria.md`** - Detailed scoring criteria, thresholds, Tech Radar guide
- **`references/license-config.md`** - License presets and compatibility guide

## Examples

- **`examples/evaluation-example.md`** - Complete comparison: date-fns vs dayjs vs moment
