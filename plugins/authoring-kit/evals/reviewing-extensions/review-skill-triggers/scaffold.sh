#!/bin/bash
# Seeds the workspace with a small plugin to audit, copied from evals/reviewing-extensions/_fixtures/.
set -eu
src="$(cd "$(dirname "$0")/.." && pwd)/_fixtures"
[ -d "$src" ] || { echo "fixture source not found: $src" >&2; exit 1; }
mkdir -p fixtures/.claude-plugin
printf '{\n  "name": "acme-tools",\n  "version": "0.1.0",\n  "description": "Internal helpers for the acme monorepo."\n}\n' > fixtures/.claude-plugin/plugin.json
cp -R "$src/skills" fixtures/

# Fixtures are stored as <name>.fixture so the kit's own lint run does not
# treat their planted problems as the plugin's; restore the real names here.
find fixtures -name "*.fixture" | while read -r f; do mv "$f" "${f%.fixture}"; done
