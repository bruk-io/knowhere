#!/bin/bash
# pypi-package-info.sh - Fetch PyPI package statistics and metadata
# Usage: ./pypi-package-info.sh package-name
#
# Uses PyPI JSON API

set -e

PACKAGE="${1:?Usage: $0 package-name}"

echo "=== PyPI Package Info: $PACKAGE ==="
echo ""

# Fetch package info
echo "## Package Metadata"
RESPONSE=$(curl -s "https://pypi.org/pypi/$PACKAGE/json" 2>/dev/null)

if echo "$RESPONSE" | jq -e '.message' >/dev/null 2>&1; then
  echo "Package not found: $PACKAGE"
  exit 1
fi

echo "$RESPONSE" | jq '{
  name: .info.name,
  version: .info.version,
  summary: .info.summary,
  author: .info.author,
  author_email: .info.author_email,
  maintainer: .info.maintainer,
  license: .info.license,
  home_page: .info.home_page,
  project_url: .info.project_url,
  package_url: .info.package_url,
  requires_python: .info.requires_python,
  keywords: .info.keywords,
  classifiers_count: (.info.classifiers | length)
}'
echo ""

# Project URLs
echo "## Project URLs"
echo "$RESPONSE" | jq -r '.info.project_urls // {} | to_entries[] | "  \(.key): \(.value)"' 2>/dev/null || echo "None listed"
echo ""

# Dependencies
echo "## Dependencies"
DEPS=$(echo "$RESPONSE" | jq -r '.info.requires_dist // []')
DEP_COUNT=$(echo "$DEPS" | jq 'length')
echo "Total dependencies: $DEP_COUNT"
echo ""
echo "Direct dependencies:"
echo "$DEPS" | jq -r '.[] | "  - \(.)"' 2>/dev/null | head -20
if [ "$DEP_COUNT" -gt 20 ]; then
  echo "  ... and $((DEP_COUNT - 20)) more"
fi
echo ""

# Release history
echo "## Release History (last 10)"
echo "$RESPONSE" | jq -r '
  .releases | to_entries |
  map(select(.value | length > 0)) |
  map({version: .key, date: .value[0].upload_time}) |
  sort_by(.date) |
  reverse |
  .[0:10][] |
  "\(.version): \(.date)"
'
echo ""

# Version count
VERSION_COUNT=$(echo "$RESPONSE" | jq '.releases | keys | length')
echo "Total versions released: $VERSION_COUNT"
echo ""

# Download stats (from pypistats)
echo "## Download Statistics"
STATS=$(curl -s "https://pypistats.org/api/packages/$PACKAGE/recent" 2>/dev/null)
if echo "$STATS" | jq -e '.data' >/dev/null 2>&1; then
  echo "$STATS" | jq '{
    last_day: .data.last_day,
    last_week: .data.last_week,
    last_month: .data.last_month
  }'
else
  echo "Unable to fetch download stats"
fi
echo ""

# Check for type stubs
echo "## Type Hints"
echo "$RESPONSE" | jq -r '
  if .info.classifiers | any(contains("Typing :: Typed")) then
    "Package includes type hints (PEP 561)"
  else
    "No PEP 561 type hints declared - check for types-\(.info.name) stub package"
  end
'
echo ""

# Development status
echo "## Development Status"
echo "$RESPONSE" | jq -r '
  .info.classifiers[] |
  select(startswith("Development Status"))
' 2>/dev/null || echo "Not specified"
echo ""

# Security check suggestion
echo "## Security Check"
echo "Run: pip-audit (after installing)"
echo "Or check: https://snyk.io/vuln/pip:$PACKAGE"
echo "Or: https://pyup.io/packages/pypi/$PACKAGE/"
echo ""

# Libraries.io link
echo "## More Info"
echo "https://libraries.io/pypi/$PACKAGE"
echo "https://pepy.tech/project/$PACKAGE"
echo ""

echo "=== End of PyPI Report ==="
