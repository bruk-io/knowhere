# Plan: the gates

Spec: [spec.md](../spec.md), change 06. Delivers R10, R11, R12 and R20.

## Files that change

- `intent/self-running-loop/plans/06-gates.md`
- `.github/CODEOWNERS`
- `.github/scripts/check.sh`
- `.github/workflows/checks.yml`
- `.github/workflows/claude-review.yml`
- `.github/workflows/claude.yml`
- `.github/workflows/philosophy-evals.yml`
- `.github/workflows/artefact-check.yml`
- `.github/workflows/validate.yml`
- `.claude/checks.json`
- `.gitignore`
- `plugins/philosophy/templates/CODEOWNERS`
- `plugins/philosophy/README.md`
- `plugins/philosophy/CHANGELOG.md`

## Order of work

1. `.github/CODEOWNERS` assigns `@brukhabtu` the gated paths: intents and specs, the
   gates themselves (`.github/`, `REVIEW.md`, `.claude/settings.json`,
   `.claude/checks.json`, `bands.yaml`, and the plugins' `hooks/`, `scripts/` and
   `evals/`), and LikeC4 models (R12). A template for other repositories ships with
   the plugin.
2. One check script, `.github/scripts/check.sh fast|full`, and `.claude/checks.json`
   declaring both tiers. Fast is the philosophy plugin's tests, ruff, and
   `artefact-check`; full adds authoring-kit's tests and the marketplace validation.
   `.gitignore` lets `.claude/checks.json` through (R11).
3. `checks.yml` runs the full check on every PR, so the evidence is CI's (R11). The
   separate artefact-check workflow goes, since the full check runs it on every PR and a
   path-filtered required check would block PRs that never trigger it.
4. The review gate: `claude-review.yml` runs `/philosophy:review <pr>` with a JSON
   schema for the counts, and fails when the Important count is above zero (R10). It
   lists `claude[bot]` in `allowed_bots`, so it reviews the PRs the loop opens (R11).
5. The evals run on every PR and skip themselves when the plugin didn't change, so the
   check can be required without blocking other PRs (R11).
6. `claude.yml` answers only `@brukhabtu`, so only the owner can continue a gated build
   (R20). Every workflow already declares its permissions; check each is the minimum.
   `main`'s bypass list is empty, so `claude[bot]` is not a bypass actor (R20).
7. README and changelog. The branch protection change itself (code-owner review and
   the required checks) is a repository setting, so the PR gives the command for the
   owner to run once this merges.

## Risks

- A required check that doesn't run blocks a PR forever, so every required check runs
  on every PR and decides inside the job whether there is work to do.
- The action's bot names aren't documented beyond the `[bot]` convention, so
  `allowed_bots` lists `claude[bot]` and `claude`. Allowed bots aren't checked for
  repository permissions, and only the Claude app can act as `claude[bot]`.
- A review job that fails on Important findings fails on the first push of every PR
  that has one, by design; the fix loop is `@claude` on the findings.
- Until the owner changes branch protection, none of this blocks a merge.

## Proof

- `bash .github/scripts/check.sh fast` and `bash .github/scripts/check.sh full` exit 0
  on this branch, and their output is in the PR.
- Each workflow parses, and each declares `permissions`.
- `gh api repos/bruk-io/knowhere/branches/main/protection` shows no bypass allowances.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0.
