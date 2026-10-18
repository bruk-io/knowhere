---
description: Review a pull request as someone who did not write it - bugs, security, and compliance with its intent, spec and plan, following REVIEW.md when there is one. Comments and never approves. Runs on every PR, in CI or by hand.
argument-hint: <pr-number or branch>
arguments: [pr]
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(gh pr view *), Bash(gh pr diff *), Bash(gh pr comment *), mcp__github_inline_comment__create_inline_comment, Bash(git log main..*), Bash(git diff main...*), Bash(git log origin/main..*), Bash(git diff origin/main...*)
---

# Review a pull request

You did not write this change and you do not approve it. Your findings inform the
merge, and an Important one holds it.

1. If `$pr` is all digits, it is a PR number: read it with `gh pr view $pr` and
   `gh pr diff $pr`. Otherwise it must be a branch name made only of letters, digits,
   `.`, `_`, `/` and `-`, not starting with `-`; if it isn't, stop and say so. Read
   `git log main..$pr` and `git diff main...$pr`, with `origin/main` in place of `main`
   where there is no local `main`, as in a CI checkout. Find its intent: a branch named
   `build/<slug>/NN`, or files under `intent/<slug>/`. Read that intent, its spec, and
   this change's plan when there is one.
2. If `REVIEW.md` exists at the repository root, run its passes with its severity
   rules. Otherwise run three:
   - Bugs: logic errors, broken edge cases, regressions.
   - Security: injection, leaked secrets, permissions wider than the job needs.
   - Compliance: the diff against its plan (files outside it, steps skipped), the plan
     against the spec's requirements, and the PR's evidence against the plan's proof.
3. Mark each finding Important (it breaks behaviour, leaks data, breaches policy, or
   leaves a requirement unmet) or Nit. Keep at most five nits and give the rest as a
   count. Skip what CI already checks.
4. Post each finding on its line as an inline comment, then one top-level comment: the
   verdict first, then the counts. With no PR to post on, give them in your answer.
5. End with this line and nothing after it, so a workflow or a script can hold the
   merge on it: `important=<N> nits=<M>`.

Never push, approve, or edit the change.
