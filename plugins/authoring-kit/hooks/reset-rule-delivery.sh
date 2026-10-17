#!/bin/sh
# SessionStart (startup|clear|compact) hook: after /clear or a compaction the
# rules that the PostToolUse hook delivered are no longer in context, and a
# session that starts can carry an id that already has delivery markers (a
# child `claude -p` run inherits its parent's id in some environments). So the
# record of what was delivered is dropped and each rule - and the litmus that
# leads the first one - is delivered again on the next touch. Not on `resume`:
# a resumed session still has the delivered text in context.
#
# The `hook` subcommand does it, prunes marker directories unused for a week
# while it is there, and prints nothing (stdout from a SessionStart hook
# becomes context). Always exits 0; a no-op when the linter or python3 cannot
# be found.

[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/scripts/claude-lint" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 "$CLAUDE_PLUGIN_ROOT/scripts/claude-lint" hook
