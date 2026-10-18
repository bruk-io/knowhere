# Plan: the four plays as commands

Spec: [spec.md](../spec.md), change 02. Delivers R4, R5, R6 and R7.

## Files that change

- `intent/self-running-loop/plans/02-plays.md`
- `plugins/philosophy/skills/intent/SKILL.md`
- `plugins/philosophy/skills/spec/SKILL.md`
- `plugins/philosophy/skills/build/SKILL.md`
- `plugins/philosophy/skills/review/SKILL.md`
- `plugins/philosophy/scripts/loop.py`
- `plugins/philosophy/scripts/next-change`
- `plugins/philosophy/scripts/gated-paths`
- `plugins/philosophy/scripts/run-check`
- `plugins/philosophy/tests/test_loop.py`

## Order of work

1. `loop.py`, a pure core for the build's three mechanical decisions: the spec's
   delivery order and which change is next (R6, R9), which of a plan's files
   CODEOWNERS gates (R6, R12), and the evidence block for a check's output (R6).
2. The three thin commands over it: `next-change`, `gated-paths` and `run-check`.
   `next-change` counts a change as taken when its plan is on the branch or a
   `build/<slug>/NN` branch exists on the remote.
3. Tests for the core, and for the commands against this intent.
4. The four skills, each with model invocation off and an argument hint (R4). Each
   body is the procedure only; the mechanical steps call the scripts.
   - `intent`: interview, then write `intent.md` from the template and open its PR.
   - `spec`: write `spec.md` from an accepted intent, apply the policy in force, list it
     in the header, map every constraint, and flag conflicts as areas of concern (R5).
   - `build`: next change, plan as the first commit, stop at a gated path, implement,
     run the fast check, open the PR with the evidence (R6).
   - `review`: passes against `REVIEW.md` or the default three, inline findings, a
     verdict, never approve, end with the Important count (R7).
5. Lint the skills with `claude-lint`.

## Risks

- A skill body is read once, when the command runs, so it states the procedure as
  standing instructions and keeps the mechanical choices in scripts, where they can't
  drift between runs.
- CODEOWNERS has no file until change 06, so `gated-paths` reports nothing until then
  and every build in this intent goes through review by hand anyway.
- The review's structured count only gates a merge once the workflow passes
  `--json-schema` and fails on it (change 06). Here the skill ends with the count.
- `run-check` needs `.claude/checks.json`, which knowhere doesn't have yet (it is a
  gated path, added in change 06). Without it, the command exits 2 and says what to
  declare.

## Proof

- `uv run --no-project --with pytest python -m pytest -q` in `plugins/philosophy`
  passes, including tests that `next-change` picks 01, then skips a change with a plan
  or a remote branch, then reports done; that `gated-paths` matches CODEOWNERS patterns
  (anchored, `*`, `**`, directories) against a plan's files; and that `run-check` writes
  the command, exit code and output tail.
- `claude-lint` reports no errors on the four skills.
- `uvx ruff check --config plugins/philosophy/ruff.toml plugins/philosophy` is clean.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0.
