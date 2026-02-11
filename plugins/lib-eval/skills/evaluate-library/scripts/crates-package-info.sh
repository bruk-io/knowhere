#!/bin/bash
# crates-package-info.sh - Fetch crates.io (Rust) package statistics
# Usage: ./crates-package-info.sh crate-name

set -e

CRATE="${1:?Usage: $0 crate-name}"

echo "=== Crates.io Package Info: $CRATE ==="
echo ""

# Fetch crate info
echo "## Crate Metadata"
RESPONSE=$(curl -s "https://crates.io/api/v1/crates/$CRATE" 2>/dev/null)

if echo "$RESPONSE" | jq -e '.errors' >/dev/null 2>&1; then
  echo "Crate not found: $CRATE"
  exit 1
fi

echo "$RESPONSE" | jq '{
  name: .crate.name,
  description: .crate.description,
  max_version: .crate.max_version,
  max_stable_version: .crate.max_stable_version,
  downloads: .crate.downloads,
  recent_downloads: .crate.recent_downloads,
  created_at: .crate.created_at,
  updated_at: .crate.updated_at,
  homepage: .crate.homepage,
  repository: .crate.repository,
  documentation: .crate.documentation,
  categories: [.crate.categories[]],
  keywords: [.crate.keywords[]]
}'
echo ""

# Get latest version details
echo "## Latest Version"
LATEST_VERSION=$(echo "$RESPONSE" | jq -r '.crate.max_version')
VERSION_RESPONSE=$(curl -s "https://crates.io/api/v1/crates/$CRATE/$LATEST_VERSION" 2>/dev/null)

echo "$VERSION_RESPONSE" | jq '{
  version: .version.num,
  license: .version.license,
  rust_version: .version.rust_version,
  crate_size: .version.crate_size,
  downloads: .version.downloads,
  published: .version.created_at,
  yanked: .version.yanked
}'
echo ""

# Dependencies
echo "## Dependencies"
DEPS=$(curl -s "https://crates.io/api/v1/crates/$CRATE/$LATEST_VERSION/dependencies" 2>/dev/null)
NORMAL_DEPS=$(echo "$DEPS" | jq '[.dependencies[] | select(.kind == "normal")] | length')
DEV_DEPS=$(echo "$DEPS" | jq '[.dependencies[] | select(.kind == "dev")] | length')
BUILD_DEPS=$(echo "$DEPS" | jq '[.dependencies[] | select(.kind == "build")] | length')

echo "Normal dependencies: $NORMAL_DEPS"
echo "Dev dependencies: $DEV_DEPS"
echo "Build dependencies: $BUILD_DEPS"
echo ""

echo "### Direct Dependencies"
echo "$DEPS" | jq -r '.dependencies[] | select(.kind == "normal") | "  - \(.crate_id): \(.req) \(if .optional then "(optional)" else "" end)"' 2>/dev/null | head -20
echo ""

# Version history
echo "## Version History (last 10)"
curl -s "https://crates.io/api/v1/crates/$CRATE/versions" 2>/dev/null | jq -r '
  .versions[:10][] |
  "\(.num): \(.created_at) \(if .yanked then "[YANKED]" else "" end)"
'
echo ""

# Owners/Maintainers
echo "## Owners"
curl -s "https://crates.io/api/v1/crates/$CRATE/owners" 2>/dev/null | jq -r '.users[] | "  - \(.login) (\(.name // "no name"))"'
echo ""

# Download stats
echo "## Download Statistics"
DOWNLOADS=$(echo "$RESPONSE" | jq -r '.crate.downloads')
RECENT=$(echo "$RESPONSE" | jq -r '.crate.recent_downloads')
echo "Total downloads: $DOWNLOADS"
echo "Recent downloads (90 days): $RECENT"
echo ""

# Reverse dependencies (dependents)
echo "## Reverse Dependencies (who uses this)"
RDEPS=$(curl -s "https://crates.io/api/v1/crates/$CRATE/reverse_dependencies?per_page=10" 2>/dev/null)
RDEP_COUNT=$(echo "$RDEPS" | jq '.meta.total')
echo "Total crates depending on $CRATE: $RDEP_COUNT"
echo ""
echo "Top dependents:"
echo "$RDEPS" | jq -r '.versions[:10][] | "  - \(.crate_id)"' 2>/dev/null
echo ""

# Links
echo "## More Info"
echo "Crates.io: https://crates.io/crates/$CRATE"
echo "Docs.rs: https://docs.rs/$CRATE"
echo "Lib.rs: https://lib.rs/crates/$CRATE"
echo ""

echo "=== End of Crates.io Report ==="
