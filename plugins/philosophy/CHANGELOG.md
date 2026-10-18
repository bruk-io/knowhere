# Changelog

## 0.5.0

The work loop follows Anthropic's AI-native SDLC playbook, and the Backlog.md board is
gone. Built from `intent/self-running-loop/` in knowhere; changes 01 to 07 of its spec.

### Added

- **The four plays as commands:** `/philosophy:intent`, `/philosophy:spec`,
  `/philosophy:build` and `/philosophy:review`, skills with model invocation off, so a
  play runs only when a person or a workflow invokes it. Each stage commits a file the
  next reads (`intent/<slug>/intent.md`, `spec.md`, `plans/NN-<change>.md`), and each
  handover is a merge.
- **`templates/`** for the intent, the spec and the plan.
- **`scripts/artefact-check`** asserts each artefact's shape, and runs as a hook when
  Claude writes one and as a PR check in knowhere.
- **`scripts/next-change`, `gated-paths` and `run-check`**, the build's mechanical
  calls: which change is next (one at a time per intent), which plan files CODEOWNERS
  gates, and the declared check's output as evidence.
- **Subagents get the constraints.** `SessionStart` never fires for a subagent, so the
  context hook answers `SubagentStart` with the same text.
- **An eval suite** in `evals/`: a build commits its plan first, a spec flags a policy
  conflict instead of settling it, a review reports a file outside the plan, and a
  subagent gets the constraints. `/philosophy:review` also takes a branch, for runs
  without GitHub, and reads it through `scripts/branch-diff`, which accepts only a plain
  branch name.
- **`templates/github/`**: the workflows that run the plays on a merge (spec on an
  intent, the next build on a spec or a change, the review on every PR, and the owner's
  `@claude continue`), for a repository to copy.
- **`templates/CODEOWNERS`** for a repository to copy: intents, specs, the gates and
  architecture definitions wait for the owner, and the rest merges on its checks.
- **The guard holds a build to its plan.** On a `build/<slug>/NN` branch, nothing but
  the plan can be written until it is committed, a file the plan doesn't list is denied, and
  a committed repro test named on a `Repro:` line of the plan's Proof can't be edited.

### Removed

- **The board:** `board.py`, `board-check`, `close-task`, `record-check`,
  `rules/board.md` and `docs/board-examples.md`.
- **The reviewer agent and the ten step skills** (`capture-intent`, `size-work`,
  `accept-work`, `write-spec`, `record-decision`, `plan-change`, `delegate-work`,
  `verify-work`, `close-work`, `learn-from-work`). Process that was left to the model
  to discover is now a command that is invoked, and closing is a merge.
- **The guard's close and reviewer logic.** It keeps `git init -b main`.

### Changed

- **"Doing the work" in `constraints.md`** describes the new loop, the gates, and where
  a lesson goes: a mistake made twice into CLAUDE.md, an incident into an eval case.

## 0.4.6

- **Published in the knowhere marketplace** (`bruk-io/knowhere`, `plugins/philosophy/`),
  which is now its source. Install with `philosophy@knowhere`.
- **The test rule is split by layer.** `rules/python-tests.md` keeps how to choose a
  layer and the order of work, for any test file. `python-tests-unit.md`,
  `python-tests-integration.md` and `python-tests-e2e.md` each carry one layer's
  constraints and arrive only when a file in that layer's directory is touched.
- **Three test layers, defined by where the mocks start.** `rules/python-tests.md` had
  four layers (unit, functional, adapter, e2e) and retired "integration test", while the
  philosophy document makes integration tests the default for new behaviour. The rule now
  agrees with the document: a unit test tests one function, which is pure, so nothing is
  mocked; an integration test runs the program's own parts together, with the world faked
  at its edge and nowhere else; an e2e test runs against the real world with nothing
  faked, the whole program or one gateway against the real thing it wraps. "Functional
  test" and "adapter test" are retired, and the README's planned item about the
  disagreement is gone.
- **The reviewer's preloaded skill is an indented list item again,** the form
  `test_agent_preloads_resolve` reads; the upload had flattened it and the test failed.

## 0.4.5

