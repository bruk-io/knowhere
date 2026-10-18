---
description: Build the next change of an approved spec - commit its plan first, implement it, run the repository's fast check, and open a PR with the evidence. Runs when a spec or a change merges, in CI or by hand, and continues a build its owner unblocked.
argument-hint: <slug> [auto-merge]
arguments: [slug, merge]
disable-model-invocation: true
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/next-change" *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gated-paths" *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-check" *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artefact-check" *), Bash(git checkout -b build/*), Bash(git add *), Bash(git commit *), Bash(git push -u origin HEAD), Bash(gh pr create *), Bash(gh pr edit *), Bash(gh pr ready *), Bash(gh pr checks *), Bash(gh pr merge --auto *)
---

# Build the next change

One change per PR: its plan first, then its code, then the evidence. The scripts make
the mechanical calls; the plan and the code are yours.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/next-change" intent/$slug`. `done` or
   `taken` means stop and say so. `build NN <title> <R-numbers>` names the change.
   `continue NN <title> <R-numbers>` means you are on that change's build branch and its
   plan is committed. A build comes back to its branch only when its owner has
   unblocked it, by replying `@claude continue` on its PR, which runs this in CI, or by
   running it by hand, so go to step 5.
2. From `main`, create the branch `build/$slug/NN`.
3. Read the intent, the spec, and the code the change touches. Write
   `intent/$slug/plans/NN-<short-name>.md` from `${CLAUDE_PLUGIN_ROOT}/templates/plan.md`:
   every file that changes, one backticked path per bullet; the order of work, each
   step naming its requirement; the risks; and the proof, the checks that will show it
   works. Someone who never saw this session must be able to implement from it. Run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artefact-check" intent/$slug`, then commit the
   plan alone as the branch's first commit, with the message `plan: NN <title>`.
4. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gated-paths" <the plan>`. Exit 0 means
   nothing is gated: go on. Exit 2 means it couldn't read the plan: stop and say so.
   Exit 1 lists the gated paths: push, open the PR as a draft (`gh pr create --draft`)
   with the plan and those paths, ask the owner there to reply `@claude continue` once
   they have read the plan, and stop.
5. Implement in the plan's order. Edit only the files the plan lists; the guard denies
   the rest. If another file turns out to need changing, add it to the plan in the same
   commit and say why in the PR, and run `gated-paths` on the plan again: a file it
   newly lists is gated, so commit, push, name it on the PR, ask the owner to reply
   there, and stop, as in step 4. A drift bigger than that is a reason to stop and say
   so, not to push on. For a bug, first write the test that reproduces it, name it on a
   `Repro:` line under Proof, confirm it fails for the expected reason, and commit it.
6. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-check" fast` until it exits 0. Fix
   the code, never the check: a test the plan names as a repro stays as it is.
7. Commit, push, and open the PR as a draft (`gh pr create --draft`), or update it: the
   R-numbers it delivers, a link to the plan, and the block `run-check` printed,
   exactly as printed.
8. Mark the PR ready with `gh pr ready`, which starts the review; if it is already
   ready, run `gh pr ready --undo` first, so the review runs on the finished work. Wait
   for its checks with `gh pr checks --watch`, so the review's comments are on the PR
   before anything can merge. If `$merge` is `auto-merge`, turn on auto-merge with
   `gh pr merge --auto --merge`.

Push with exactly `git push -u origin HEAD`, so a push only ever updates this branch.

Never approve the PR or merge it yourself. Turning on auto-merge is allowed: it asks
GitHub to merge once the required checks pass, every review conversation is resolved,
and CODEOWNERS asks for no one, so the checks and the review decide, and the owner where
CODEOWNERS says so. In CI the workflow runs this with
the Claude app's token, so that merge starts the next workflow (spec R11).
