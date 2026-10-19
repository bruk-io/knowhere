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
for Python 3.9 and later. The board tools need the Backlog.md CLI (`backlog`) on PATH.

The constraints say the default branch is `main`. Git can hold that for new
repositories: `git config --global init.defaultBranch main`.

## What it does

| Piece | What it carries | When it reaches the model |
|---|---|---|
| `constraints.md` | The constraints that apply everywhere, including the order of the work loop | Every session, printed by the hook |
| `rules/code-design.md` | Every choice tells the reader something | First time a source file is touched, in owner mode |
| `rules/python.md` | Python dialect, the 3.15 floor, uv, ruff, mypy, pypeeker, with the core-and-shell and `match` examples | First time a `.py` or `pyproject.toml` is touched, in owner mode |
| `rules/python-tests.md` | The three test layers, defined by where the mocks start, and the order of work | First time a Python test file is touched, in owner mode |
| `rules/python-tests-unit.md` | Unit tests: one pure function, nothing mocked | First time a file under `tests/unit/` is touched, in owner mode |
| `rules/python-tests-integration.md` | Integration tests: the world faked at its edge and nowhere else | First time a file under `tests/integration/` is touched, in owner mode |
| `rules/python-tests-e2e.md` | End-to-end tests: the real world, nothing faked | First time a file under `tests/e2e/` is touched, in owner mode |
| `rules/board.md` | What each board key and section means | First time `backlog/` is touched or `backlog` runs |
| The step skills | One small skill per step of the work loop (below) | On demand |
| `philosophy:python-idioms` | The full idiom dictionary and the yielded-effects example | On demand |
| `philosophy:reviewer` | The agent that reviews a task and closes it, with `close-work` preloaded | When a task is handed to it |
| `scripts/board-check` | The board's conventions as checks | When a skill, the reviewer, or a person runs it |
| `scripts/close-task` | The close, the same way every time | When the reviewer closes a task |
| `scripts/migrate-layout` | Moves one piece of work from the old layout (intent task, spec doc) to named intent, spec and plan files | Once per piece of work, when upgrading from 0.6 |
| `scripts/record-check` | A check's own output on the task, word for word | When the worker or the reviewer runs a check |
| `docs/engineering-philosophy.md` | The reasoning | Never; the constraints point at it |
| `docs/board-examples.md` | Real board files, checked by the tests | When the board rule's reader is unsure of a shape |

Claude Code does not load a plugin's `CLAUDE.md` or `rules/`, so `hooks/context.py` does
that job. A rule arrives once per session and per subagent, and again after a compact
or a clear.

## The step skills

Each skill handles one step and follows one of Anthropic's AI-native SDLC plays. They
compose through the files they leave on the board, not by calling each other. The order
of the steps is in `constraints.md`, so it is in every session. To start new work, call
`/philosophy:capture-intent` or describe the problem.

| Skill | Step | Anthropic play |
|---|---|---|
| `capture-intent` | Write down what finished looks like | Capture as intent.md |
| `size-work` | Size by complexity, unknowns, and risk; split or spike | - |
| `accept-work` | Decide the work is ready to start | The human approval at each gate |
| `write-spec` | Write the requirements for large or cross-team work | Requirements and design (requirements) |
| `write-plan` | Order an intent into slices and derive its tasks from them | - |
| `record-decision` | Answer a design question as a decision | Requirements and design (design) |
| `plan-change` | Plan one change before editing | Plan mode as the default starting point |
| `delegate-work` | Subagents, parallel sessions, model and effort | Parallel sessions and subagents |
| `verify-work` | Check the work with the repository's own checks | Give Claude a feedback loop |
| `close-work` | Decide whether it closes, as someone who did not do it | AI in the PR review loop |
| `learn-from-work` | Turn lessons into tasks, rules, skills, checks, or evals | The CLAUDE.md, skills, evals, metrics |

Four plays are not skills, because they are configuration rather than judgment: evals
in CI, hooks as approval gates, CI/CD integration, and metric detection. This plugin
does not include them yet.

## The board tools

Whatever a skill used to check by reading is a script now, and the skills say when to
run it and how to read the result.

```sh
python3 scripts/board-check                       # the whole board
python3 scripts/board-check ready TASK-3          # also: plan <id>, close <id>
python3 scripts/board-check spec doc-1 --coverage
python3 scripts/board-check parallel TASK-3 TASK-4  # shared files, or one waiting on the other
python3 scripts/board-check route TASK-3            # the model and effort for it
python3 scripts/record-check TASK-3 --tier fast     # the declared check; output on the task
python3 scripts/record-check TASK-3 -- just lint    # any other check
python3 scripts/record-check TASK-3 --repro -- uv run pytest tests/test_bug.py
python3 scripts/close-task TASK-3 --notes "Verdict: closes. Two findings answered here."
```

