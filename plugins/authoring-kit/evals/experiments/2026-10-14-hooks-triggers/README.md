# Trigger experiment: authoring-hooks description (2026-10-14)

One change per variant, each measured against the unchanged description. Nothing here
is applied to the plugin yet.

- Skill: `authoring-hooks`. Its 11 should-fire cases and 2 near-misses (`--tag authoring-hooks`).
- Model under test and judge: Haiku. 3 runs per case, kit loaded only (`--ablation none`).
- Measure: runs where the trajectory shows the Skill call (`trigger_rate.py`); near-miss
  false fires; mean case score as a check that firing helps the outcome.
- Variants: `variants.py` (the exact description text of each). Results: `results/`.

| Variant | Change | Should fire | False fires | Mean score |
|---|---|---|---|---|
| v0 baseline | none | 10/33 | 0/6 | 0.60 |
| v1 categories | quoted example phrases replaced by intent categories | 10/33 | 0/6 | 0.59 |
| v2 third person | "Builds and debugs ..." instead of "Use when ..." | 8/33 | 0/6 | 0.62 |
| v4 no implementation | dropped "Scaffolds and validates the config with a bundled tool." | 10/33 | 0/6 | 0.63 |
| v3a reason only | added: hook behaviour has traps Claude gets wrong from memory (named) | 19/33 | 0/6 | 0.68 |
| v3b directive only | added: "Load this before writing, reviewing or debugging any hook, even a small one." | 25/33 | 0/6 | 0.77 |
| v3 reason + directive | both | 28/33 | 0/6 | 0.82 |

## What works

- Telling Claude when to load the skill relative to the task ("before writing,
  reviewing or debugging any hook, even a small one"). This is the largest single effect.
- Telling Claude why it needs the skill: the specific things it gets wrong from memory.
  Weaker alone, and it adds to the directive.
- Firing carries through to outcome: mean score follows trigger rate (0.60 to 0.82).

## What does not move it (on this skill, Haiku)

- Phrasing the triggers as intent categories instead of quoted example phrases.
- Third person versus "Use when". Third person was slightly worse; within noise.
- Removing the implementation clause.

Every prompt already said "hook". The problem was never matching. Claude recognised
the topic and answered from its own knowledge. What changes behaviour is a description
that says its own knowledge is not enough.

## Round 2: harder near-misses and a second skill

Same setup (Haiku, default effort, 3 runs, kit loaded only). The description is either
unchanged or has the reason and the directive added (`variants2.py`). New near-misses
share words with the skill but need something else:
- hooks: husky with lint-staged, a GitHub Actions workflow, a Stripe webhook, a React
  hook, pytest conftest hooks;
- memory: a CONTRIBUTING.md and an ADR.

| Skill | Description | Should fire | False fires | Mean score |
|---|---|---|---|---|
| authoring-hooks | unchanged | 6/33 | 0/21 | 0.61 |
| authoring-hooks | + reason + directive | 25/33 | 0/21 | 0.77 |
| authoring-memory | unchanged | 5/30 | 0/9 | 0.57 |
| authoring-memory | + reason + directive | 13/30 | 0/9 | 0.69 |

- The effect reproduces on hooks (6 to 25). The harder near-misses never fired, so
  "any hook, even a small one" does not pull in git hooks, CI, webhooks, React or
  pytest hooks.
- It carries over to memory, but more weakly (5 to 13). The memory cases that still do
  not fire are questions or plans: "is this split right", "why does this line fade",
  "which of these lines belongs here". Claude answers in about 5 steps without loading
  anything. The directive names writing, reviewing and debugging, and these read to
  Claude as advice. Untested next variant: name advising or planning changes as well.
- Tension with the kit's own linter: on the memory variant, "load this before writing
  ... any CLAUDE.md" draws SK016 (info). SK016 says a trigger keyed on a file should be a
  rule or hook. The hooks variant ("before writing ... any hook") names an activity,
  not a file, and does not draw it. If the guidance becomes "say when to load relative
  to the task", SK016 needs to tell a task directive apart from a file trigger.

## Round 3: memory wording, and effort on the hooks winner

Memory, each variant one change from round 2's "+ reason + directive":

| Variant | Change | Should fire | False fires | Mean score |
|---|---|---|---|---|
| combined (round 2) | - | 13/30 | 0/9 | 0.69 |
| advise | directive adds "planning or advising on changes to" | 19/30 | 0/9 | 0.78 |
| activity | "any CLAUDE.md, CLAUDE.local.md or AGENTS.md" becomes "project memory" | 13/30 | 0/9 | 0.69 |

- Naming advice and planning in the directive helps: the question-style cases started
  firing (subtree-rule-fades 0 to 3/3, imports-do-not-save-context 0 to 2/3).
- Naming the activity instead of the files costs nothing, and SK016 does not flag it.
  So the linter-clean wording works as well as the file-keyed wording.

Hooks, round 2's "+ reason + directive", by effort level:

| Effort | Should fire | False fires | Mean score | Wall time |
|---|---|---|---|---|
| low | 19/33 | 0/21 | 0.67 | 6 min |
| default | 25/33 (round 2) | 0/21 | 0.77 | - |
| high | 33/33 | 0/21 | 0.96 | 13 min |

Effort does matter for triggering, against the earlier assumption below.

Round 4 adds the unchanged description at high effort, which completes the grid
(should-fire out of 33, no false fires anywhere in 21 near-miss runs per cell):

| Description | Low | Default | High |
|---|---|---|---|
| unchanged | 2/11 (one run per case) | 6-10 | 20 (score 0.72) |
| + reason + directive | 19 | 25-28 | 33 (score 0.96) |

Effort and the description add up. High effort alone gets the unchanged description
to 20/33. That is about what the improved description gets at low effort, and well
short of the improved description at the same effort. The description change is
worth roughly as much as going from low to high effort, and it is the one the skill
author controls.

## Effort (first check)

Checked once and dropped from the trigger experiment. `CLAUDE_CODE_EFFORT_LEVEL` does
reach eval sessions: at low, 2.9k output tokens and 6 s of thinking per session; at max,
14k and 165 s. The trigger decision happens before most of that thinking. At low, the
current hooks description fired 2/11, within noise of the default. Plan: one low/high
check on the final description, not a matrix.

## Limits

- One skill, one model, 3 runs. Identical-effect variants landed at 8-10/33, so treat
  differences of about 3 runs as noise.
- The two near-misses are not close calls (a convention, a git pre-commit hook). The
  directive "any hook, even a small one" needs harder near-misses before we trust it does
  not over-fire. Examples: husky, a GitHub Actions workflow, a webhook, React hooks.
- Not yet run on Sonnet or Opus, or on a second skill.
