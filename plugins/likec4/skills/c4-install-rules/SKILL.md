---
name: c4-install-rules
description: Installs glob-scoped C4 methodology rule files into .claude/rules/ so Claude receives level-specific guidance when editing .likec4 files. Use when setting up C4 rules, adding architecture linting, or installing likec4 methodology rules.
disable-model-invocation: true
allowed-tools: Bash, Read
---

# Install C4 Rules

Run the copy-rules script to install C4 methodology rule files into the current project's `.claude/rules/` directory.

## Steps

1. Run the copy-rules script:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/copy-rules ${CLAUDE_PLUGIN_ROOT}/rules
   ```

2. The script will:
   - Create `.claude/rules/` if it doesn't exist
   - Copy all C4 rule files from the plugin's `rules/` directory
   - Skip files that already exist (unless `--force` is passed)
   - Report what was installed

3. Show the user what was installed and explain:
   - Rules are scoped via `globs` frontmatter to specific file patterns
   - Context-level rules only activate when editing `context.likec4` files
   - Container-level rules only activate in `containers/` directories
   - Component-level rules only activate in `components/` directories
   - Relationship rules apply to all `.likec4` files
   - Rules require the recommended directory structure from `/c4-init`

4. If the project doesn't have an `architecture/` directory, suggest running `/c4-init` first.
