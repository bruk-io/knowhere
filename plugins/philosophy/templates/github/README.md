# Workflows for a repository that runs the loop

Copy these into `.github/workflows/`, with `templates/CODEOWNERS` as
`.github/CODEOWNERS`, to run the loop in another repository:

| File | Runs | On |
|---|---|---|
| `intent-spec.yml` | `/philosophy:spec <slug>` | A merged intent with no spec yet |
| `intent-build.yml` | `/philosophy:build <slug> auto-merge` | A merged spec or change, when `next-change` says to build |
| `build-continue.yml` | `/philosophy:build <slug>` on the PR's branch | The owner's `@claude continue` on a build PR |
| `claude-review.yml` | `/philosophy:review <pr>` | Every PR; fails while it has an Important finding |

Before they work:

- Replace `OWNER` with the owner's GitHub login.
- Add the `CLAUDE_CODE_OAUTH_TOKEN` secret (`claude setup-token`, then
  `gh secret set CLAUDE_CODE_OAUTH_TOKEN`), and give the Claude GitHub app access.
- Declare the repository's checks in `.claude/checks.json`, and adjust the build's
  `--allowedTools` to the commands they run.
- Protect `main`: require a PR, code-owner review, and the review as a required check.
  Turn on "Allow auto-merge".

The build workflow fetches the plugin's scripts from knowhere. Pin the clone to a tag
once the plugin has one you trust.
