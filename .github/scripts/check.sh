#!/bin/bash
# The repository's check, in two tiers, declared in .claude/checks.json.
#   fast: what a build runs before it opens a PR - the philosophy plugin's tests and
#         lint, and the shape of every intent, spec and plan.
#   full: fast, plus authoring-kit's tests and the marketplace's validation. CI runs it
#         on every PR, so the evidence a merge rests on is CI's, not a session's.
# Exits non-zero on the first failure.
set -euo pipefail
tier="${1:-fast}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

echo "== philosophy: tests"
(cd plugins/philosophy && uv run -q --no-project --with pytest python -m pytest -q)
echo "== philosophy: ruff"
uvx ruff check --config plugins/philosophy/ruff.toml plugins/philosophy
echo "== artefacts"
python3 plugins/philosophy/scripts/artefact-check intent

if [ "$tier" = full ]; then
  echo "== authoring-kit: tests"
  (cd plugins/authoring-kit && uv run -q --no-project --with pytest python -m pytest -q)
  echo "== marketplace"
  python3 .github/scripts/validate-plugin.py --mode marketplace
fi
