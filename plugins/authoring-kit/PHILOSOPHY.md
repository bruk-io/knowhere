# Philosophy

_What `authoring-kit` believes, and how it makes each belief concrete. The plugin isn't a
collection of tools - it's the enforcement arm of a few convictions about making an AI
reliable. Each principle below is followed by how the plugin upholds it. This is the why; the
skills are the how._

## The bottleneck is context and validation, not code

The model can write the code. What's scarce is giving it the right context, structuring the
work so it can be verified, and checking the result. Authoring an extension is how you invest
in that scarce part once, instead of re-paying it by hand every session - the difference
between a prompt you retype and a workflow that persists.

*The plugin upholds this* with a gate that runs before you build anything -
`choosing-extension-types`, opening on `references/minimizing-model-work.md`: should the model
touch this at all, or is it really code or enforcement? Most "let's author a skill" impulses
die here, correctly.

## Prefer code; reserve the model for what only it can do

A probabilistic engine should never do deterministic work. The model is for judgement,
synthesis, and generation - everything checkable is code, a tool, or a hook. Prose the model
merely interprets is the last resort, not the first reach.

*The plugin upholds this* three ways: the gate's ordered ask pushes work down to code; the
linter (`claude-lint`) turns every checkable rule into an assertion that states its reason; and
the auditor flags prose that should have been code. It did not always: until 0.4.0 its rule
files restated what its linter asserts. Now a rule file holds judgement and a pointer.

## Reliability is two axes - pin each toward deterministic

Not a ladder, two independent questions. Does it run because the harness fires it, or because
the model chose to? Is the result fixed by a script, or sampled by the model? The closer both
sit to deterministic, the more a behaviour holds - and the two are independent, so you push on
each separately.

*The plugin upholds this* by placing its own guarantees where the axes are strongest: a hook
on every touch of an artifact delivers that kind's rule file the first time - the litmus with
the first one, no longer in every session - and runs the linter after a write (guaranteed
execution, fixed result - the top-left corner), handing the model only the judgement a check
can't make. "Run only the linter" was a sentence in the auditor's prompt; a hook now blocks
any other command.

## Match the extension type to what the behaviour is

A rule is a constraint; a skill is a procedure; an agent is a worker with its own boundary; a
hook is the only hard guarantee; CLAUDE.md is always-on memory. They differ by *when they load
and what guarantees them*, not by capability - so you route on what a thing fundamentally is,
never on which fields it can carry.

*The plugin upholds this* with `choosing-extension-types` as the selector and one skill per
extension type (`authoring-rules`, `authoring-skills`, `authoring-agents`, `authoring-hooks`,
`authoring-memory`), each carrying the judgement of how.

## One source of truth - point, don't copy

A fact written twice eventually disagrees with itself. Every fact lives in exactly one place;
everything else cites it.

*The plugin upholds this* in its own shape: the assertable rules and their numeric limits live
in the linter alone (`claude-lint rules`), what a field or a hook event is lives in the tools'
tables (`claude-lint fields`, one field at a time with `fields <kind> <field>`; `hooktool
events`), and `claude-lint drift` compares those tables with the installed build. Until 0.4.0 the skills copied the tables into prose, and one fact
sat in up to sixteen files. Now each fact has one home, and a test fails when a second file
restates it. This document defers every concrete fact to a skill or a command.

## Review is two jobs

Mechanical correctness and judgement are different kinds of check, and belong to different
reviewers. Conflate them and a human ends up eyeballing what code should assert, while code is
asked to judge what only a human can.

*The plugin upholds this* by splitting review in two: `claude-lint` owns every assertable
invariant (sizes, name formats, `@import` hops), hook-fired on every write; the
`authoring-auditor` subagent owns the judgement a linter can't make - a weak description, a
mis-chosen extension type, prose that should be code. The skills carry no review checklists.

## It dogfoods its own philosophy

The plugin is built the way it tells you to build: a gate before a selector, references over
duplication, code over prose, and its own advice wired as hooks, with a judgement auditor
beside them. Its test suite asserts on every run that it lints clean under its own
linter and that its hook config passes its own `hooktool`. It has also been caught out: until
0.4.0 its descriptions carried path matches ("whenever editing any SKILL.md"), a trigger left
to judgement. They now carry intent only, and the hook does the file-keyed delivery. That is
the whole point - the philosophy is only credible because the tool that teaches it obeys it.

---

_Read the skills to apply any of this; `/authoring-kit:choosing-extension-types` is the front door. This document
is the conviction behind them, and the plugin is that conviction made enforceable._
