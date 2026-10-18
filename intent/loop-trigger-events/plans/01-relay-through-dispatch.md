# Plan: relay through repository_dispatch

Spec: [spec.md](../spec.md), change 01. Delivers R1, R2, R3, R4, R5.

## Files that change

- `intent/loop-trigger-events/plans/01-relay-through-dispatch.md`
- `intent/self-running-loop/spec.md`
- `plugins/philosophy/scripts/dispatch-check`
- `plugins/philosophy/tests/test_dispatch_check.py`
- `plugins/philosophy/README.md`
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
2. `plugins/philosophy/scripts/dispatch-check`: the R5 checks as a script, so the
   property this change rests on is tested before merge, not only by step 7's live run
   ("validation logic is a script"). `dispatch-check spec|build <slug> --before <sha>
   --sha <sha> [--root DIR] [--remote origin]` exits 2, saying why, unless, in order:
   the slug matches `^[a-z0-9][a-z0-9-]*$`; `before` and `sha` are each a full 40-hex
   sha other than all zeros; `sha` is on `main` and `before` is an ancestor of `sha`;
   and the diff over `before..sha`, with the same paths and filter `find` uses for that
   play (`--diff-filter=AM` on `intent/*/intent.md` for `spec`; `intent/*/spec.md` and
   `intent/*/plans/*.md`, unfiltered, for `build`), touches the slug's trigger path.
   For `spec` it then exits 1, the run to stay green, when `intent/<slug>/spec.md` is
   on `main` or a `spec/<slug>` branch is on the remote, and 0 when the spec is due.
   For `build` it exits 0 once the checks pass, and the existing `next-change` step
   decides whether the change is due (R5). Pure functions take the facts and return a
   verdict; one thin function reads git. `tests/test_dispatch_check.py` runs it
   against throwaway repositories with a bare remote, and the README's script list
   gains it.
3. `.github/workflows/intent-spec.yml`:
   - `on:` gains `repository_dispatch: types: [intent-spec]` alongside the unchanged
     `push` trigger (R1).
   - `find` gains `if: github.event_name == 'push'`; its diff logic is unchanged (R1).
   - A new `dispatch` job (`needs: find`,
     `if: "github.event_name == 'push' && needs.find.outputs.slugs != '[]'"`,
     `permissions: contents: write`) posts
     `repos/${{ github.repository }}/dispatches` with `event_type: intent-spec` and
     `client_payload` fields `slugs` (`needs.find.outputs.slugs`, the compact JSON
     array string unchanged), `before` (`github.event.before`) and `sha`
     (`github.sha`), read through `env:` rather than inlined into `run:` (R1, R2). On
     a `repository_dispatch`-triggered run `dispatch` is skipped: an `if:` with no
     status-check function gets an implicit `success() &&`, and `find`, which it
     needs, is skipped on that run. The explicit `github.event_name == 'push'` says the
     same thing outright.
   - The `spec` job drops `needs: find`, and its `if:` becomes
     `github.event_name == 'repository_dispatch'`. It must not need `find`: with the
     implicit `success() &&`, a job whose `needs` was skipped is skipped too, and
     `find` never runs on a dispatch-triggered run, so the action would never be
     reached. It doesn't need `find`'s output either, since its slugs come from the
     payload. Its matrix slug comes from `fromJSON(github.event.client_payload.slugs)`,
     and it checks out `main` with `fetch-depth: 0`. A new step before the action,
     reading `matrix.slug` and `github.event.client_payload.before`/`sha` through
     `env:`, runs `dispatch-check spec` (step 2): exit 2 fails the job red, exit 1 sets
     `due=false` (the run stays green and the action step is skipped), and exit 0 sets
     `due=true` (R5). The action step gains `if: steps.<verify>.outputs.due == 'true'`
     and `allowed_bots: "github-actions[bot]"` (R3).
4. `.github/workflows/intent-build.yml`: the same shape as step 3 for `find`,
   `dispatch` and the `build` job, which likewise drops `needs: find`, with two
   differences the spec's chosen checks already draw: `dispatch-check build` uses
   `find`'s unfiltered diff (`intent/*/spec.md`, `intent/*/plans/*.md`), and the
   "still due" half of R5 (the fourth check) is left to the existing `next` step. The
   ordering inside the `build` job becomes: the verify step runs `dispatch-check build`
   first and hard-fails the job on exit 2; only if it passes does the existing `next`
   step run `next-change` and keep its current `[ $code -le 1 ]` behaviour (skip green
   on "done"/"taken", fail red above that); the action step keeps its existing
   `if: steps.next.outputs.build == 'true'` and gains `allowed_bots`
   (R1, R2, R3, R5).
