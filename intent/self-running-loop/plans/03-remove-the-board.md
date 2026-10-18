# Plan: remove the board pieces, and give subagents the constraints

Spec: [spec.md](../spec.md), change 03. Delivers R15 and R16.

## Files that change

- `intent/self-running-loop/plans/03-remove-the-board.md`
- `plugins/philosophy/scripts/board.py`
- `plugins/philosophy/scripts/board-check`
- `plugins/philosophy/scripts/close-task`
- `plugins/philosophy/scripts/record-check`
- `plugins/philosophy/rules/board.md`
- `plugins/philosophy/docs/board-examples.md`
- `plugins/philosophy/agents/reviewer.md`
- `plugins/philosophy/skills/capture-intent/SKILL.md`
- `plugins/philosophy/skills/size-work/SKILL.md`
- `plugins/philosophy/skills/size-work/references/story-points.md`
- `plugins/philosophy/skills/accept-work/SKILL.md`
- `plugins/philosophy/skills/write-spec/SKILL.md`
- `plugins/philosophy/skills/record-decision/SKILL.md`
- `plugins/philosophy/skills/plan-change/SKILL.md`
- `plugins/philosophy/skills/delegate-work/SKILL.md`
- `plugins/philosophy/skills/verify-work/SKILL.md`
- `plugins/philosophy/skills/close-work/SKILL.md`
- `plugins/philosophy/skills/learn-from-work/SKILL.md`
- `plugins/philosophy/tests/test_board.py`
- `plugins/philosophy/hooks/guard.py`
- `plugins/philosophy/hooks/guard.sh`
- `plugins/philosophy/hooks/shellwords.py`
- `plugins/philosophy/hooks/context.py`
- `plugins/philosophy/hooks/hooks.json`
- `plugins/philosophy/tests/test_guard.py`
- `plugins/philosophy/tests/test_context.py`
- `plugins/philosophy/tests/test_plugin.py`
- `plugins/philosophy/templates/plan.md`
- `plugins/philosophy/constraints.md`
- `plugins/philosophy/README.md`
- `plugins/philosophy/CHANGELOG.md`
- `plugins/philosophy/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `docs/index.md`
- `docs/getting-started/installation.md`
- `docs/getting-started/quickstart.md`

## Order of work

1. Delete the board scripts, the board rule and its examples, the reviewer agent, the
   ten step skills, and `test_board.py` (R16).
2. Cut the guard down to what still applies: `git init` starts on `main`. The close,
   the reviewer's limits and the board parsing go, with their tests, and `guard.sh`
   lets only `git ... init` reach Python (R16). Change 04 adds the plan-sync and repro
   guards back into it.
3. `context.py` answers `SubagentStart` with the same mode line and constraints that
   `SessionStart` prints, as `additionalContext`; `hooks.json` registers it with no
   matcher, so every subagent gets it. The `backlog` command hook goes (R15).
4. Rewrite "Doing the work" in `constraints.md` for this loop: intent, spec, build,
   review, the commands, the gates, and where a lesson goes (spec area of concern 6)
   (R16).
5. Rewrite the README, bump to 0.5.0 with a changelog entry, and update the plugin's
   description in `plugin.json`, the marketplace and the site docs (R16).

## Risks

- Every subagent now gets the constraints, including read-only ones such as Explore,
  which costs context. The rewritten "Doing the work" section is shorter than the board
  version, which offsets some of it.
- A skill or document elsewhere could still name a removed skill. `test_plugin.py`
  fails on any `philosophy:` name that doesn't resolve, and a grep for the removed
  names over the whole repository catches the rest.
- Until change 04, the guard checks only `git init`. Nothing depends on the removed
  close guard, because closing is now a merge.

## Proof

- `uv run --no-project --with pytest python -m pytest -q` in `plugins/philosophy`
  passes, including a test that a `SubagentStart` payload gets the constraints as
  `additionalContext` and the `git init` tests.
- `grep -rn` for each removed skill name, `board-check`, `close-task` and
  `record-check` over the repository finds them only in this intent and the changelog.
- The hooktool validates `hooks.json`, and `claude-lint` reports no errors on the
  plugin.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0.
