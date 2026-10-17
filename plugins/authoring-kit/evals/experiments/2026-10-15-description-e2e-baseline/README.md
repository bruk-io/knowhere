# Baseline: do skills written with the kit fire more often? (2026-10-15)

`python3 evals/description_e2e.py run --model haiku --judge-model haiku --runs-write 2 --runs-probe 2`,
once at default probe effort and once with `--probe-effort low`. Five `description-e2e`
cases, the kit as it is on `main` (before any trigger guidance). Stage 1 costs about
$0.15 per run; stage 2 adds roughly $1.

| Probe effort | Written | Should fire | Near-miss false fires | Rubric pass (when + why + activity) |
|---|---|---|---|---|
| default | with kit | 81/100 | 0/80 | 3/10 |
| default | without | 82/100 | 2/80 | 2/10 |
| low | with kit | 81/100 | 0/80 | 3/10 |
| low | without | 77/100 | 0/80 | 1/10 |

- The kit as it stands makes no difference to how often the skills it writes fire.
- Written skills fire about 80% of the time whether the topic is team rules or
  something Claude thinks it already knows (uv, Textual 8). The general-knowledge
  cases did not separate as expected. Every written description already names the
  specific rules ("uv only", "lock_timeout", "RFC 9457"), which works as a reason to load.
- Probe effort barely moves these skills, unlike the kit's own hooks skill.
- Almost no written description meets the new rubric (3/10 with the kit). So the rubric
  has room to show the guidance working, and stage 2 has about 20 points of headroom.
- `authoring-skills` itself loaded in 12 of 20 writing runs: the kit's own trigger
  problem limits how much its guidance can reach.

## After the guidance (commit b62eaa0)

Same commands, after `authoring-skills` gained the description guidance and the kit's
own descriptions were rewritten to follow it.

| Probe effort | Written | Should fire | Near-miss false fires | Rubric pass |
|---|---|---|---|---|
| default | with kit | 98/100 (was 81) | 0/80 | 10/10 (was 3) |
| default | without | 86/100 | 0/80 | 2/10 |
| low | with kit | 96/100 (was 81) | 4/80 (was 0) | 9/10 (was 3) |
| low | without | 71/100 | 0/80 | 1/10 |

`authoring-skills` loaded in 19/20 writing runs (was 12/20).

Full suite, Haiku, one run per case (`after-suite-results.json`, compared with the
2026-10-14 run), times each kit skill fired:

| Skill | Before | After |
|---|---|---|
| authoring-hooks | 2/11 | 11/11 |
| authoring-skills | 3/12 | 11/17 |
| authoring-agents | 3/8 | 7/8 |
| authoring-rules | 4/12 | 9/12 |
| wrapping-api-calls | 5/10 | 8/10 |
| authoring-memory | 1/10 | 6/10 |
| choosing-extension-types | 1/9 | 4/9 |

No new near-miss fired (12 near-miss cases). Four regression cases scored lower; in
each the skill did not fire on that single run. One is `never-triggers`, whose rubric is
now stricter by design. Written skills at low effort picked up 4 false fires in 80
(api-errors and python-packaging), the cost of a pushier description.
