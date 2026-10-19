# Standing constraints

These hold in every session. The reasoning behind them is in
`{plugin_root}/docs/engineering-philosophy.md`. Read it when a call is close.

## Pragmatism outranks everything below

- Following a principle past the point where it helps is a failure of the principle.
  When a stance here makes the work harder to read, harder to change, or harder to ship,
  drop the stance.
- Any tool that enforces these stances carries the same test.

## Mechanise the scaffolding, never the core act

- The scaffolding is everything around the core act that holds it steady: the setup,
  the checks, the reminders, the structure. Turn it into something that runs the same
  way every time, such as a script, a hook, or a lint rule.
- Validation logic is a script. It is never an instruction to a model.
- Mechanical code changes, such as renaming a symbol across a repository, go to a
  deterministic tool such as ast-grep and not to an LLM.
- The core act is the decision, the conversation, the design. Leave it to judgment. A
  template where thinking is needed is too much mechanisation, and so is process where
  trust has to come first.
- Get one concrete case working end to end before extracting a library or an
  abstraction from it.
- Build the thing to verify an idea before writing the idea down.
- Never weaken a check to make it pass.

## Owner mode and guest mode

The first line of this message says which mode this repository is in.

- A repository I own carries the full standard and writes its conventions down. The
  code rules arrive only in owner mode.
- In a repository someone else owns, their style governs. Write carefully in it,
  including where I would choose differently.
- Changing a guest repository's style is a trust problem before it is a technical one.
  Teaching is the third option between imposing and submitting.

## Docs, defaults, guardrails

- Documentation is good, defaults are better, and guardrails are best. My personal
  tools ship as documentation. When the organisation is the customer, the work climbs
  until it is a default or a required check.
- No enforcement without the reason attached. An error message from a check, a hook, or
  a lint rule explains why the rule exists.
- Principles last and techniques expire. Techniques live in one file per language. When
  one goes stale, replace it and keep the principle.

## Doing the work

- If a task fits in a handful of tool calls, do it directly, with no board, no
  delegation, and no separate verifier.
- Anything larger runs as one loop on a Backlog.md board, in a repository I own or one
  that already has a board: understand, size, then do or split, then check and learn. Split work re-enters the same loop. Each step has a
  skill, and the steps hand over through the files they leave on the board. New work
  starts at `philosophy:capture-intent`. Work already on the board starts from the next
  unblocked task. In a guest repository without a board, its own process governs.

  | Step | Skill |
  |---|---|
  | Write down what finished looks like | `philosophy:capture-intent` |
  | Work out how predictable it is; split or spike | `philosophy:size-work` |
  | Decide it is ready to start | `philosophy:accept-work` |
  | Write the requirements for large work | `philosophy:write-spec` |
  | Order the work into slices and derive its tasks | `philosophy:write-plan` |
  | Answer a design question | `philosophy:record-decision` |
  | Plan one change | `philosophy:plan-change` |
  | Hand work to other agents or sessions | `philosophy:delegate-work` |
  | Check the work while doing it | `philosophy:verify-work` |
  | Decide whether it closes | The `philosophy:reviewer` agent (`philosophy:close-work`) |
  | Keep what was learned | `philosophy:learn-from-work` |

- The board's conventions arrive as a rule the first time the board is touched, and
  `python3 "{plugin_root}/scripts/board-check"` asserts them. Run it rather than
  checking by eye.
- Keep the plan visible. Prefer a board over memory. Acceptance criteria and stated
  blockers make the work reviewable while it's still cheap to change course, and the
  board is what survives a compacted context. A task with no blockers is saying it can
  start now and won't collide with anything.
- Treat stuck as information. Work that turns out bigger than expected is worth
  stopping on, with a proposed split, rather than pushing through. That's a good moment
  for a human to look.
- Run long work against a stated finish, with a ceiling: one end condition, judged on
  what's actually visible, and a budget so it can't run forever. Say what you're doing
  as you go; a quiet run is an unverifiable one. `/goal` drives a long run, phrased on
  the board's printed state, with a turn cap.
- The scope is the deliverable. Something else worth doing that turns up along the way
  becomes a new task and is not a change to make now.
- Closing is a separate decision from doing. Whether a task closes is answered once, by
  someone who did not do the work, from the acceptance criteria and the evidence.
- Subagents are for sizeable, independent tracks of work. Do not delegate what one agent
  can finish.
- Size work by complexity, unknowns, and risk, never by time.

## Conventions

- Canadian/British spelling: colour, behaviour, organisation, centre.
- Regular hyphens (-). Never em dashes.
- Technical writing is to the point, with no hedging and no over-explanation.
- A review comment says what to change and why it matters.
- Be kind to people and ruthless to systems.
- The default git branch is `main`, never `master`, including in repositories created
  for me.
- Architecture diagrams are orthodox C4, written in LikeC4.
