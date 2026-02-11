#!/bin/bash
# nuget-package-info.sh - Fetch NuGet (.NET) package statistics
# Usage: ./nuget-package-info.sh package-name

set -e

PACKAGE="${1:?Usage: $0 package-name}"

# NuGet uses lowercase for API
PACKAGE_LOWER=$(echo "$PACKAGE" | tr '[:upper:]' '[:lower:]')

echo "=== NuGet Package Info: $PACKAGE ==="
echo ""

# Get package registration info
echo "## Package Metadata"
REG_URL="https://api.nuget.org/v3/registration5-semver1/$PACKAGE_LOWER/index.json"
REG_RESPONSE=$(curl -s "$REG_URL" 2>/dev/null)

if ! echo "$REG_RESPONSE" | jq -e '.count' >/dev/null 2>&1; then
  echo "Package not found: $PACKAGE"
  exit 1
fi

# Get latest version info
LATEST_PAGE=$(echo "$REG_RESPONSE" | jq -r '.items[-1]["@id"]')
PAGE_RESPONSE=$(curl -s "$LATEST_PAGE" 2>/dev/null || echo "$REG_RESPONSE")

# Try to get the latest catalog entry
LATEST_ENTRY=$(echo "$PAGE_RESPONSE" | jq '.items[-1].items[-1].catalogEntry // .items[-1].catalogEntry // empty' 2>/dev/null)
if [ -z "$LATEST_ENTRY" ] || [ "$LATEST_ENTRY" = "null" ]; then
  LATEST_ENTRY=$(echo "$REG_RESPONSE" | jq '.items[-1].items[-1].catalogEntry // empty' 2>/dev/null)
fi

if [ -n "$LATEST_ENTRY" ] && [ "$LATEST_ENTRY" != "null" ]; then
  echo "$LATEST_ENTRY" | jq '{
    id: .id,
    version: .version,
    description: .description,
    authors: .authors,
    license: (.licenseExpression // .licenseUrl),
    projectUrl: .projectUrl,
    tags: .tags,
    published: .published,
    requireLicenseAcceptance: .requireLicenseAcceptance
  }' 2>/dev/null
else
  echo "Unable to parse package metadata"
fi
echo ""

# Search API for more details
echo "## Search Results"
SEARCH_RESPONSE=$(curl -s "https://azuresearch-usnc.nuget.org/query?q=packageid:$PACKAGE&prerelease=false&take=1" 2>/dev/null)
echo "$SEARCH_RESPONSE" | jq '.data[0] | {
  id: .id,
  version: .version,
  totalDownloads: .totalDownloads,
  verified: .verified,
  owners: .owners,
  description: .description
}' 2>/dev/null || echo "Unable to fetch search data"
echo ""

# Version history
echo "## Version History (last 10)"
# Get all versions from registration
echo "$REG_RESPONSE" | jq -r '
  [.items[].items[]? // .items[]] |
  map(.catalogEntry // .) |
  sort_by(.published) |
  reverse |
  .[:10][] |
  "\(.version): \(.published)"
' 2>/dev/null || echo "Unable to fetch version history"
echo ""

# Dependencies
echo "## Dependencies"
if [ -n "$LATEST_ENTRY" ] && [ "$LATEST_ENTRY" != "null" ]; then
  DEP_GROUPS=$(echo "$LATEST_ENTRY" | jq '.dependencyGroups // []')
  if [ "$(echo "$DEP_GROUPS" | jq 'length')" -gt 0 ]; then
    echo "$DEP_GROUPS" | jq -r '.[] | "Target Framework: \(.targetFramework // "all")", (.dependencies // [] | .[] | "  - \(.id): \(.range)")'
  else
    echo "No dependencies listed"
  fi
else
  echo "Unable to fetch dependency information"
fi
echo ""

# Download count
echo "## Download Statistics"
TOTAL_DL=$(echo "$SEARCH_RESPONSE" | jq -r '.data[0].totalDownloads // "N/A"')
echo "Total downloads: $TOTAL_DL"
echo ""

# Framework compatibility
echo "## Target Frameworks"
if [ -n "$LATEST_ENTRY" ] && [ "$LATEST_ENTRY" != "null" ]; then
  echo "$LATEST_ENTRY" | jq -r '.dependencyGroups[]?.targetFramework // empty' 2>/dev/null | sort -u || echo "Check package page"
fi
echo ""

# Links
echo "## More Info"
echo "NuGet: https://www.nuget.org/packages/$PACKAGE"
echo "FuGet (package explorer): https://www.fuget.org/packages/$PACKAGE"
echo "NuGet Trends: https://nugettrends.com/packages?ids=$PACKAGE"
echo ""

# Security
echo "## Security"
echo "Snyk: https://snyk.io/vuln/nuget:$PACKAGE"
echo ""

echo "=== End of NuGet Report ==="
