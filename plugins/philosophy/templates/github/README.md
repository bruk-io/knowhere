# Workflows for a repository that runs the loop

Copy these into `.github/workflows/`, with `templates/CODEOWNERS` as
`.github/CODEOWNERS`, to run the loop in another repository:

| File | Runs | On |
|---|---|---|
| `intent-spec.yml` | `/philosophy:spec <slug>` | A merged intent with no spec yet, in two hops: `find` on the merge, the action on `find`'s dispatch |
| `intent-build.yml` | `/philosophy:build <slug> auto-merge` | A merged spec or change, when `next-change` says to build, in the same two hops |
| `build-continue.yml` | `/philosophy:build <slug>` on the PR's branch | The owner's `@claude continue` on a build PR |
| `claude-review.yml` | `/philosophy:review <pr>` | A PR opened as ready, or moved from draft to ready; fails while it has an Important finding |
| `loop-bands.yml` | `band-check`, then a read-only diagnosis or `/philosophy:intent` | Daily; with `templates/bands.yaml` at the root |

Before they work:

- Replace `OWNER` with the owner's GitHub login.
- Add the `CLAUDE_CODE_OAUTH_TOKEN` secret (`claude setup-token`, then
  `gh secret set CLAUDE_CODE_OAUTH_TOKEN`), and give the Claude GitHub app access.
- Declare the repository's checks in `.claude/checks.json`, and adjust the build's
  `--allowedTools` to the commands they run.
- Protect `main`: require a PR, code-owner review, the full check and the evals as
  required checks, and conversation resolution, so every review comment is answered and
  resolved before merge. Turn on "Allow auto-merge".
- Run the required checks on `ready_for_review` as well as the default `pull_request`
  events. A build's own pushes are made as `github-actions[bot]`, and the runs they
  start can wait for approval; the build marks its PR ready as the Claude app after its
  last push, so the checks run on its final commit.

These templates keep `actions/checkout`'s credential, because `dispatch-check` and
`next-change` read the remote's branches before the action runs, and a private
repository needs that read authenticated: a failed read would count as no branch and
let a second spec or build start. The cost is that a build's own pushes are made as
`github-actions[bot]`, and their `pull_request` runs wait for approval; the
`ready_for_review` runs above are the ones that count. knowhere is public, so its own
workflows check out without the credential and push as the Claude app.

A build whose plan touches `.github/workflows/` can't be built in CI: the Claude app's
token has no `workflows` permission, so its push is refused, and the owner runs that
build by hand instead.

The build workflow fetches the plugin's scripts from knowhere. Pin the clone to a tag
once the plugin has one you trust.

Every action is pinned to a commit, with its release as a comment
(`actions/checkout@<sha> # v4.4.0`), because these jobs hold the token and a tag can be
moved. To move the pins to each major tag's latest release, run knowhere's
`.github/scripts/pin-actions.py --bump` on the workflow files, or let Dependabot do it,
as knowhere's `.github/dependabot.yml` does; both keep the comment.