`board-check` prints one finding per line, saying what is wrong and how to fix it, or a
JSON list with `--json`. It exits 0 when clean, 1 with findings, and 2 when it cannot
read the board. It understands two conventions the CLI doesn't: an open question is
settled when it is ticked or its line says `Carried forward:`, and a finish line has
moved when the criteria's wording differs from the commit that accepted the task.

`close-task` refuses, changing nothing, unless every criterion is ticked, every child is
done, and a moved finish line carries `finish-moved`. The criteria's wording and that
label must also match the last commit, so a review can tick criteria but not reword
them, however the file was edited, and a test recorded with `--repro` must be unchanged
since its commit. A bug needs a recorded repro, or a note starting `No repro:` that
says why. It then sets `Done` through the CLI, appends the notes, and commits the task
file alone.

`record-check` runs a command, prints its output, and appends the command, its exit
code and the last 60 lines of output to the task, exiting with the command's own code.
`--tier fast` and `--tier full` run the commands the repository declares in
`.claude/checks.json`:

```json
{"fast": "just test-changed", "full": "just check"}
```

They run from the board's own repository, and `close-task` refuses a task whose
declared checks changed since it was accepted, unless a note starting
`Checks changed:` says why. With `--repro` the command must fail and its test files
must be committed, and the note records that commit.

`hooks/guard.py` holds the close to that path. It denies setting `Done` any other way,
asks the person before `close-task` runs outside the reviewer, and keeps the reviewer's
shell off commands that change files or git history and off `backlog` commands that
change a task. The guard also denies `git init` without `-b main` unless git already
defaults to `main`.

The reviewer's own calls are allowed without a prompt: this plugin's scripts at this
plugin's path, the declared checks through `record-check --tier`, and the `backlog`
commands it may run. That is a deliberate trade. The close, including its commit, runs
with no person in the loop, because closing is decided by someone who did not do the
work and the reviewer is that someone; the notes say why it closed. Claude Code asks
before its Edit and Write tools change anything under `.claude/`, unless permissions are
bypassed, and a change to the declared checks after acceptance stops the close, so the
checks the reviewer runs are ones a person chose. Never add a permission rule that allows `record-check` with a command
after `--`: the rule would see only `record-check` and allow whatever follows. The
allow is read strictly and fails closed, so a command with a `$`, a backtick, a `#`, a
redirect, a wrapper such as `env`, or a script named by a relative path goes to the
usual permission prompt.

Everything else in the guard is a guardrail, not a security boundary: it fails open, it
does not see Backlog.md's MCP tools, and a shell can always write a file in a way it
doesn't recognise.

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

The tests cover the hooks, the board tools, and the cross-file references. They run the
hooks as subprocesses against throwaway repositories, and the board tools against a
real board built with the `backlog` CLI (skipped when it isn't installed). To run the
hooks and scripts under a specific interpreter, set `HOOK_PYTHON`.

`claude plugin validate --strict .` checks the manifests and the hook config.

## What it does not do

- **Most of the Python standard is prose.** ruff, mypy, and pypeeker are named in
  `rules/python.md`, but nothing here runs them. The uv guard, ruff and ast-grep on
  edit live in the `bruk` and `idiom` plugins.
- **Parts of the work loop are untried.** `board-check`, `close-task`, `record-check`,
  the reviewer agent, the guard, the `finish-moved` label, checks in tiers, and specs
  are written and tested but not yet used on real work. Intents, the accept step, and the board
  conventions have been used since October 2026.
- **It does not cover authoring Claude Code extensions.** The work loop says where a
  lesson goes and how work is handed off. How to write a good skill, rule, agent or hook
  is the `authoring-kit` plugin's job, so install both.
- **It overlaps the `bruk` and `idiom` plugins.** With those enabled as well, the same
  ground is covered twice in different words. Use one or the other.

## Planned for 0.5.0

- **Programmatic enforcement of the Python rules with pypeeker.** Then `rules/python.md`
  shrinks to the judgement lines and a pointer to `philosophy:python-idioms`, and the
  checkable lines become checks with their reasons in the messages.
- **The checkable lines of the `rules/python-tests*.md` rules** go with them: doubles only under
  `tests/integration/`, the integration suite run twice, and the retired "functional
  test" and "adapter test".
- **Prose checks:** Canadian spelling and no em dashes, as a hook in owner mode.
- **A `Stop` hook for the fast tier,** so "before saying a task is done" doesn't depend
  on `verify-work` triggering.
- **A worker agent** carrying what `delegate-work` can only ask for: its own worktree,
  no scheduling, and no sizing.
- **`rules/code-design.md` and `rules/python.md` overlap,** and the first says the
  community's style outranks mine while the second is my dialect. The `python.md` shrink
  settles which wins.

## Remove

```sh
claude plugin uninstall philosophy@knowhere
```
