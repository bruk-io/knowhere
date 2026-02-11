#!/bin/bash
# rubygems-package-info.sh - Fetch RubyGems package statistics
# Usage: ./rubygems-package-info.sh gem-name

set -e

GEM="${1:?Usage: $0 gem-name}"

echo "=== RubyGems Package Info: $GEM ==="
echo ""

# Fetch gem info
echo "## Gem Metadata"
RESPONSE=$(curl -s "https://rubygems.org/api/v1/gems/$GEM.json" 2>/dev/null)

if echo "$RESPONSE" | jq -e '.name' >/dev/null 2>&1; then
  echo "$RESPONSE" | jq '{
    name: .name,
    version: .version,
    authors: .authors,
    info: .info,
    licenses: .licenses,
    homepage_uri: .homepage_uri,
    source_code_uri: .source_code_uri,
    documentation_uri: .documentation_uri,
    bug_tracker_uri: .bug_tracker_uri,
    changelog_uri: .changelog_uri,
    downloads: .downloads,
    version_downloads: .version_downloads,
    created_at: .version_created_at
  }'
else
  echo "Gem not found: $GEM"
  exit 1
fi
echo ""

# Dependencies
echo "## Dependencies"
DEPS=$(echo "$RESPONSE" | jq '.dependencies')
RUNTIME_DEPS=$(echo "$DEPS" | jq '.runtime | length')
DEV_DEPS=$(echo "$DEPS" | jq '.development | length')

echo "Runtime dependencies: $RUNTIME_DEPS"
echo "Development dependencies: $DEV_DEPS"
echo ""

echo "### Runtime Dependencies"
echo "$DEPS" | jq -r '.runtime[] | "  - \(.name): \(.requirements)"' 2>/dev/null || echo "None"
echo ""

# Version history
echo "## Version History (last 10)"
curl -s "https://rubygems.org/api/v1/versions/$GEM.json" 2>/dev/null | jq -r '
  .[:10][] |
  "\(.number): \(.created_at) \(if .yanked then "[YANKED]" else "" end) - \(.downloads) downloads"
'
echo ""

# Download stats
echo "## Download Statistics"
TOTAL=$(echo "$RESPONSE" | jq -r '.downloads')
VERSION_DL=$(echo "$RESPONSE" | jq -r '.version_downloads')
echo "Total downloads (all versions): $TOTAL"
echo "Current version downloads: $VERSION_DL"
echo ""

# Owners
echo "## Owners"
curl -s "https://rubygems.org/api/v1/gems/$GEM/owners.json" 2>/dev/null | jq -r '.[] | "  - \(.handle // .email)"' 2>/dev/null || echo "Unable to fetch owners"
echo ""

# Reverse dependencies
echo "## Reverse Dependencies"
RDEPS=$(curl -s "https://rubygems.org/api/v1/gems/$GEM/reverse_dependencies.json" 2>/dev/null)
RDEP_COUNT=$(echo "$RDEPS" | jq 'length')
echo "Gems depending on $GEM: $RDEP_COUNT"
echo ""
echo "Top dependents:"
echo "$RDEPS" | jq -r '.[:10][]' 2>/dev/null || echo "None"
echo ""

# Ruby version requirement
echo "## Ruby Version"
RUBY_VER=$(echo "$RESPONSE" | jq -r '.required_ruby_version // "Not specified"')
echo "Required Ruby version: $RUBY_VER"
echo ""

# Links
echo "## More Info"
echo "RubyGems: https://rubygems.org/gems/$GEM"
echo "RubyDoc: https://www.rubydoc.info/gems/$GEM"
echo "Ruby Toolbox: https://www.ruby-toolbox.com/projects/$GEM"
echo ""

echo "=== End of RubyGems Report ==="
