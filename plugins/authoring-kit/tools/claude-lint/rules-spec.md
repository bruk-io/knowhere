# claude-lint - what is and is not a lint rule

A design note, not a runtime artifact: it lives under `tools/` and is never
loaded into a model's context.

## Division of labour

The plugin's own litmus decides where a statement lives: if you could write an
assertion for it, it is code; if you would need a rubric, it is prose.

- **The linter owns every assertable invariant, and its reason.** A rule is a
  row in the script's rule table - id, severity, kind, check, `why` - and a
  finding carries the reason and the fix. `claude-lint rules` prints the table.
- **Reference data lives in the tools.** A frontmatter field, its values and
  default: `claude-lint fields <kind> [field]`. Hook events and handler fields:
  `hooktool events`, `hooktool fields`. Whether an injection loads:
  `claude-lint check-injection`. Whether any of it is stale: `claude-lint drift`.
- **Rule files hold judgement only.** A `rules/*.md` file says what no
  assertion can. Hook mode delivers it on the first touch of its kind, with
  the runnable command for the rest and, once a session, the litmus above.
- **A boundary is a hook**: the auditor's Bash is held to this linter.
- **Skills hold procedure and judgement:** when to set a field, never what the
  field is.

So a fact stated in prose that a command already prints is a bug in the prose.
`tests/test_consistency.py` fails when prose states a limit the linter owns, or
restates a fact that has a single owner.

## Deliberately not linted

These need a rubric. They stay as judgement in the skills, the rule files
and the auditor agent, and must not be faked as lint:

- whether a description is good at triggering (the file-keyed trigger check
  flags one mechanical shape and is an `info`, because it is a guess)
- whether every non-default frontmatter field is justified
- whether `tools` / `disallowedTools` is the minimal boundary for the role
- whether an instruction is specific and verifiable
- one topic per file; enforcement dressed up as guidance
- security review of third-party injection directives
- semantic duplication across CLAUDE.md, AGENTS.md and rules
- which paragraphs of a skill body narrate a procedure that should be a script

And two that another tool owns: hook configuration (`hooktool validate`;
`HK001` only relays its verdict) and the full plugin manifest
(`claude plugin validate`; the `PL` rules repeat the few checks that are cheap
offline).
