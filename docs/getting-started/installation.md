# Installation

## Requirements

- [Claude Code](https://claude.com/claude-code) CLI installed
- `python3` on PATH: the philosophy plugin's hooks and scripts run under it, 3.9 or later, with nothing to install
- `git` and the GitHub CLI (`gh`) on PATH, for the plays that open PRs

## Add the Marketplace

```bash
claude plugin marketplace add bruk-io/knowhere
```

Inside Claude Code the same step is `/plugin marketplace add bruk-io/knowhere`.

## Install a Plugin

```bash
claude plugin install philosophy@knowhere
```

Start a new session afterwards.