5. `plugins/philosophy/templates/github/intent-spec.yml` and `intent-build.yml`: the
   same edits as steps 3 and 4, keeping each template's existing divergence from its
   `.github/workflows/` counterpart (the pinned `actions/checkout` version, the
   knowhere clone step, the pinned `setup-uv` version, the narrower `--allowedTools`).
   The templates run `dispatch-check` from the knowhere clone, as the build template
   already runs `next-change`; the `intent-spec.yml` template gains that clone step,
   since it has none today (R1).
6. `plugins/philosophy/templates/github/README.md`: reword the `intent-spec.yml` and
   `intent-build.yml` table rows to say each runs in two hops, `find` on the merge and
   the action on `find`'s dispatch, so a repository copying these templates doesn't
   read the old single-hop description as current (R1).
7. After this PR merges to `main` (the relay only exists once `main` has it, so this
   step can't run from the branch): push a throwaway smoke-test intent on its own
   branch, merged by hand the way `loop-smoke-test` verified the handovers before it,
   and watch `find` and `dispatch` run on that merge, then confirm the `spec` job's
   action step is reached under `repository_dispatch` rather than failing at
   `Unsupported event type` or at `checkHumanActor` (spec open question, Areas of
   concern 2). Record the run's URL as a follow-up comment on this PR. A
   `checkHumanActor` failure is informative, not a design error: it names the actual
   actor, and the fix is a one-line edit to `allowed_bots` in both workflows (and
   their templates); since this PR has already merged by then, that fix ships as its
   own quick follow-up PR under the same gate (`.github/` is a CODEOWNERS path
   however small the edit).

## Risks

- `gh api`'s bracket notation (`-f "client_payload[slugs]=$SLUGS"`) has to build the
  nested JSON object GitHub's dispatches endpoint expects, with `slugs` staying a
  string field rather than becoming a nested array; a malformed call either errors
  loudly or silently changes the payload shape the `spec`/`build` job reads with
  `fromJSON`. Step 7's live push is what proves this, not a local check.
- `find`'s diff filter and `dispatch-check`'s filter must stay identical (R5's third
  check exists only to re-derive what `find` already decided); a drift reopens the gap
  between what `find` found and what the dispatched job verifies. The tests pin
  `dispatch-check`'s side; `find`'s stays in the workflow.
- The `checkHumanActor` actor for a `GITHUB_TOKEN`-fired `repository_dispatch` rests on
  convention (spec Areas of concern 2), not on a run in this repository. Step 7 is
  where that gets settled, and the fix if it's wrong is scoped in this plan already.
- `fetch-depth: 0` is required wherever `dispatch-check` runs; a shallow checkout
  makes the ancestry checks fail closed (exit 2, not a false pass), which is the safe
  direction if it's missed, but would still block every run.
- `github.event.before` is all zeros on a branch's first push, and the 07-triggers
  plan noted `main` never sees that. A force-push to `main` or a recreated `main`
  history would, though, and `dispatch-check`'s zero-sha guard turns that into a hard
  failure rather than a skip, as for any other broken range. That is the correct
  direction for R5 (fail closed), not a gap, but it means a force-push to `main` would
  need its `intent-build`/`intent-spec` runs re-triggered by hand once `before` is
  sane again.

## Proof

- `python3 plugins/philosophy/scripts/run-check fast` exits 0 (philosophy's tests and
  lint, and `artefact-check intent`).
- `uv run --no-project --with pytest python -m pytest -q tests/test_dispatch_check.py`
  in `plugins/philosophy` passes, covering: a slug that isn't a plain name, an
  all-zero or short sha, a `sha` not on `main`, a `before` that isn't an ancestor of
  `sha`, and a range that doesn't touch the slug's trigger path, each refused with exit
  2; for `spec`, a `spec.md` on `main` or a `spec/<slug>` branch on the remote, not
  due with exit 1; a genuine merge of an unspecced intent, due with exit 0; and a push
  of several commits whose intent change is in an earlier commit, which passes.
- `python3 -c "import yaml,glob; [yaml.safe_load(open(p)) for p in glob.glob('.github/workflows/intent-*.yml') + glob.glob('plugins/philosophy/templates/github/intent-*.yml')]"` exits without error, confirming the edited workflows still parse.
- Step 7's smoke-test run, added as a comment on this PR once it merges: the `find`
  job's run (triggered by `push`), the `dispatch` job's run, and the `spec` (or
  `build`) job's run (triggered by `repository_dispatch`), with the action step shown
  reaching Claude's run rather than `Unsupported event type` or `checkHumanActor`.
