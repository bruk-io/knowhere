#!/bin/bash
# maven-package-info.sh - Fetch Maven Central package statistics
# Usage: ./maven-package-info.sh groupId:artifactId
# Example: ./maven-package-info.sh com.google.guava:guava

set -e

COORDS="${1:?Usage: $0 groupId:artifactId (e.g., com.google.guava:guava)}"

# Parse coordinates
GROUP_ID=$(echo "$COORDS" | cut -d: -f1)
ARTIFACT_ID=$(echo "$COORDS" | cut -d: -f2)

if [ -z "$GROUP_ID" ] || [ -z "$ARTIFACT_ID" ]; then
  echo "Invalid coordinates. Use format: groupId:artifactId"
  exit 1
fi

# Convert groupId to path format
GROUP_PATH=$(echo "$GROUP_ID" | tr '.' '/')

echo "=== Maven Central Package Info: $COORDS ==="
echo ""

# Search for the artifact
echo "## Package Metadata"
SEARCH_RESPONSE=$(curl -s "https://search.maven.org/solrsearch/select?q=g:$GROUP_ID+AND+a:$ARTIFACT_ID&rows=1&wt=json" 2>/dev/null)

if [ "$(echo "$SEARCH_RESPONSE" | jq '.response.numFound')" = "0" ]; then
  echo "Package not found: $COORDS"
  exit 1
fi

echo "$SEARCH_RESPONSE" | jq '.response.docs[0] | {
  groupId: .g,
  artifactId: .a,
  latestVersion: .latestVersion,
  packaging: .p,
  timestamp: (.timestamp / 1000 | strftime("%Y-%m-%d %H:%M:%S")),
  versionCount: .versionCount
}'
echo ""

# Get all versions
echo "## Version History (last 10)"
VERSIONS_RESPONSE=$(curl -s "https://search.maven.org/solrsearch/select?q=g:$GROUP_ID+AND+a:$ARTIFACT_ID&core=gav&rows=10&wt=json" 2>/dev/null)
echo "$VERSIONS_RESPONSE" | jq -r '.response.docs[] | "\(.v): \(.timestamp / 1000 | strftime("%Y-%m-%d"))"'
echo ""

# Get latest version
LATEST_VERSION=$(echo "$SEARCH_RESPONSE" | jq -r '.response.docs[0].latestVersion')

# Get POM for dependency info
echo "## Dependencies (from POM)"
POM_URL="https://repo1.maven.org/maven2/$GROUP_PATH/$ARTIFACT_ID/$LATEST_VERSION/$ARTIFACT_ID-$LATEST_VERSION.pom"
echo "POM URL: $POM_URL"
echo ""

# Try to fetch and parse POM
POM_CONTENT=$(curl -s "$POM_URL" 2>/dev/null || echo "")
if [ -n "$POM_CONTENT" ]; then
  # Count dependencies (basic XML parsing)
  DEP_COUNT=$(echo "$POM_CONTENT" | grep -c "<dependency>" || echo "0")
  echo "Approximate dependency count: $DEP_COUNT"

  # Extract license
  echo ""
  echo "## License"
  echo "$POM_CONTENT" | grep -A5 "<licenses>" | grep -oP '(?<=<name>).*(?=</name>)' | head -1 || echo "Not specified in POM"

  # Extract SCM/repository info
  echo ""
  echo "## Source Repository"
  echo "$POM_CONTENT" | grep -oP '(?<=<url>)https?://github.com[^<]+' | head -1 || echo "Not specified"
fi
echo ""

# MVN Repository link (community stats)
echo "## MVN Repository (community stats)"
echo "https://mvnrepository.com/artifact/$GROUP_ID/$ARTIFACT_ID"
echo ""

# Libraries.io link
echo "## Libraries.io"
echo "https://libraries.io/maven/$GROUP_ID:$ARTIFACT_ID"
echo ""

# Usage statistics (from libraries.io API if available)
echo "## Usage Information"
LIBIO_RESPONSE=$(curl -s "https://libraries.io/api/maven/$GROUP_ID:$ARTIFACT_ID?api_key=" 2>/dev/null || echo "{}")
if echo "$LIBIO_RESPONSE" | jq -e '.name' >/dev/null 2>&1; then
  echo "$LIBIO_RESPONSE" | jq '{
    dependent_repos_count: .dependent_repos_count,
    dependents_count: .dependents_count,
    rank: .rank,
    stars: .stars,
    forks: .forks
  }' 2>/dev/null || echo "Unable to fetch usage stats"
else
  echo "Usage stats require Libraries.io API key"
  echo "Set LIBRARIES_IO_API_KEY environment variable for more data"
fi
echo ""

# Security check links
echo "## Security"
echo "Snyk: https://snyk.io/vuln/maven:$GROUP_ID:$ARTIFACT_ID"
echo "OSV: https://osv.dev/list?ecosystem=Maven&q=$ARTIFACT_ID"
echo ""

echo "=== End of Maven Report ==="
