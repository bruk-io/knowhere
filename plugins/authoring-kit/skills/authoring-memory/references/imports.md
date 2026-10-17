# Import and AGENTS.md bridge examples

Literal syntax for `Skill(authoring-kit:authoring-memory)`. It lives here because a
SKILL.md body attaches at-sign paths at load; a reference file read with the Read
tool is inert.

## Imports in CLAUDE.md, CLAUDE.local.md, rules, and AGENTS.md

```text
See @README for the overview and @package.json for npm commands.

# Additional instructions
- git workflow @docs/git-instructions.md
- personal, shared across worktrees @~/.claude/my-project-instructions.md
- path with spaces @Design\ Docs/api-conventions.md
```

- `@docs/git-instructions.md` resolves against the file containing the import.
- `@~/...` and absolute paths point outside the project: an external import, subject
  to the approval dialog when it sits in a project-level file.
- `` `@README` `` in a code span, or any import inside a fenced block, stays literal.
- `@"Design Docs/x.md"` (quoted) is not imported at all.
- Observed on 2.1.295: with a chain `CLAUDE.md` → `h1.md` → ... → `h6.md`, content
  through `h4.md` reached the model and `h5.md` did not - the documented hop limit (CM002).

## Bridging AGENTS.md from CLAUDE.md

Use when the repo needs both files, or some sessions cannot read `AGENTS.md`
directly:

```markdown
@AGENTS.md

## Claude Code

Use plan mode for changes under `src/billing/`.
```

With no Claude-specific content, a symlink also works (not for Windows clones; Edit
and Write refuse to write through it):

```bash
ln -s AGENTS.md CLAUDE.md
```

## Reading CLAUDE.md and AGENTS.md together

`/config` → **Project instructions**, or in `~/.claude/settings.json`, a `--settings`
file, or managed settings (ignored in project and local settings):

```json
{
  "pluginConfigs": {
    "cc-plugin-agents-md@builtin": {
      "options": { "instructionFiles": "claude-md-and-agents-md" }
    }
  }
}
```

Before v2.1.285 the plugin ID was `agents-md@builtin`; later versions read either.
