# Quick Start

Get up and running with knowhere plugins.

## Scaffold a Python Project

After installing the `python` plugin, ask Claude to create a project:

```
> Create a new Python CLI tool called my-tool
```

Claude will use the copier template to generate a complete project with pyproject.toml, three-layer architecture, tests, and CI.

## Generate a CI Workflow

With the `github` plugin installed:

```
> Set up CI for this project
```

Claude generates a GitHub Actions workflow with linting, formatting, type checking, and tests — tailored to your project's language.

## Deploy Documentation

With the `mkdocs` and `github` plugins installed:

```
> Create documentation for this project and deploy it to GitHub Pages
```

Claude scaffolds an MkDocs Material site and adds a Pages deployment workflow.

## How Plugins Work

Each plugin provides:

- **Skills** — Instructions and copier templates Claude uses to generate code
- **Hooks** — Guard rails that prevent Claude from writing files from scratch when a template exists
- **Cross-plugin references** — Plugins compose with each other (e.g., the Python plugin generates CI via the GitHub plugin)
