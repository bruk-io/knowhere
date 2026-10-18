# philosophy

How I build software, as one Claude Code plugin.

## Install

It is published in the knowhere marketplace:

```sh
claude plugin marketplace add bruk-io/knowhere
claude plugin install philosophy@knowhere
```

The same two steps work inside Claude Code as `/plugin marketplace add bruk-io/knowhere`
and `/plugin install philosophy@knowhere`. Start a new session afterwards.

The hooks and scripts run under `python3` and need nothing installed. They are written
for Python 3.9 and later. The plays use `git` and the GitHub CLI (`gh`).

The constraints say the default branch is `main`. Git can hold that for new
repositories: `git config --global init.defaultBranch main`.

## What it does

| Piece | What it carries | When it reaches the model |
|---|---|---|
| `constraints.md` | The constraints that apply everywhere, including the work loop | Every session and every subagent, from the hook |
| `rules/code-design.md` | Every choice tells the reader something | First time a source file is touched, in owner mode |
| `rules/python.md` | Python dialect, the 3.15 floor, uv, ruff, mypy, pypeeker, with the core-and-shell and `match` examples | First time a `.py` or `pyproject.toml` is touched, in owner mode |
| `rules/python-tests.md` | The three test layers, defined by where the mocks start, and the order of work | First time a Python test file is touched, in owner mode |
| `rules/python-tests-unit.md` | Unit tests: one pure function, nothing mocked | First time a file under `tests/unit/` is touched, in owner mode |
| `rules/python-tests-integration.md` | Integration tests: the world faked at its edge and nowhere else | First time a file under `tests/integration/` is touched, in owner mode |
| `rules/python-tests-e2e.md` | End-to-end tests: the real world, nothing faked | First time a file under `tests/e2e/` is touched, in owner mode |
| The four plays | One command per play of the loop (below) | When a person or a workflow runs it |
| `philosophy:python-idioms` | The full idiom dictionary and the yielded-effects example | On demand |
| `templates/` | The shapes of an intent, a spec and a plan | When a play writes one |
| `scripts/artefact-check` | The artefacts' shapes as checks | When an artefact is written, in CI, or when run |
| `scripts/next-change`, `gated-paths`, `run-check` | The build's mechanical decisions | When the build runs them |
| `docs/engineering-philosophy.md` | The reasoning | Never; the constraints point at it |

Claude Code does not load a plugin's `CLAUDE.md` or `rules/`, so `hooks/context.py` does
that job. The constraints arrive at the start of each session and each subagent, and a
rule arrives once per session and per subagent, and again after a compact or a clear.

## The loop

The loop follows Anthropic's AI-native SDLC playbook. Each stage commits a file the next
stage reads, each handover is a merge, and the merge is the approval. An intent lives at
`intent/<slug>/` in the repository that owns it, and that repository runs it.

| Play | Command | Leaves | Anthropic play |
|---|---|---|---|
| Capture the intent | `/philosophy:intent <slug>` | `intent.md`, in a PR | Capture as intent.md |
| Write the spec | `/philosophy:spec <slug>` | `spec.md`, in a PR | Requirements and design |
| Build one change | `/philosophy:build <slug> [auto-merge]` | `plans/NN-<change>.md`, then the code, in a PR | Plan mode, give Claude a feedback loop |
| Review a PR | `/philosophy:review <pr>` | Findings on the PR, never an approval | AI in the PR review loop |

Each play is a skill with model invocation turned off, so it runs only when a person or
a workflow invokes it. The judgement is the model's; the mechanical steps are scripts:

```sh
python3 scripts/artefact-check intent               # every intent's shape
python3 scripts/next-change intent/<slug>           # build NN, taken NN, or done
python3 scripts/gated-paths intent/<slug>/plans/01-x.md   # plan files CODEOWNERS gates
python3 scripts/run-check fast                      # the declared check, as evidence
```

`artefact-check` prints one finding per line, saying what is wrong and how to fix it, or
a JSON list with `--json`. It exits 0 when clean, 1 with findings, and 2 when it cannot
read a file. It runs on its own whenever Claude writes an intent, a spec or a plan.

`next-change` reads the spec's delivery order: the first change with no plan is next,
and it is taken while a `build/<slug>/NN` branch for it exists on the remote, so one
intent builds one change at a time. It reads branches, not PRs, so it needs no GitHub;
abandon a build by deleting its branch. `run-check` runs the command a repository declares
in `.claude/checks.json` and prints the command, its output's tail and its exit code:

```json
{"fast": "just test-changed", "full": "just check"}
```

`hooks/guard.py` holds a build to its plan. On a `build/<slug>/NN` branch, only the
change's plan can be written until it is committed; after that, an Edit, Write or notebook edit to a
file the plan doesn't list is denied with the fix in the reason, and so is a repro test the
plan's Proof names once it is committed. It also denies `git init` without `-b main`
unless git already defaults to `main`. It is a guardrail, not a security boundary: it
fails open, and a shell command can still write a file.

## Owner mode and guest mode

The hook decides the mode from the git origin of the repository holding the file being
touched, and says which mode the session started in on its first line.

- **Owner:** the origin matches a line in `owners.txt`, or the repository has no origin.
- **Guest:** everything else. The code and Python rules are not loaded.

Edit `owners.txt` to add an organisation or a single repository.

## Tests

```sh
uv run --with pytest pytest tests
```

The tests cover the hooks, the scripts, and the cross-file references. They run the
hooks and commands as subprocesses against throwaway repositories. To run them under a
specific interpreter, set `HOOK_PYTHON`.

`claude plugin validate --strict .` checks the manifests and the hook config.

`evals/` holds the eval suite, one case per behaviour the loop depends on; its README
says how to run it. In knowhere it runs on every PR that changes the plugin.

## What it does not do

- **Most of the Python standard is prose.** ruff, mypy, and pypeeker are named in
  `rules/python.md`, but nothing here runs them. The uv guard, ruff and ast-grep on
  edit live in the `bruk` and `idiom` plugins.
- **The loop is new.** The plays and scripts are written and tested, and the intent
  that built them is the first to go through. The workflows that run the plays on a
  merge, the gates, the evals and the metrics are still being built.
- **It does not cover authoring Claude Code extensions.** How to write a good skill,
  rule, agent or hook is the `authoring-kit` plugin's job, so install both.
- **It overlaps the `bruk` and `idiom` plugins.** With those enabled as well, the same
  ground is covered twice in different words. Use one or the other.

## Planned

- **The rest of the self-running loop** (`intent/self-running-loop/spec.md` in
  knowhere): CODEOWNERS and the required checks as gates, workflows that run the plays
  on a merge, and metrics with control bands.
- **Programmatic enforcement of the Python rules with pypeeker.** Then `rules/python.md`
  shrinks to the judgement lines and a pointer to `philosophy:python-idioms`, and the
  checkable lines become checks with their reasons in the messages.
- **The checkable lines of the `rules/python-tests*.md` rules** go with them: doubles
  only under `tests/integration/`, the integration suite run twice, and the retired
  "functional test" and "adapter test".
- **Prose checks:** Canadian spelling and no em dashes, as a hook in owner mode.
- **`rules/code-design.md` and `rules/python.md` overlap,** and the first says the
  community's style outranks mine while the second is my dialect. The `python.md` shrink
  settles which wins.

## Remove

```sh
claude plugin uninstall philosophy@knowhere
```
