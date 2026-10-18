# Evals

Cases for `claude plugin eval`, one folder per play (`evals/<play>/<case>/`). Each case
checks one behaviour the loop depends on, and each came from something that went wrong
or nearly did:

| Case | What it checks | Where it came from |
|---|---|---|
| `build/build-plans-first` | `/philosophy:build` commits its plan first, as `plan: 01`, before any code (read from git's reflog; the guard keeps code out of the plan commit) | brig-seed: implementers dispatched by Workflow scripts never planned |
| `spec/spec-flags-policy-conflict` | `/philosophy:spec` flags a conflict between the intent and CLAUDE.md as an area of concern with an owner, instead of settling it | The playbook's design play: policy conflicts are the owner's call |
| `review/review-checks-the-plan` | `/philosophy:review` reports a file outside the plan as Important and doesn't approve | The review on knowhere#13 |
| `subagent/subagent-gets-constraints` | A subagent was given the constraints, which only the `SubagentStart` hook can do | brig-seed: subagents never saw the loop |

Every case runs in a small repository that `_scaffold/demo-repo.sh` builds: git on
`main`, a bare remote as `origin`, and one intent, `demo`, taken as far as the case
needs. There is no GitHub, so a play pushes to `origin` and stops short of a PR.

Run from the plugin root. The scaffolds run only with `--scaffold`:

```
claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write Edit --runs 1 --ablation none
claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write Edit --tag build
```

In knowhere, `.github/workflows/philosophy-evals.yml` runs the suite once per case on
every PR that changes the plugin, and fails if any case fails. An incident in the loop
becomes a case here, and it stays.

The CI run has `CLAUDE_CODE_OAUTH_TOKEN` in its environment while it runs the PR's own
scaffolds and gives a model Bash. That is acceptable only because the job skips PRs
from forks, the cases run in an OS sandbox, and anyone who can open a same-repository
PR could already edit the workflow. Keep all three true.
