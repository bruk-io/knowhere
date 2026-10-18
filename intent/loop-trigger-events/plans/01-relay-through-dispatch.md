# Plan: relay through repository_dispatch

Spec: [spec.md](../spec.md), change 01. Delivers R1, R2, R3, R4, R5.

## Files that change

- `intent/loop-trigger-events/plans/01-relay-through-dispatch.md`
- `intent/self-running-loop/spec.md`
- `.github/workflows/intent-spec.yml`
- `.github/workflows/intent-build.yml`
- `plugins/philosophy/templates/github/intent-spec.yml`
- `plugins/philosophy/templates/github/intent-build.yml`
- `plugins/philosophy/templates/github/README.md`

## Order of work

1. `intent/self-running-loop/spec.md`: reword its eighth and ninth requirements to say
   the push fires the matching `repository_dispatch`, which runs the play, and reword
   its eleventh requirement's chaining sentence to say the merge starts `find` on
   `push`, and `find`'s dispatch, not the merge itself, is what starts the action (R4).
2. `.github/workflows/intent-spec.yml`:
   - `on:` gains `repository_dispatch: types: [intent-spec]` alongside the unchanged
     `push` trigger (R1).
   - `find` gains `if: github.event_name == 'push'`; its diff logic is unchanged (R1).
   - A new `dispatch` job (`needs: find`,
     `if: "github.event_name == 'push' && needs.find.outputs.slugs != '[]'"`,
     `permissions: contents: write`) posts
     `repos/${{ github.repository }}/dispatches` with `event_type: intent-spec` and
     `client_payload` fields `slugs` (`needs.find.outputs.slugs`, the compact JSON
     array string unchanged), `before` (`github.event.before`) and `sha`
     (`github.sha`), read through `env:` rather than inlined into `run:` (R1, R2). The
     explicit `github.event_name == 'push'` matters even though `find` already skips
     on a `repository_dispatch`-triggered run: a custom `if:` with no status-check
     function (`success()` etc.) is *not* made conditional on its `needs:` job having
     run, so without it `dispatch` would evaluate `needs.find.outputs.slugs != '[]'`
     against an empty string on every `repository_dispatch` run too, and fire a bogus
     second dispatch.
   - The `spec` job keeps `needs: find` for ordering, but its `if:` becomes
     `github.event_name == 'repository_dispatch'` with no status-check function, so
     on a `repository_dispatch`-triggered run it still runs even though `find` (and
     `dispatch`) were skipped on that same run — GitHub Actions only cascades a
     `needs:` job's skip into a dependent job when the dependent's `if:` relies on the
     default success check or calls a status function; a bare boolean expression
     overrides that. Matrix slug comes from
     `fromJSON(github.event.client_payload.slugs)`; checkout is of `main` with
     `fetch-depth: 0`. A new step before the action, reading `matrix.slug` and
     `github.event.client_payload.before`/`sha` through `env:`, fails the job
     (non-zero exit, red) unless, in order: the slug matches `^[a-z0-9][a-z0-9-]*$`;
     `before` and `sha` are each non-zero (`git hash-object --stdin <<<''` is not a
     valid guard; compare against `0000000000000000000000000000000000000000`) and
     `sha` is an ancestor of (on) `main` and `before` is an ancestor of `sha`; the diff
     over that range, filtered the same way `find` filters it, touches
     `intent/<slug>/intent.md`. Only after all four pass does the step set a `due`
     output: `false` (the run stays green, the action step is skipped) when
     `intent/<slug>/spec.md` already exists on `main` or a remote `spec/<slug>`
     branch exists; `true` otherwise (R5). The action step gains
     `if: steps.<verify>.outputs.due == 'true'` and `allowed_bots:
     "github-actions[bot]"` (R3).
3. `.github/workflows/intent-build.yml`: the same shape as step 2 for `find`,
   `dispatch` and the `if:`/matrix/checkout changes to the `build` job, with two
   differences the spec's chosen checks already draw: the diff filter is `find`'s
   unfiltered one (`intent/*/spec.md`, `intent/*/plans/*.md`, no
   `--diff-filter=AM`), and the "still due" half of R5 (the fourth check) is left to
   the existing `next` step rather than folded into the new verify step. The ordering
   inside the `build` job becomes: the new verify step runs first and, same as step 2,
   hard-fails the job on the first three checks; only if it passes does the existing
   `next` step run `next-change` and keep its current `[ $code -le 1 ]` behaviour
   (skip green on "done"/"taken", fail red above that); the action step keeps its
   existing `if: steps.next.outputs.build == 'true'` and gains `allowed_bots`
   (R1, R2, R3, R5).
