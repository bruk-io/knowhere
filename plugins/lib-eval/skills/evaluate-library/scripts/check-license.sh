#!/bin/bash
# check-license.sh - Check license compatibility for a package
# Usage: ./check-license.sh <ecosystem> <package-name> [allowed-licenses]
# allowed-licenses: comma-separated list (default: MIT,Apache-2.0,BSD-2-Clause,BSD-3-Clause,ISC,0BSD,Unlicense)
#
# Examples:
#   ./check-license.sh npm lodash
#   ./check-license.sh npm lodash "MIT,Apache-2.0"
#   ./check-license.sh pypi requests "MIT,BSD-3-Clause,Apache-2.0"

set -e

ECOSYSTEM="${1:?Usage: $0 <ecosystem> <package-name> [allowed-licenses]}"
PACKAGE="${2:?Usage: $0 <ecosystem> <package-name> [allowed-licenses]}"
ALLOWED="${3:-MIT,Apache-2.0,BSD-2-Clause,BSD-3-Clause,ISC,0BSD,Unlicense,CC0-1.0,WTFPL}"

echo "=== License Check: $PACKAGE ($ECOSYSTEM) ==="
echo ""
echo "Allowed licenses: $ALLOWED"
echo ""

# Convert allowed licenses to array for checking
IFS=',' read -ra ALLOWED_ARRAY <<< "$ALLOWED"

# Function to check if license is allowed
check_allowed() {
  local license="$1"
  # Normalize license string
  license=$(echo "$license" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9.-]//g')

  for allowed in "${ALLOWED_ARRAY[@]}"; do
    allowed_upper=$(echo "$allowed" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9.-]//g')
    if [[ "$license" == *"$allowed_upper"* ]] || [[ "$allowed_upper" == *"$license"* ]]; then
      return 0
    fi
  done
  return 1
}