- **The Python rule carries the examples from the idioms document.** The pure core, thin shell retry loop
  with its one-line tests, the `match` ending in `assert_never`, and the short examples
  for `sentinel`, `copy.replace`, generics, flattening and the bare-name capture were
  only in the `python-idioms` reference, which loads when the skill triggers and the
  reference is read. The rule arrives the first time a Python file is touched, so the
  examples now reach every owner-mode Python session. "Shape of the code" is split into
  "Core and shell" and "Classes and names" so the example sits beside the bullets it
  shows. The reference is unchanged.

## 0.4.4

- **Restored the workflow lines 0.4.3 cut from `learn-from-work` and `delegate-work`.**
  They mention hooks and subagents, but they are steps of the work loop, most of them
  from the bh-02 usage feedback: where each lesson goes, that a worker's brief carries
  the task and not its process, the delegation depth budget, and when a recurring
  hand-off earns a subagent definition. The line between the plugins: philosophy says
  where a lesson goes and how work is handed off; authoring-kit says how to build the
  skill, rule, or hook well. `rules/agent-tooling.md` was only the second kind, so its
  removal stands.

## 0.4.3

How to author Claude Code extensions belongs to the `authoring-kit` plugin, so it is
gone from here.

### Removed

- **`rules/agent-tooling.md`.** It matched the same files as authoring-kit's rules and
  restated its standard, so one touch delivered both. Four of its lines are not in
  authoring-kit yet and move there if they still matter: add a skill or rule only after
  the model has demonstrably got something wrong; adjust model and effort from evals;
  get evals working for one skill before an eval library; a workflow document states
  principles and is not a checklist.
- **The `<plugin>/` path alias** in the context hook, which only `agent-tooling` used.
- **From `delegate-work`:** setting the subagent spawn depth, when a job deserves a
  subagent definition, and what belongs in a worker's brief versus a hook.

### Changed

- **`learn-from-work`** sends a lesson about how Claude works to
  `authoring-kit:choosing-extension-types` instead of choosing the kind itself.
- **"Never weaken a check to make it pass"** moved from `verify-work` to the
  constraints. It must hold whether or not the skill loads.
- **`python-idioms`** no longer triggers on "writing Python": the Python rule already
  arrives when a Python file is touched and names the skill, so the description keeps
  only what a person asks for.

## 0.4.2

From the second authoring-kit review.

### Added

- **`scripts/record-check`** runs a check and appends the command, its exit code and its
  own output to the task, so the evidence is never retyped. `--tier fast` and
  `--tier full` run the commands the repository declares in `.claude/checks.json`;
  `verify-work` and the reviewer use them. With `--repro` it records a failing test and
  its commit, and `close-task` refuses if that test changed since. A bug closes with a
  repro, or a note starting `No repro:`. Declared checks run from the board's own
  repository, and `close-task` refuses a task whose `.claude/checks.json` changed since
  it was accepted, unless a note starting `Checks changed:` says why.
- **`board-check parallel`** reports tasks that share files or wait on each other, which
  `delegate-work` used to ask the model to judge.
- **`board-check route`** gives the model and effort for a task from its type and size,
  and `route --sweep` the model for a sweep. The table is in `scripts/board.py` and
  names model aliases, not versions, so no skill names a model.
- **The guard** allows the reviewer's own calls without a prompt, so the close runs
  with no person in the loop, on purpose. The allow is read strictly and fails closed:
  a `$`, a backtick, a `#`, a redirect, an assignment, a wrapper or a script named by a
  relative path means the usual prompt. The guard also reads the command inside
  `record-check`, and denies `git init` without `main` unless git defaults to it.
- **The context hook** gives a file inside a plugin a `<plugin>/` alias, so
  `agent-tooling` reaches a plugin's own `agents/`, `rules/`, `commands/` and `hooks/`.

### Fixed

- **Finding a task's acceptance.** `board-check moved` and `close-task` used
  `git log --follow`, and git's rename and copy detection paired one task file with
  another because board files look alike, so a new task could inherit an older task's
  criteria. Acceptance is now the commit that first added the task's own id under
  `backlog/tasks/`.
- **`#` inside a word** no longer hides the rest of a command from the guard.

### Changed

- **Each principle has one home.** The skills and rules no longer restate what
  `constraints.md` says: closing as a separate decision, delegating for scale, sizing
  never by time, small work needing no plan, stuck as a reason to stop, one case before
  a library, and the pragmatism line each rule repeated. `agent-tooling` keeps only what
  is specific to authoring extensions.
