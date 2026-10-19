---
description: Answer the review on a build PR, once - fix or decline each finding with its reason, reply, and resolve the thread - so a PR whose findings are settled merges on its checks. Runs when the review finishes on a build PR, in CI or by hand.
argument-hint: <pr-number>
arguments: [pr]
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/review-findings" *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/answer-thread" *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/commit-change" *), Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-check" *), Bash(git push -u origin HEAD), Bash(gh pr view *), Bash(gh pr diff *), Bash(gh pr comment *)
---

# Respond to the review

You built this change; the review is someone else's reading of it. Answer every finding
once: fix it, or decline it and say why. You never approve or merge, and you never ask
for another review: this is one round, and what it leaves goes to the owner.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/review-findings" $pr`. Exit 1 means
   nothing needs an answer: stop. Exit 2 means GitHub couldn't be read: stop and say so.
   Exit 0 prints the open threads and the review's summary as JSON.
2. Read the PR with `gh pr view $pr` and `gh pr diff $pr`, and its plan,
   `intent/<slug>/plans/NN-*.md` for the PR's `build/<slug>/NN` branch.
3. Decide each finding, the summary's included:
   - **Fix it** when it's right and the fix stays inside the plan. A fix that needs a
     file the plan doesn't list adds it to the plan in the same commit, as the build
     play says; the guard holds you to that.
   - **Decline it** when it's wrong, out of the change's scope, or already settled by
     the spec or the plan, with the reason.
   - **Leave it for the owner** when settling it would change the spec or a path
     CODEOWNERS gates: don't fix or resolve it; say so in your reply.
4. Make the fixes, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-check" fast` until it
   exits 0, commit them with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/commit-change"
   <plan> -m <message>`, and push with exactly `git push -u origin HEAD`.
5. Answer each thread: write the reply to a file (what changed and the commit, or why
   not) and run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/answer-thread" $pr <thread>
   <comment> --body-file <file>`, which replies and resolves it. A thread left for the
   owner gets a reply with `gh pr comment` instead, so it stays open.
6. Answer the findings that came only in the summary in one `gh pr comment`, each
   with what was done or why not.

Never approve, merge, edit the review play, or mark the PR ready again.
