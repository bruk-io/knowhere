---
description: Write intent/<slug>/spec.md from an accepted intent - numbered requirements, the design and its delivery order, a constraint mapping, and areas of concern - with the policy in force applied and listed. Runs when an intent merges, in CI or by hand.
argument-hint: <slug>
arguments: [slug]
disable-model-invocation: true
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artefact-check" *), Bash(git checkout -b spec/*), Bash(git add intent/*), Bash(git commit *), Bash(git push -u origin HEAD), Bash(gh pr create *)
---

# Write the spec

Requirements and design are one pass, with the policy applied while the spec is written
rather than found in review weeks later. The spec is where the owner approves the
architecture, so its PR always waits for them.

1. Read `intent/$slug/intent.md`. It must be accepted: on `main`, or with a status that
   says so. A draft intent gets no spec.
2. Read the policy in force: CLAUDE.md, the rules and skills that apply to what the
   intent touches, `REVIEW.md`, and any architecture definitions (LikeC4 models,
   boundary configuration). Name each one you applied on the `Applied:` line.
3. Write `intent/$slug/spec.md` from `${CLAUDE_PLUGIN_ROOT}/templates/spec.md`:
   - Requirements: discrete and checkable, numbered R1 to Rn with no gaps.
   - Design: the approach and the decisions behind it. Its `### Delivery order` table
     splits the work into changes, `NN <title>` and the R-numbers each delivers. Each
     change is one PR's worth, ordered so each builds on the last.
   - Constraint mapping: one row per intent constraint, naming what meets it.
   - Open questions: carry each one from the intent. Tick it with its answer, or say
     `Carried forward:` and why it can wait.
   - Areas of concern: where two policies conflict, or a requirement strains one, flag
     it with its owner and a proposal. Never resolve a conflict between policies
     yourself; that is the owner's call.
4. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artefact-check" intent/$slug` and fix
   what it reports.
5. On a branch `spec/$slug`, commit the spec alone, push it with exactly
   `git push -u origin HEAD`, and open a PR that says merging it approves the spec and
   starts the build.

Never ask a question mid-run. Anything that needs a person goes in Open questions or
Areas of concern.
