# Evals

Cases for `claude plugin eval`, one folder per skill (`evals/<skill>/<case>/`).
Each case is tagged with its skill and with one of:

- `capability` - plain Claude gets it wrong without the kit. These measure what
  the skill adds; expect them to start low and climb.
- `regression` - plain Claude already gets it right. These sit near 100% in both
  arms and catch the skill making things worse.

Run from the plugin root. `--scaffold` runs the cases' own setup scripts (fixtures
for `authoring-memory` and `reviewing-extensions`); `Bash` is needed only by
`reviewing-extensions`, whose auditor runs the linter, and needs `bubblewrap` and
`socat` on Linux:

```
claude plugin eval . --scaffold --allow-tools Write Edit Bash -j 4          # everything
claude plugin eval . --tag authoring-skills --allow-tools Write Edit -j 4   # one skill
claude plugin eval . --tag capability --allow-tools Write Edit -j 4         # what the kit adds
```

Writes into `.claude/` are refused inside plugin eval, so cases that author files
ask for a plugin layout (`skills/<name>/SKILL.md`), which is writable and is
linted by the kit's hook as it would be for a user. Rules and project settings
cannot live in a plugin, so those cases grade the Write Claude attempted.

## Running and reading a run

`evals/report.py run` wraps `claude plugin eval .`: pass it the same options. It
keeps every session's transcript, then writes into `evals/results/<timestamp>/`:

- `results.json` - the run, every case, every run of each arm, each grader's
  verdict and explanation, and each session's trajectory (its steps: thinking,
  tool calls with their inputs and results, skill loads, hooks, the end state).
- `report.html` - one self-contained page built from `results.json`: totals,
  a per-skill table, a filterable case list, the grader grid per run, and each
  session's trajectory as a log you can open step by step.
- `raw.json`, `claude/` and `traces/` - what `claude plugin eval` wrote, and the
  transcripts without the token stream.

```
python3 evals/report.py run --trust-plugin --scaffold --allow-tools Write Edit Bash -j 4 --judge-model sonnet
python3 evals/report.py run --trust-plugin --tag authoring-skills --scaffold --allow-tools Write Edit -j 4 --judge-model sonnet
python3 evals/report.py run --trust-plugin --scaffold --allow-tools Write Edit Bash -j 4 --runs 1 --model haiku --judge-model haiku --max-cost-usd 10   # cheap pass
python3 evals/report.py render evals/results/<timestamp>/results.json     # rebuild the page
```

Every option after `run` goes to `claude plugin eval` unchanged. `--model` sets the
model under test (default: your Claude Code default), `--judge-model` the grader
model, `--tag` the cases and `--runs` the repeats per case (default 3). The page
header shows both models. Haiku and Sonnet both match all calibration labels, so a
Haiku judge is fine for cheap passes; scores from different `--model` runs are not
comparable, so compare like with like.

The page's look comes from `_report/bh-01-tokens.json` (a copy of the bh-01
design system's tokens; refresh it from the spec, never edit it by hand) and
`_report/template.html`. A hook's own output is not in the transcript, so the
trajectory shows Claude's reaction to lint feedback, not the feedback itself.

## Code or judgement

- A grader that re-checks a lint rule is named `lint-<RULE>-...`, and a test
  fails if the rule no longer exists. In the real product the hook enforces
  these after every write, so every case that writes a plugin runs in one
  (`_scaffold/plugin-manifest.sh`) and the with-plugin arm measures the loop.
- Observable choices - which file, which field, which tool, whether the skill
  loaded - are graded by code (`regex`, `file_exists`, `tool_used`).
- Only reasoning is graded by a judge, on short output, with PASS and FAIL
  conditions. Run with `--judge-model sonnet`.
- `_judges/` holds judge calibration: fixed answers with a known verdict, scored
  by the exact rubric under test (a test keeps the copies identical). Run them
  with `--tag judge-calibration --ablation none`; the page reports the judge's
  accuracy.

Results go to `evals/results/`, which is not committed.