# Fetch license based on ecosystem
case "$ECOSYSTEM" in
  npm)
    echo "## Checking npm package..."
    RESPONSE=$(curl -s "https://registry.npmjs.org/$PACKAGE/latest" 2>/dev/null)
    LICENSE=$(echo "$RESPONSE" | jq -r '.license // "UNKNOWN"')
    REPO=$(echo "$RESPONSE" | jq -r '.repository.url // "unknown"')
    ;;

  pypi|pip)
    echo "## Checking PyPI package..."
    RESPONSE=$(curl -s "https://pypi.org/pypi/$PACKAGE/json" 2>/dev/null)
    LICENSE=$(echo "$RESPONSE" | jq -r '.info.license // "UNKNOWN"')
    REPO=$(echo "$RESPONSE" | jq -r '.info.project_urls.Repository // .info.home_page // "unknown"')
    ;;

  cargo)
    echo "## Checking crates.io package..."
    RESPONSE=$(curl -s "https://crates.io/api/v1/crates/$PACKAGE" 2>/dev/null)
    VERSION=$(echo "$RESPONSE" | jq -r '.crate.max_version')
    VERSION_RESPONSE=$(curl -s "https://crates.io/api/v1/crates/$PACKAGE/$VERSION" 2>/dev/null)
    LICENSE=$(echo "$VERSION_RESPONSE" | jq -r '.version.license // "UNKNOWN"')
    REPO=$(echo "$RESPONSE" | jq -r '.crate.repository // "unknown"')
    ;;

  maven)
    echo "## Checking Maven package..."
    # Parse groupId:artifactId
    GROUP_ID=$(echo "$PACKAGE" | cut -d: -f1)
    ARTIFACT_ID=$(echo "$PACKAGE" | cut -d: -f2)
    GROUP_PATH=$(echo "$GROUP_ID" | tr '.' '/')

    SEARCH=$(curl -s "https://search.maven.org/solrsearch/select?q=g:$GROUP_ID+AND+a:$ARTIFACT_ID&rows=1&wt=json" 2>/dev/null)
    VERSION=$(echo "$SEARCH" | jq -r '.response.docs[0].latestVersion')

    POM_URL="https://repo1.maven.org/maven2/$GROUP_PATH/$ARTIFACT_ID/$VERSION/$ARTIFACT_ID-$VERSION.pom"
    POM=$(curl -s "$POM_URL" 2>/dev/null)
    LICENSE=$(echo "$POM" | grep -oP '(?<=<name>).*(?=</name>)' | head -1 || echo "UNKNOWN")
    REPO=$(echo "$POM" | grep -oP 'https?://github.com[^<]+' | head -1 || echo "unknown")
    ;;

  rubygems|gem)
    echo "## Checking RubyGems package..."
    RESPONSE=$(curl -s "https://rubygems.org/api/v1/gems/$PACKAGE.json" 2>/dev/null)
    LICENSE=$(echo "$RESPONSE" | jq -r '.licenses[0] // "UNKNOWN"')
    REPO=$(echo "$RESPONSE" | jq -r '.source_code_uri // .homepage_uri // "unknown"')
    ;;

  nuget)
    echo "## Checking NuGet package..."
    PACKAGE_LOWER=$(echo "$PACKAGE" | tr '[:upper:]' '[:lower:]')
    SEARCH=$(curl -s "https://azuresearch-usnc.nuget.org/query?q=packageid:$PACKAGE&take=1" 2>/dev/null)
    LICENSE=$(echo "$SEARCH" | jq -r '.data[0].licenseUrl // "UNKNOWN"')
    # NuGet often returns URL, try to extract license type
    if [[ "$LICENSE" == *"mit"* ]]; then LICENSE="MIT"; fi
    if [[ "$LICENSE" == *"apache"* ]]; then LICENSE="Apache-2.0"; fi
    REPO="https://www.nuget.org/packages/$PACKAGE"
    ;;

  go)
    echo "## Checking Go module..."
    # Go modules are trickier - check GitHub if possible
    if [[ "$PACKAGE" == github.com/* ]]; then
      REPO="https://$PACKAGE"
      # Try to get license from GitHub
      REPO_PATH=$(echo "$PACKAGE" | sed 's|github.com/||')
      GH_RESPONSE=$(gh api "repos/$REPO_PATH" --jq '.license.spdx_id' 2>/dev/null || echo "UNKNOWN")
      LICENSE="$GH_RESPONSE"
    else
      LICENSE="UNKNOWN"
      REPO="https://pkg.go.dev/$PACKAGE"
    fi
    ;;

  *)
    echo "Unknown ecosystem: $ECOSYSTEM"
    exit 1
    ;;
esac

echo ""
echo "## License Information"
echo "Package: $PACKAGE"
echo "License: $LICENSE"
echo "Repository: $REPO"
echo ""

# Check if license is allowed
echo "## Compatibility Check"
if check_allowed "$LICENSE"; then
  echo "✅ PASS: License '$LICENSE' is in the allowed list"
  RESULT="PASS"
else
  echo "❌ FAIL: License '$LICENSE' is NOT in the allowed list"
  RESULT="FAIL"
fi
echo ""

# License classification
echo "## License Classification"
case "$(echo "$LICENSE" | tr '[:lower:]' '[:upper:]')" in
  *MIT*|*ISC*|*BSD*|*APACHE*|*UNLICENSE*|*CC0*|*0BSD*|*WTFPL*)
    echo "Type: Permissive"
    echo "Risk: Low"
    echo "Notes: Generally safe for commercial use, attribution usually required"
    ;;
  *GPL*|*LGPL*|*AGPL*)
    echo "Type: Copyleft"
    echo "Risk: Medium to High"
    echo "Notes: May require source disclosure. Check with legal."
    if [[ "$LICENSE" == *"AGPL"* ]]; then
      echo "WARNING: AGPL requires sharing source even for network use!"
    fi
    ;;
  *MPL*)
    echo "Type: Weak Copyleft"
    echo "Risk: Medium"
    echo "Notes: File-level copyleft. Modified files must be shared."
    ;;
  *UNKNOWN*|*"")
    echo "Type: UNKNOWN"
    echo "Risk: High"
    echo "Notes: No license means all rights reserved. DO NOT USE without clarification."
    ;;
  *)
    echo "Type: Other/Custom"
    echo "Risk: Unknown"
    echo "Notes: Review license text carefully. Consider legal review."
    ;;
esac
echo ""

# Common license compatibility
echo "## Quick Compatibility Guide"
echo ""
echo "Your project license -> Can use these libraries:"
echo "  MIT/BSD/ISC -> MIT, BSD, ISC, Apache-2.0, 0BSD, Unlicense"
echo "  Apache-2.0  -> MIT, BSD, ISC, Apache-2.0 (NOT GPLv2)"
echo "  GPL-3.0     -> MIT, BSD, ISC, Apache-2.0, GPL-3.0, LGPL-3.0"
echo "  LGPL-3.0    -> MIT, BSD, ISC, Apache-2.0, LGPL-3.0"
echo "  Proprietary -> MIT, BSD, ISC, Apache-2.0 (check each carefully)"
echo ""

# SPDX reference
echo "## SPDX License Reference"
echo "https://spdx.org/licenses/"
echo "https://choosealicense.com/licenses/"
echo ""

# Return appropriate exit code
if [ "$RESULT" = "PASS" ]; then
  exit 0
else
  exit 1
fi
