# knowhere

Personal Claude Code plugin marketplace for bruk-io projects.

## Install

Register the marketplace in Claude Code:

```
/plugin marketplace add bruk-io/knowhere
```

Then browse and install plugins:

```
/plugin search
```

## Structure

```
.claude-plugin/marketplace.json   # Marketplace manifest
plugins/                          # Inline plugins (full source)
external_plugins/                 # URL-referenced plugins (shims)
```

- **Inline plugins** have their full source copied into `plugins/<name>/`
- **URL plugins** point to an external git repo and have a minimal shim in `external_plugins/<name>/`

## Publishing Plugins

Plugins are published automatically via GitHub Actions. Add a workflow to your plugin repo that sends a `repository_dispatch` event to this marketplace.

### Prerequisites

Create a fine-grained PAT with:
- **Repository access**: `bruk-io/knowhere` (Contents: Read and write)
- Add it as `KNOWHERE_PAT` in your plugin repo's secrets

### URL Plugin (recommended for external repos)

The plugin source stays in its own repo. The marketplace stores a reference URL.

Add this workflow to your plugin repo:

```yaml
# .github/workflows/publish-to-knowhere.yml
name: Publish to knowhere

on:
  push:
    branches: [main]
    paths:
      - ".claude-plugin/**"

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Read plugin.json
        id: plugin
        run: |
          echo "json=$(cat .claude-plugin/plugin.json)" >> "$GITHUB_OUTPUT"

      - name: Read mcp.json
        id: mcp
        run: |
          if [ -f .claude-plugin/mcp.json ]; then
            echo "json=$(cat .claude-plugin/mcp.json)" >> "$GITHUB_OUTPUT"
          else
            echo "json=null" >> "$GITHUB_OUTPUT"
          fi

      - name: Publish
        env:
          GH_TOKEN: ${{ secrets.KNOWHERE_PAT }}
        run: |
          gh api repos/bruk-io/knowhere/dispatches \
            -f event_type=publish-url-plugin \
            -f 'client_payload={
              "plugin": {
                "name": "YOUR_PLUGIN_NAME",
                "description": "YOUR_DESCRIPTION",
                "author": {"name": "bruk-io"},
                "category": "development",
                "homepage": "https://github.com/bruk-io/YOUR_REPO",
                "url": "https://github.com/bruk-io/YOUR_REPO.git"
              },
              "shim": {
                "plugin_json": ${{ toJson(steps.plugin.outputs.json) }},
                "mcp_json": ${{ toJson(steps.mcp.outputs.json) }}
              }
            }'
```

### Inline Plugin (for plugins hosted in this marketplace)

The plugin source is copied into the marketplace repo.

```yaml
# .github/workflows/publish-to-knowhere.yml
name: Publish to knowhere

on:
  push:
    branches: [main]
    paths:
      - ".claude-plugin/**"

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Publish
        env:
          GH_TOKEN: ${{ secrets.KNOWHERE_PAT }}
        run: |
          gh api repos/bruk-io/knowhere/dispatches \
            -f event_type=publish-inline-plugin \
            -f "client_payload={
              \"plugin\": {
                \"name\": \"YOUR_PLUGIN_NAME\",
                \"description\": \"YOUR_DESCRIPTION\",
                \"author\": {\"name\": \"bruk-io\"},
                \"category\": \"development\",
                \"homepage\": \"https://github.com/bruk-io/YOUR_REPO\"
              },
              \"source_repo\": \"bruk-io/YOUR_REPO\",
              \"source_ref\": \"$(git rev-parse HEAD)\",
              \"source_path\": \".\"
            }"
```

### Removing a Plugin

```yaml
- name: Remove
  env:
    GH_TOKEN: ${{ secrets.KNOWHERE_PAT }}
  run: |
    gh api repos/bruk-io/knowhere/dispatches \
      -f event_type=remove-plugin \
      -f 'client_payload={"plugin": {"name": "YOUR_PLUGIN_NAME"}}'
```

## Allowed Categories

- `database`
- `deployment`
- `design`
- `development`
- `learning`
- `monitoring`
- `productivity`
- `security`
- `testing`

## Secrets

| Secret | Where | Purpose |
|--------|-------|---------|
| `MARKETPLACE_PAT` | knowhere | Push commits, clone source repos |
| `KNOWHERE_PAT` | publisher repos | Send `repository_dispatch` to knowhere |

Both can use the same fine-grained PAT scoped to the bruk-io org.

## Local Development

Validate the marketplace:

```bash
python .github/scripts/validate-plugin.py --mode marketplace
```

Test the update script:

```bash
python .github/scripts/update-marketplace.py \
  --mode upsert-url \
  --plugin-json '{"name":"test-plugin","description":"Test","author":{"name":"bruk-io"},"category":"development","source":{"source":"url","url":"https://github.com/bruk-io/test.git"}}'
```
