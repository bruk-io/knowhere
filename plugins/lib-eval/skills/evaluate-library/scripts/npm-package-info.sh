#!/bin/bash
# npm-package-info.sh - Fetch npm package statistics and metadata
# Usage: ./npm-package-info.sh package-name
#
# Uses npm registry API and npmjs.com

set -e

PACKAGE="${1:?Usage: $0 package-name}"

echo "=== NPM Package Info: $PACKAGE ==="
echo ""

# Fetch package info from registry
echo "## Package Metadata"
curl -s "https://registry.npmjs.org/$PACKAGE" | jq '{
  name: .name,
  description: .description,
  latest_version: .["dist-tags"].latest,
  license: .license,
  homepage: .homepage,
  repository: .repository.url,
  bugs: .bugs.url,
  keywords: .keywords,
  maintainers: [.maintainers[].name],
  maintainer_count: (.maintainers | length),
  created: .time.created,
  last_modified: .time.modified
}' 2>/dev/null || echo "Package not found or error fetching"
echo ""

# Get latest version details
echo "## Latest Version Details"
LATEST=$(curl -s "https://registry.npmjs.org/$PACKAGE/latest" 2>/dev/null)
echo "$LATEST" | jq '{
  version: .version,
  dependencies: (.dependencies | keys | length // 0),
  devDependencies: (.devDependencies | keys | length // 0),
  peerDependencies: (.peerDependencies | keys | length // 0),
  engines: .engines,
  types: (if .types or .typings then "Yes" else "No TypeScript types bundled" end)
}' 2>/dev/null || echo "Unable to fetch latest version"
echo ""

# Dependencies list
echo "## Direct Dependencies"
echo "$LATEST" | jq -r '.dependencies // {} | to_entries[] | "  - \(.key): \(.value)"' 2>/dev/null || echo "None"
echo ""

# Download stats (requires separate API)
echo "## Download Statistics"
# Last week
WEEKLY=$(curl -s "https://api.npmjs.org/downloads/point/last-week/$PACKAGE" 2>/dev/null)
echo "Downloads last week: $(echo "$WEEKLY" | jq -r '.downloads // "N/A"')"

# Last month
MONTHLY=$(curl -s "https://api.npmjs.org/downloads/point/last-month/$PACKAGE" 2>/dev/null)
echo "Downloads last month: $(echo "$MONTHLY" | jq -r '.downloads // "N/A"')"

# Last year
YEARLY=$(curl -s "https://api.npmjs.org/downloads/point/last-year/$PACKAGE" 2>/dev/null)
echo "Downloads last year: $(echo "$YEARLY" | jq -r '.downloads // "N/A"')"
echo ""

# Version history (last 10)
echo "## Version History (last 10 releases)"
curl -s "https://registry.npmjs.org/$PACKAGE" | jq -r '
  .time | to_entries |
  map(select(.key != "created" and .key != "modified")) |
  sort_by(.value) |
  reverse |
  .[0:10][] |
  "\(.key): \(.value)"
' 2>/dev/null || echo "Unable to fetch version history"
echo ""

# Security check suggestion
echo "## Security Check"
echo "Run: npm audit --package-lock-only (after installing)"
echo "Or check: https://snyk.io/vuln/npm:$PACKAGE"
echo ""

# Bundle size (bundlephobia)
echo "## Bundle Size (check manually)"
echo "https://bundlephobia.com/package/$PACKAGE"
echo ""

# npm trends comparison link
echo "## Compare with alternatives"
echo "https://npmtrends.com/$PACKAGE"
echo ""

echo "=== End of NPM Report ==="
