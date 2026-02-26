# Installation

## Requirements

- [Claude Code](https://claude.com/claude-code) CLI installed
- [UV](https://docs.astral.sh/uv/) (used by copier templates)

## Add the Marketplace

Add knowhere as a plugin marketplace in your Claude Code settings:

```bash
claude plugins add-marketplace https://github.com/bruk-io/knowhere.git
```

This registers the marketplace so you can browse and install plugins from it.

## Install a Plugin

```bash
claude plugins install <plugin-name>
```

For example, to install the Python scaffolding plugin:

```bash
claude plugins install python
```
