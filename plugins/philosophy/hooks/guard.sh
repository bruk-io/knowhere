#!/bin/sh
# PreToolUse (Bash|Edit|Write) hook: the shell in front of guard.py.
#
# This runs before every Bash call and every edit, so for most of them it must cost no
# more than a shell start. guard.py only ever acts on a payload that mentions close-task,
# the board or `git ... init`, or that comes from the reviewer agent (whose agent_type
# ends in `reviewer"`), so anything else exits here before Python starts. What is
# denied, allowed or asked about, and why, is decided in guard.py.
#
# Fails open: with no plugin root, no guard.py or no python3, nothing is blocked.

payload=$(cat)
case $payload in
  *close-task*|*backlog*|*'reviewer"'*|*'git '*init*) ;;
  *) exit 0 ;;
esac

[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/hooks/guard.py" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
printf '%s\n' "$payload" | exec python3 "$CLAUDE_PLUGIN_ROOT/hooks/guard.py"
