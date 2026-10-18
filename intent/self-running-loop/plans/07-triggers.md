# Plan: the triggers

Spec: [spec.md](../spec.md), change 07. Delivers R8 and R9.

## Files that change

- `intent/self-running-loop/plans/07-triggers.md`
- `.github/workflows/intent-spec.yml`
- `.github/workflows/intent-build.yml`
- `.github/workflows/build-continue.yml`
- `.github/workflows/claude.yml`
- `plugins/philosophy/skills/build/SKILL.md`
- `plugins/philosophy/templates/github/intent-spec.yml`
- `plugins/philosophy/templates/github/intent-build.yml`
- `plugins/philosophy/templates/github/build-continue.yml`
- `plugins/philosophy/templates/github/claude-review.yml`
- `plugins/philosophy/templates/github/README.md`
- `plugins/philosophy/README.md`
- `plugins/philosophy/CHANGELOG.md`

## Order of work

1. `intent-spec.yml`: a push to `main` that adds or changes `intent/*/intent.md` runs
   `/philosophy:spec <slug>` for each intent that has no spec yet, one job per intent
   (R8). Its PR touches a gated path, so it waits for the owner.
2. `intent-build.yml`: a push to `main` that changes `intent/*/spec.md` or
   `intent/*/plans/*.md` asks `next-change` which change is next, and only when it says
   `build` runs `/philosophy:build <slug> auto-merge`. A concurrency group per intent
   keeps one build at a time (R9).
3. `build-continue.yml`: the owner's `@claude continue` on a build PR runs the build
   again on that PR's branch, where it picks up from the plan. `claude.yml` leaves
   those comments to it, and the build skill asks for exactly that reply.
4. Templates of the four workflows for another repository to copy, with the scripts
   fetched from knowhere rather than read from the repository (spec area of concern 8).
5. README and changelog.

## Risks

- The chaining traps (spec area of concern 3) are unverified until a throwaway intent
  goes through: a merge made by auto-merge must start the next workflow, and the
  review must run on `claude[bot]`'s PRs. This change can't verify either on its own;
  the PR says how to.
- Auto-merge needs the repository's "Allow auto-merge" setting, which is the owner's
  to turn on.
- The build runs with a tool list; a step the list misses fails in CI rather than
  asking. The list covers git, the plugin's scripts, the check script, and the `gh pr`
  calls the play makes.
- `github.event.before` is all zeros on a branch's first push; on `main` it never is.

## Proof

- Each workflow parses, declares `permissions`, and names a concurrency group where it
  builds.
- The "find" step's script, run against this repository's history, picks
  `self-running-loop` for the push that added its spec, and nothing for a push that
  touched neither.
- `next-change` on this intent prints what the build step would act on.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0.
