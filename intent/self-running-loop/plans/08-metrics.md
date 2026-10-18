# Plan: metrics and control bands

Spec: [spec.md](../spec.md), change 08. Delivers R18 and R19.

## Files that change

- `intent/self-running-loop/plans/08-metrics.md`
- `plugins/philosophy/scripts/metrics.py`
- `plugins/philosophy/scripts/loop-metrics`
- `plugins/philosophy/scripts/loop-readings`
- `plugins/philosophy/scripts/band.py`
- `plugins/philosophy/scripts/band-check`
- `plugins/philosophy/tests/test_metrics.py`
- `plugins/philosophy/tests/test_band.py`
- `bands.yaml`
- `.github/workflows/loop-bands.yml`
- `plugins/philosophy/templates/bands.yaml`
- `plugins/philosophy/templates/github/loop-bands.yml`
- `plugins/philosophy/templates/github/README.md`
- `plugins/philosophy/README.md`
- `plugins/philosophy/CHANGELOG.md`

## Order of work

1. `metrics.py`, a pure core over `gh`'s JSON and git's timestamps: the CI failure rate
   and PR cycle hours per day, the share of PRs merged without the owner, Important
   findings per PR, the hours between handovers, and spec changes after the first plan
   (R18).
2. `loop-metrics`, the per-intent and repository report, reading merge times from
   `main`'s first-parent history and PRs from `gh` (R18).
3. `band.py`, the playbook's detection: mean and sigma over a baseline, 1, 2 and 3
   sigma, and the two Western Electric drift rules. No model (R19).
4. `loop-readings` (one value per day for a metric, from `gh`) and `band-check` (the
   tier the newest reading falls in), thin commands over the two cores (R19).
5. `bands.yaml`, which says what each tier may do, and `loop-bands.yml`, a daily
   workflow: 1 sigma logs, 2 sigma has Claude diagnose read-only into the run summary,
   3 sigma has `/philosophy:intent` write the breach up as an intent, whose PR the owner
   triages (R19). Templates of both for another repository.
6. Tests for both cores and for the commands with a fake `gh`.
7. README and changelog.

## Risks

- The playbook's baseline is 30 days of hourly readings. A personal repository has too
  few runs an hour for that, so readings are daily, and a verdict needs seven earlier
  days. Until then `band-check` exits 2 and the workflow says there aren't enough
  readings yet.
- Merge times come from `main`'s first-parent history, so a change that lands without a
  merge commit is timed by its own commit, which is when it was written, not merged.
- An intent written at 3 sigma is the owner's to triage, like any intent: CODEOWNERS
  holds it, and nothing builds until they merge it.

## Proof

- `uv run --no-project --with pytest python -m pytest -q` in `plugins/philosophy`
  passes, including the band rules (3 sigma, 2 sigma, both drift rules, 1 sigma, too
  few readings), the per-day readings, the share merged without the owner, the
  Important count, spec rework, and `band-check` and `loop-readings` with a fake `gh`.
- `loop-metrics` and `loop-readings` run against this repository and print real
  numbers.
- `bash .github/scripts/check.sh fast` passes.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0.
