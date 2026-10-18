---
description: Build the next change of an approved spec - commit its plan first, implement it, run the repository's fast check, and open a PR with the evidence. Runs when a spec or a change merges, in CI or by hand, and continues a build its owner unblocked.
argument-hint: <slug> [auto-merge]
arguments: [slug, merge]
disable-model-invocation: true
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/next-change" *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gated-paths" *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-check" *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artefact-check" *)
---

# Build the next change

One change per PR: its plan first, then its code, then the evidence. The scripts make
the mechanical calls; the plan and the code are yours.

If you are on a `build/$slug/NN` branch whose open PR holds only the plan, its owner
has unblocked it: go to step 5.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/next-change" intent/$slug`. `done` or
   `taken` means stop and say so. `build NN <title> <R-numbers>` names the change.
2. From `main`, create the branch `build/$slug/NN`.
3. Read the intent, the spec, and the code the change touches. Write
   `intent/$slug/plans/NN-<short-name>.md` from `${CLAUDE_PLUGIN_ROOT}/templates/plan.md`:
   every file that changes, one backticked path per bullet; the order of work, each
   step naming its requirement; the risks; and the proof, the checks that will show it
   works. Someone who never saw this session must be able to implement from it. Run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artefact-check" intent/$slug`, then commit the
   plan alone as the branch's first commit.
4. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gated-paths" <the plan>`. If it lists a
   path, push, open the PR with the plan and those paths, ask the owner there to reply
   `@claude` to continue, and stop.
5. Implement in the plan's order. Edit only the files the plan lists. If another file
   turns out to need changing, add it to the plan in the same commit and say why in the
   PR. A drift bigger than that is a reason to stop and say so, not to push on.
6. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-check" fast` until it exits 0. Fix
   the code, never the check: a test the plan names as a repro stays as it is.
7. Commit, push, and open the PR, or update it: the R-numbers it delivers, a link to
   the plan, and the block `run-check` printed, exactly as printed. If `$merge` is
   `auto-merge`, turn on auto-merge with `gh pr merge --auto --merge`.

Never approve or merge the PR yourself. The required checks decide, and the owner
where CODEOWNERS says so.
