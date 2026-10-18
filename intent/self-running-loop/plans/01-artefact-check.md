# Plan: templates and artefact-check

Spec: [spec.md](../spec.md), change 01. Delivers R1, R2 and R3.

## Files that change

- `intent/self-running-loop/plans/01-artefact-check.md`
- `plugins/philosophy/templates/intent.md`
- `plugins/philosophy/templates/spec.md`
- `plugins/philosophy/templates/plan.md`
- `plugins/philosophy/scripts/artefact.py`
- `plugins/philosophy/scripts/artefact-check`
- `plugins/philosophy/hooks/artefact_hook.py`
- `plugins/philosophy/hooks/hooks.json`
- `plugins/philosophy/tests/test_artefact.py`
- `.github/workflows/artefact-check.yml`

## Order of work

1. The three templates, from the playbook's sections and this intent's own files (R1).
2. The core in `artefact.py`: parse headings, checkboxes and R-numbers, one check per
   artefact, findings as plain data. No file or process access (R2).
3. Tests against this intent's real files, and against copies broken one way each.
4. `artefact-check`, a thin command over the core, with exit codes 0, 1 and 2 (R2).
5. The write hook and its entry in `hooks.json`, so a finding arrives with the write
   that caused it (R3).
6. The PR check workflow, read-only, on PRs that touch `intent/**` (R3).
7. Run the command on this intent and fix what it reports.
8. Check locally that a plugin command runs from a `claude -p` prompt (spec area of
   concern 4).

## Risks

- The spec paraphrases the intent's constraints in its constraint mapping, so the check
  compares counts, not wording. A mapping with the right number of rows and a missing
  constraint passes. The finding says the check counts rows.
- The write hook runs on every Write and Edit. It does nothing for a path outside
  `intent/`, and like `context.py` it never breaks the session: any failure exits 0
  with the reason on stderr.
- Area of concern 4 can't be checked in CI until a workflow is on `main`. This change
  checks the mechanism locally and records the result; the CI check lands with the
  triggers in change 07.

## Proof

- `uv run --no-project --with pytest python -m pytest -q` in `plugins/philosophy`
  passes. The new tests show each artefact passing on this intent's files and failing
  with a named finding for a missing section, a gap in the R-numbers, an unticked open
  question, a concern with no owner, and a plan citing an R-number its spec doesn't
  define.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0 on this branch.
- `uvx ruff check --config plugins/philosophy/ruff.toml plugins/philosophy` is clean.
- A hook test: a Write to a broken plan returns the finding as `additionalContext`, and
  a Write anywhere else returns nothing.
