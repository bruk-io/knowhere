#!/bin/sh
# PostToolUse (Read|Write|Edit) hook: rule delivery and write-time lint for
# authoring artifacts.
#
# A thin shim. All the logic - which paths count as artifacts, which rule is
# delivered on first touch, which checks run, how it is all reported - lives in
# the linter's `hook` subcommand, so there is no path list here to drift from
# the linter's own.
#
# PostToolUse cannot block (the tool has already run), and plain stdout from a
# PostToolUse hook is not shown to the model. The `hook` subcommand therefore
# prints one JSON object whose hookSpecificOutput.additionalContext carries the
# rule and the findings; that field is the channel that reaches the model. It
# always exits 0.
#
# The linter is not on PATH: it lives in the plugin's scripts/ directory (a
# plugin with a bin/ directory is not installed by claude.ai or Cowork), so it
# is found through CLAUDE_PLUGIN_ROOT first. A `claude-lint` that someone has
# put on PATH themselves is the fallback.
#
# If the linter or python3 cannot be found this is a no-op: exit before reading
# stdin or spawning anything.

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/scripts/claude-lint" ]; then
  LINT="$CLAUDE_PLUGIN_ROOT/scripts/claude-lint"
elif LINT=$(command -v claude-lint 2>/dev/null) && [ -n "$LINT" ]; then
  :
else
  exit 0
fi

command -v python3 >/dev/null 2>&1 || exit 0
command -v cat >/dev/null 2>&1 || exec python3 "$LINT" hook

# Extension gate. Most reads and writes are not artifacts, and for those
# starting Python is the whole cost of this hook. An artifact's file name ends
# in one of the suffixes `classify --extensions` prints, and in the event JSON
# a string that ends in one is followed at once by its closing quote. A payload
# with neither of those byte sequences in it therefore cannot name an artifact,
# wherever the path sits and whatever the content fields hold (a quote inside a
# JSON string is written \", so content cannot forge the sequence - and if
# anything else in the payload happens to contain it, the only cost is that
# Python starts and decides for itself). Nothing is parsed here.
#
# `cat` reads the payload in one go; the shell's own `read` takes it a byte at
# a time and was slower than Python itself on a large Write. A Read carries the
# file's content too, so the cost here grows with the file: about 25 ms per
# megabyte, against 5 ms for an ordinary payload.
payload=$(cat)
case $payload in
  *'.md"'* | *'.json"'*) ;;
  *) exit 0 ;;
esac

exec python3 "$LINT" hook <<EOF_PAYLOAD
$payload
EOF_PAYLOAD