4. `plugins/philosophy/templates/github/intent-spec.yml` and `intent-build.yml`:
   the same edits as steps 2 and 3, keeping each template's existing divergence from
   its `.github/workflows/` counterpart (the pinned `actions/checkout` version, the
   knowhere clone step, the pinned `setup-uv` version, the narrower
   `--allowedTools`) (R1).
5. `plugins/philosophy/templates/github/README.md`: reword the `intent-spec.yml` and
   `intent-build.yml` table rows to say each runs in two hops, `find` on the merge and
   the action on `find`'s dispatch, so a repository copying these templates doesn't
   read the old single-hop description as current (R1).
6. After this PR merges to `main` (the relay only exists once `main` has it — this
   step cannot run from the branch): push a throwaway smoke-test intent on its own
   branch, merged by hand the way `loop-smoke-test` verified the handovers before it,
   and watch `find` and `dispatch` run on that merge, then confirm the `spec` job's
   action step is reached under `repository_dispatch` rather than failing at
   `Unsupported event type` or at `checkHumanActor` (spec open question, Areas of
   concern 2). Record the run's URL as a follow-up comment on this PR. A
   `checkHumanActor` failure is informative, not a design error: it names the actual
   actor, and the fix is a one-line edit to `allowed_bots` in both workflows (and
   their templates); since this PR has already merged by then, that fix ships as its
   own quick follow-up PR under the same gate (`.github/` is a CODEOWNERS path
   regardless of how small the edit is).

## Risks

- `gh api`'s bracket notation (`-f "client_payload[slugs]=$SLUGS"`) has to build the
  nested JSON object GitHub's dispatches endpoint expects, with `slugs` staying a
  string field rather than becoming a nested array; a malformed call either errors
  loudly or silently changes the payload shape the `spec`/`build` job reads with
  `fromJSON`. Step 6's live push is what actually proves this, not a local check.
- `find`'s diff filter and the verify step's filter must stay identical (R5's third
  check exists only to re-derive what `find` already decided); a drift reopens the
  gap between what `find` found and what the dispatched job verifies.
- The `checkHumanActor` actor for a `GITHUB_TOKEN`-fired `repository_dispatch` rests on
  convention (spec Areas of concern 2), not on a run in this repository. Step 6 is
  where that gets settled, and the fix if it's wrong is scoped in this plan already.
- `fetch-depth: 0` is required wherever `git merge-base --is-ancestor` or a
  `before..sha` diff runs; a shallow checkout makes the ancestry checks fail closed
  (hard failure, not a false pass), which is the safe direction if it's missed, but
  would still block every run.
- `github.event.before` is all zeros on a branch's first push, and the 07-triggers
  plan noted `main` never sees that. A force-push to `main` or a recreated `main`
  history would, though, and the zero-SHA guard added in step 2 turns that into a hard
  failure rather than a skip, same as any other broken range. That is the correct
  direction for R5 (fail closed), not a gap, but it means a force-push to `main` would
  need its `intent-build`/`intent-spec` runs re-triggered by hand once `before` is
  sane again.

## Proof

- `python3 plugins/philosophy/scripts/run-check fast` exits 0 (philosophy's tests and
  lint, and `artefact-check intent`, unaffected by this change).
- `python3 -c "import yaml,glob; [yaml.safe_load(open(p)) for p in glob.glob('.github/workflows/intent-*.yml') + glob.glob('plugins/philosophy/templates/github/intent-*.yml')]"` exits without error, confirming the edited workflows still parse.
- Step 6's smoke-test run, added as a comment on this PR once it merges: the `find`
  job's run (triggered by `push`), the `dispatch` job's run, and the `spec` (or
  `build`) job's run (triggered by `repository_dispatch`), with the action step
  shown reaching Claude's run rather than `Unsupported event type` or
  `checkHumanActor`.
