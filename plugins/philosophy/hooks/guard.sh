#!/bin/sh
# PreToolUse (Bash|Edit|Write|NotebookEdit) hook: the shell in front of guard.py.
#
# This runs before every Bash call and every edit, so for most of them it must cost no
# more than a shell start. guard.py acts only on `git ... init` and on Edit and Write,
# which it holds to the plan on a build branch, so any other Bash call exits here before
# Python starts. What is denied, and why, is decided in guard.py.
#
# Fails open: with no plugin root, no guard.py or no python3, nothing is blocked.

payload=$(cat)
case $payload in
  *'git '*init*|*'"tool_name"'*'"Edit"'*|*'"tool_name"'*'"Write"'*|*'"tool_name"'*'"NotebookEdit"'*) ;;
  *) exit 0 ;;
esac

[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/hooks/guard.py" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
printf '%s\n' "$payload" | exec python3 "$CLAUDE_PLUGIN_ROOT/hooks/guard.py"
