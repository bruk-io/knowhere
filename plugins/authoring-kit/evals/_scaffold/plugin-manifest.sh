#!/bin/bash
# Makes the eval workspace a real plugin, so the kit's PostToolUse hook
# classifies agents/, hooks/ and skills/ files exactly as it would for a user
# and the lint feedback loop is part of what the with-plugin arm measures.
# Usage, from a case's own scaffold.sh: exec bash "<this file>" [plugin-name]
set -eu
mkdir -p .claude-plugin
printf '{\n  "name": "%s",\n  "version": "0.1.0"\n}\n' "${1:-my-plugin}" > .claude-plugin/plugin.json