- **`capture-intent`** triggers on work bigger than a handful of tool calls or on a
  request to put it on the board, not on every new idea.
- **`agent-tooling`** drops "context engineering is a first-class discipline" and says
  when an MCP server earns its place instead of "favour CodeAct".
- **The board rule** no longer lists allowed values and section names that
  `board-check` asserts and the step skills write.
- **`delegate-work`** has no model table: it runs `board-check route`, and a sweep a
  script can do needs no model.

### Kept on purpose

- **The checkable lines of `rules/python-tests.md`** move to 0.5.0 with the rest of the
  Python enforcement.

## 0.4.1

- **A reviewer can no longer close a task against criteria it reworded.** `close-task`
  and `board-check close` compare the criteria's wording and the `finish-moved` label
  with the last commit, and refuse if either changed: ticks are the only change a review
  can make to the finish line. A task whose file was never committed is refused too.
  The guard already blocked the `backlog` commands that reword criteria; this holds when
  the file is changed some other way, because the check reads the file, not the
  command.
- **A moved finish line is committed before review,** with the label and a note, by
  whoever moved it. The board rule and `close-work` say so.

## 0.4.0

The checks the skills used to describe are scripts now, and the close has an agent.

### Removed

- **The `work-loop` skill.** The order of the steps and the principles that ran it are
  in `constraints.md`. New work starts at `philosophy:capture-intent`.
- **The `board` skill.** What each key means is now `rules/board.md`, the allowed values
  are `board-check`, and the examples are `docs/board-examples.md`.

### Added

- **`scripts/board-check`:** ready, plan, spec with coverage, close, sizes, moved finish
  lines, and config, as text or JSON, exiting 0, 1, or 2.
- **`scripts/close-task`:** refuses unless every criterion is ticked, every child is
  done, and a moved finish line is labelled; then sets `Done`, appends the notes, and
  commits the task file alone.
- **`agents/reviewer.md`:** reviews and closes a task. No edit tools, Opus at low effort,
  with `close-work` preloaded as its method.
- **`hooks/guard.py`:** denies setting `Done` by hand, asks the person before
  `close-task` runs outside the reviewer, and keeps the reviewer's shell off writes and
  off `backlog` commands that change a task. `hooks/shellwords.py` reads the commands
  for it and for the context hook: several lines, heredocs, `sh -c`, `env`, `npx`.
- **`rules/board.md`,** delivered on the first touch of `backlog/` or the first
  `backlog` command.
- **`rules/code-design.md`:** "Every choice tells the reader something", moved out of the
  constraints and loaded for source files in owner mode only.

### Changed

- **The context hook** takes the mode from the touched file's repository, not the
  session's. It asks git only when an owner-only rule matched, once per directory, and
  prints a rule before recording it as delivered. It resets on `startup` as well as
  `clear` and `compact`, matches `owners.txt` without regard to case, and skips a rule
  whose `paths` is not a list, saying why.
- **The work loop** runs in a repository I own or one that already has a board. In a
  guest repository without one, its own process governs.
- **`close-work`** holds the reviewer's whole method, and its description no longer
  competes with the reviewer agent for "review this task".
- **Descriptions:** `record-decision` is scoped to work on the board. Filing a finding
  belongs to `capture-intent` and deciding whether it earns a task to `close-work`.
  `python-idioms` no longer keys on who owns the repository.
- **`delegate-work`** no longer says the subagent budget is enforced; it says to set it.
- **`idioms.md`** says DOC501 and DOC502 need ruff's preview mode, as the rule does.
- **The board examples** cite their requirements, which `board-check plan` caught.

### Kept on purpose

- **The C4 line stays in the constraints.** It decides the format before any `.c4` file
  exists, so a rule on those files would arrive too late.
- **"A review comment says what to change and why" stays in the constraints.** It
  applies to every review, and `close-work` now covers board tasks only.
- **Spelling, dashes, and the `main` branch stay as lines** until 0.5.0 makes them
  checks.

## 0.3.0

Specs (`write-spec`), the usage feedback from bh-02, and the authoring-kit review.

## 0.2.0

One small skill per step of the work loop, following Anthropic's plays.

## 0.1.0

The constraints, the Python and agent-tooling rules, and the hook that delivers them.
