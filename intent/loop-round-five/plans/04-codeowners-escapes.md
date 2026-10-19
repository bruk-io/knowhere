# Plan: CODEOWNERS escapes

Spec: `../spec.md`, change 04. Delivers R9.

## Files that change

- `plugins/philosophy/scripts/loop.py`
- `plugins/philosophy/tests/test_loop.py`

## Order of work

1. R9: in `loop.py`, replace the `line.split("#", 1)[0].split()` in `parse_codeowners` with a pure helper, `_words(line)`, that scans the line once. A backslash followed by `#` or a space adds that character to the current word; an unescaped `#` ends the line; unescaped whitespace ends a word; a backslash before any other character is kept as written, so `pattern_regex` still sees it. The first word is the pattern and the rest are owners, as before.
2. R9: in `test_loop.py`, add tests that fail before the change: a rule `\#notes/ @owner` gates `#notes/a.md` and not `notes/a.md`; a rule `my\ docs/ @owner` gates `my docs/a.md` and not `my/a.md` or `docs/a.md`; an unescaped trailing `# comment` after owners still reads as a comment and is not read as an owner; a line holding only `\# not a comment` is a rule, not a comment. Existing CODEOWNERS tests stay as they are.

## Risks

- A rule that read as ungated before may now gate its path. That is the fix: the old reading failed open for a gate.
- A backslash before a character other than `#` or a space is left alone. CODEOWNERS documents no other escape, and guessing at more would change what existing rules match. Rejected for this change, with that reason.
- `loop.py` sits under `scripts/`, which CODEOWNERS gates, so this build pauses on the owner's `@claude continue`.

## Proof

- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/run-check" fast` exits 0, with the new tests passing.
- The new escape tests fail on `main` and pass on this branch.
- `python3 plugins/philosophy/scripts/plan-drift build/loop-round-five/04` exits 0 on this branch.
- The `plan-drift` job passes on this PR.
