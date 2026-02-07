---
name: claude-md
description: "This skill should be used when the user asks to \"create a CLAUDE.md\", \"scaffold CLAUDE.md\", \"set up Claude Code config\", \"initialize CLAUDE.md\", \"create global Claude config\", or mentions CLAUDE.md scaffolding or Claude Code global configuration setup. Generates a starter ~/.claude/CLAUDE.md file."
---

# CLAUDE.md Scaffolding

Generate a starter `~/.claude/CLAUDE.md` global configuration file for Claude Code using a copier template.

## When to Use

This skill scaffolds a **new** CLAUDE.md from scratch. It is meant for users who do not yet have a global CLAUDE.md and want a structured starting point. For auditing or improving an existing CLAUDE.md, use the `claude-md-improver` skill instead.

## Generating a CLAUDE.md

### Using the Copier Template

```bash
uvx copier copy --trust --defaults \
  --data-file ~/.config/copier/defaults.yml \
  --data name="<name>" \
  "${CLAUDE_PLUGIN_ROOT}/skills/claude-md/templates/claude-md-for-human/" \
  ~/.claude/
```

If `~/.config/copier/defaults.yml` does not exist, omit the `--data-file` flag.

### Template Options

- `name` (str, required) — The user's name or alias

### Workflow

1. Check if `~/.claude/CLAUDE.md` already exists — if so, warn the user and ask before overwriting
2. Ask for the user's name if not provided
3. Run the copier template targeting `~/.claude/`
4. After generation, walk the user through filling in the placeholder sections:
   - Role and focus areas
   - Environment variables
   - Programming language preferences and tooling
   - Testing philosophy
   - Workflow preferences
   - Communication style preferences

## Generated Output

The template produces a `CLAUDE.md` with structured sections:

- **About Your Human** — Name, role, current focus
- **Environment Variables** — Key env vars Claude should know about
- **Programming Languages** — Per-language preferences (tools, libraries, code style)
- **Testing Philosophy** — Testing approach and boundaries
- **Workflow Philosophy** — How the user prefers to work
- **Communication** — How Claude should communicate

Each section has placeholder text that the user fills in to match their preferences.
