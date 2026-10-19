# Spec: answer round five's review findings on the self-running loop

Intent: [intent.md](intent.md), by Bruk Habtu. Status: draft. Merging this file into
`main` approves it.

Applied: standing constraints (`plugins/philosophy/constraints.md`: mechanise the
scaffolding, never weaken a check, no enforcement without the reason attached, split
by complexity and risk), `.github/CODEOWNERS` (what each change will wait on),
`plugins/philosophy/rules/code-design.md`, `plugins/philosophy/rules/python.md` and
`plugins/philosophy/rules/python-tests.md` for the script and hook changes. There is
no CLAUDE.md or REVIEW.md in this repository.

## Requirements

Evals
- **R1.** `subagent-gets-constraints` passes only if the `SubagentStart` hook ran: its
  prompt no longer contains the literal `[philosophy]` prefix or the words `Repository
  mode`, and a regex grader matches `^\[philosophy\] Repository mode: (owner|guest)` in
  the reply. The LLM grader is removed.
- **R2.** `review-checks-the-plan` has no LLM grader: `outside-plan-flagged` becomes a
  regex that matches a line naming `logger.py` marked Important.
- **R3.** `spec-flags-policy-conflict` no longer decides on the LLM grader
  `not-resolved-alone` alone: the property it checks (the spec does not settle the
  conflict itself) is expressed as a regex over the spec's Areas of concern, or the case
  keeps the LLM grader only beside a regex that must also pass.
- **R4.** The eval README states the rule: every case has a deterministic grader that
  can fail it, and no case fails on one LLM grade.

Review play and plan drift
- **R5.** The review play states that a file changed outside the plan's Files that
  change, or a plan step skipped, is Important, never a Nit.
- **R6.** A script, `plan-drift`, takes a build branch and prints each file its diff
  against `main` changes that the plan does not list (the plan file itself excepted).
  Exit 0 means none, 1 means some, 2 means it could not tell. A CI job runs it on
  `build/<slug>/NN` PRs and fails on exit 1, with the reason in its message.

Build play
- **R7.** A script, `commit-change`, stages exactly the paths the plan lists plus the
  plan, and makes a new commit. It never amends, never stages anything else, and
  refuses (with its reason) a path matching `*.pyc`, `__pycache__/` or `.gitignore`d
  files. The build play's `allowed-tools` drops `git add *` and `git commit *` in its
  favour.
- **R8.** The build branches from `origin/main` after `git fetch origin main`, not from
  HEAD. The build play's `allowed-tools` lists those two commands, and `next-change`
  reports `taken` the same as before.

gated-paths
- **R9.** `parse_codeowners` honours backslash escapes: `\#` is a literal `#` and `\ `
  a literal space inside a pattern, and only an unescaped `#` starts a comment. A
  test shows a rule written with each escape gates its path.

artefact-check
- **R10.** `<...>` placeholders fail the check in every field, including Author,
  Applied, Owner and R1, not only in open questions.
- **R11.** No artefact test reads `intent/self-running-loop`; each uses a fixture
  under `tests/`.

Guard
- **R12.** The deny reason for a plan that is not the branch's first commit says what
  is actually checked, and the guard checks it: the plan's commit is the first commit
  on the branch since `origin/main`, not merely present in HEAD.
- **R13.** Plan paths are normalised (`./`, repeated `/`, `..`) before comparison with
  an edited path, for the listed files and the repro tests alike.
- **R14.** A `**Repro:**` bullet (bold label) is read as a `Repro:` bullet.

Smaller
- **R15.** `branch-diff` refuses a branch name with a trailing newline (`\Z` or
  `fullmatch`).
- **R16.** `eval-diagnostics.py` reads missing keys without `KeyError` and closes
  every file it opens.
- **R17.** The evals workflow replaces `chmod -R a+rX /tmp` with a grant limited to the
  directory `--keep-temp` writes the traces to.

Every finding in the intent that this spec does not fix is rejected in the change that
would have fixed it, with its reason in that change's plan.

## Design

Each area is a separate change, ordered by risk: evals first, because a flaky required
check slows every change after it.

**Evals (R1-R4).** An LLM judging an LLM's reply is the flaw, so the fix is to grade
with a regex wherever the property is a string. The subagent case works because the
hook's output is a fixed line the model cannot produce unless it was given it: remove
the prompt's hint so the string is evidence. The review case's property is "logger.py
named on an Important line", which a regex on the review file states exactly. Where a
property is judgement (the policy-conflict case), the LLM grade stays as a second,
non-sole opinion. `--runs 1 --threshold 1.0` stays: lowering either would weaken the
check.

**Plan drift (R5, R6).** Chosen over either option alone: the review play says
outside-the-plan is Important so the model's grade stops varying, and a script holds
the line outside the model. The script is the check; the review is a second reader.
`plan-drift` reuses `artefact.listed_paths` and `branch-diff`'s name rules.

**Build play (R7, R8).** `allowed-tools` patterns are prefix globs and cannot restrict
arguments, so the safe surface is a script that takes none that matter. `commit-change`
reads the plan, stages its paths, commits. Branching from `origin/main` makes a build
independent of where the runner's HEAD happened to be.

**gated-paths, artefact-check, guard, smaller (R9-R17).** Each is a correction to
existing code with a test that fails before it. Logic stays in pure functions, I/O at
the edges, per `code-design`. `git log --reverse origin/main..HEAD` supplies the first
commit for R12.

### Delivery order

| Change | Delivers |
|---|---|
| 01 deterministic evals | R1, R2, R3, R4 |
| 02 plan drift outside the model | R5, R6 |
| 03 build play stages only the plan | R7, R8 |
| 04 CODEOWNERS escapes | R9 |
| 05 artefact-check placeholders and fixtures | R10, R11 |
| 06 guard reads the plan as it is | R12, R13, R14 |
| 07 smaller fixes | R15, R16, R17 |

Every change touches `evals/`, `scripts/`, `hooks/`, `.github/` or `skills/review/`,
which CODEOWNERS gates, so each build pauses on the owner's `@claude continue` once
the plan is read.

## Constraint mapping

| Intent constraint | Met by |
|---|---|
| Validation logic is a script, never an instruction to a model. | R1, R2, R3, R6, R7 |
| A check is never weakened to make it pass. | R1, R2, R3, R4, R10 |
| The review play stays gated by CODEOWNERS. | R5, R6 |

## Open questions

- [x] Is "a file outside the plan is always Important" the right rule for the review
      play, or should a plan-drift check outside the model hold that line instead?
      Both: R5 states the rule so the model agrees, and R6 holds it in a script so the
      model's grade cannot decide the merge.

## Areas of concern

1. **R6 needs a required status check, and that is a repository setting.** Owner:
   Bruk Habtu. Proposed: change 02 adds the CI job; the owner marks `plan-drift` a
   required check in branch protection after it has run once. Until then it informs
   and does not hold the merge.
2. **R3 keeps an LLM grader beside a regex, and "no case fails on one LLM grade" is a
   judgement about what counts as weakening a check.** Owner: Bruk Habtu. Proposed: if
   the policy-conflict property cannot be written as a regex without losing what the
   case catches, keep the LLM grader as advisory (reported, not failing) and keep the
   regex as the failing grader; the owner decides at the change 01 plan whether that is
   acceptable or the case should stay as is and run more than once.
3. **R7 removes `git add *` and `git commit *` from the build play, which also
   removes them for the rare change that needs a file the plan does not list.** Owner:
   Bruk Habtu. Proposed: that path already requires editing the plan in the same
   commit (build step 5), which `commit-change` covers because it stages what the
   plan lists.
