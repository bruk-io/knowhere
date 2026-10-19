# Plan: artefact-check placeholders and fixtures

Spec: `../spec.md`, change 05. Delivers R10, R11.

## Files that change

- `plugins/philosophy/scripts/artefact.py`
- `plugins/philosophy/tests/test_artefact.py`
- `plugins/philosophy/tests/fixtures/intent/sample/intent.md`
- `plugins/philosophy/tests/fixtures/intent/sample/spec.md`
- `plugins/philosophy/tests/fixtures/intent/sample/plans/01-first.md`

## Order of work

1. R11: add the fixture `tests/fixtures/intent/sample/` holding a valid intent, spec and plan, the same text as the `INTENT`, `SPEC` and `PLAN` constants in `test_artefact.py`, except the plan delivers `R1, R2` so a renumbered R2 still breaks its citations.
2. R11: in `test_artefact.py`, drop `OWN_INTENT` and point `broken_copy`, `test_command_passes_on_this_repositorys_intent` (renamed `..._on_a_clean_fixture`) and `test_hook_is_silent_for_a_clean_artefact` at the fixture. `broken_copy` copies it to `tmp_path/intent/sample`. No test in the file reads `intent/self-running-loop` afterwards.
3. R10: write tests that fail before the change: for each of Author, Status (intent header), Intent and Applied (spec header), `Owner:` (area of concern) and `**R1.**` (requirement), the template's `<...>` placeholder in that field yields a finding. A real value in the same field yields none.
4. R10: in `artefact.py`, a field value that begins with `<` is not a value. `header_field` stops its value class at `<`; `APPLIED` and `OWNER` do the same; `check_requirements` flags a defined requirement whose text begins with `<`. Messages say the field holds the template's placeholder and to replace it. Only a leading `<` counts, so prose that quotes `<value>` mid-sentence still passes.

## Risks

- A real artefact that opens a field with `<` now fails. `artefact-check intent` over this repository's own intents shows whether any does; none is expected.
- `tests/test_loop.py` also reads `intent/self-running-loop/spec.md`, to count the delivery order. It tests `loop.delivery_order`, not an artefact check, and R11 names artefact tests only, so it stays. Rejected for this change: moving it needs a second fixture spec with eight changes for no gain to the check.
- `intent/self-running-loop` is untouched, so the fixture does not depend on it staying.
- `scripts/` and `tests/` sit under CODEOWNERS gates, so this build pauses on the owner's `@claude continue`.

## Proof

- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/run-check" fast` exits 0, with the new placeholder tests passing.
- The placeholder tests fail on `main` and pass on this branch.
- `grep -n self-running-loop plugins/philosophy/tests/test_artefact.py` prints nothing.
- `python3 plugins/philosophy/scripts/artefact-check intent` exits 0.
- `python3 plugins/philosophy/scripts/plan-drift build/loop-round-five/05` exits 0.
