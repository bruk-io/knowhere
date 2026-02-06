---
description: "Set up knowhere marketplace publishing. Use when the user wants to publish to knowhere, set up knowhere publishing, register plugin with marketplace, or add their plugin to bruk-io/knowhere."
user_invocable: true
---

# Publish Setup for bruk-io/knowhere Marketplace

Guide the user through setting up their repo to automatically publish a plugin to the bruk-io/knowhere marketplace via GitHub Actions.

This skill uses a copier template at `${CLAUDE_PLUGIN_ROOT}/templates/publish-to-knowhere` to generate the workflow file.

## Steps

### 1. Verify prerequisites

Check that `.claude-plugin/plugin.json` exists in the current repo. If it does not, tell the user they need a valid Claude Code plugin first and stop.

### 2. Read plugin metadata

Read `.claude-plugin/plugin.json` from the current repo to extract:
- `name` — the plugin name
- `description` — the plugin description
- `author.name` — the author (default to `bruk-io` if missing)

### 3. Detect repo identity

Run `git remote get-url origin` to determine the GitHub org and repo name. Parse out the org/repo slug (e.g. `bruk-io/my-plugin`). Strip any `.git` suffix and `https://github.com/` or `git@github.com:` prefix.

### 4. Ask the user for configuration

Use AskUserQuestion to ask:

**Publish mode** — How should the plugin be published?
- **URL (Recommended)** — The plugin source stays in this repo. The marketplace stores a reference URL. Best for plugins maintained in their own repo.
- **Inline** — The plugin source is copied into the marketplace repo. Best for small plugins that live inside knowhere itself.

**Category** — What category best describes this plugin?
- database
- deployment
- design
- development
- learning
- monitoring
- productivity
- security
- testing

### 5. Generate the workflow file with copier

Run copier to generate `.github/workflows/publish-to-knowhere.yml` using the template bundled with this plugin. Pass all gathered values via `--data` flags:

```bash
uvx copier copy --trust --defaults \
  --data plugin_name="<name>" \
  --data plugin_description="<description>" \
  --data plugin_author="<author>" \
  --data plugin_category="<category>" \
  --data publish_mode="<url|inline>" \
  --data org_repo="<org/repo>" \
  "${CLAUDE_PLUGIN_ROOT}/templates/publish-to-knowhere" \
  .
```

If `.github/workflows/publish-to-knowhere.yml` already exists, ask the user before overwriting. If they confirm, add `--overwrite` to the copier command.

After running, verify the generated file looks correct by reading it back and showing the user the result.

### 6. Remind about the secret

Tell the user:

> To complete the setup, add the `KNOWHERE_PAT` secret to your repo:
>
> 1. Create a fine-grained PAT with **Contents: Read and write** access to `bruk-io/knowhere`
> 2. Go to your repo's **Settings > Secrets and variables > Actions**
> 3. Add a new secret named `KNOWHERE_PAT` with the PAT value
>
> Once the secret is set, pushing changes to `.claude-plugin/` on main will automatically publish your plugin to the knowhere marketplace.
