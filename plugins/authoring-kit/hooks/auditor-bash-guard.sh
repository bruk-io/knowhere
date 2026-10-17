#!/bin/sh
# PreToolUse (Bash) hook: holds the plugin's read-only auditor agent to the one
# thing it has Bash for, running the plugin's linter. The agent's tool list
# cannot scope Bash to a single command and a line in its prompt only asks, so
# the boundary is enforced here: the `hook` subcommand exits 2, with the reason
# and the allowed form on stderr, when the auditor's command is anything but
# one plain linter invocation.
#
# For every other session and agent this must cost no more than a shell start,
# because it runs before every Bash call. A hook payload names the agent it
# fired in as "agent_type":"<plugin>:authoring-auditor", so a payload in which
# no JSON string ends in the agent's name is not the auditor's and exits here,
# before Python starts. (Inside a JSON string a quote is written \", so a
# command that merely mentions the agent does not match; one that ends in its
# name does, and then Python decides.) Which agent, which plugin and which
# commands pass are all decided in the linter - nothing is parsed here.
#
# Fails closed once the payload may be the auditor's: if the linter or python3
# cannot be found, or the linter crashes, the call is blocked with the reason.
# The auditor is read-only, and that boundary is the reason the agent exists;
# without python3 it could not run its linter anyway. Every other payload has
# already exited above, so no other session is affected.

payload=$(cat)
case $payload in
  *'authoring-auditor"'*) ;;
  *) exit 0 ;;
esac

block() {
  echo "[auditor guard] Bash blocked for the authoring-auditor agent: $1. The auditor is read-only, and this guard blocks rather than let it run unchecked." >&2
  exit 2
}

[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/scripts/claude-lint" ] || block "the plugin's linter was not found"
command -v python3 >/dev/null 2>&1 || block "python3 was not found"

python3 "$CLAUDE_PLUGIN_ROOT/scripts/claude-lint" hook <<EOF_PAYLOAD
$payload
EOF_PAYLOAD
rc=$?
case $rc in
  0|2) exit $rc ;;
  *) block "the guard itself failed (exit $rc)" ;;
esac
