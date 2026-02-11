#!/bin/bash
# security-check.sh - Deep security analysis for packages
# Usage: ./security-check.sh <ecosystem> <package-name>
# ecosystem: npm, pypi, cargo, maven, rubygems, nuget
#
# Checks: OSV database, GitHub advisories, known vulnerabilities

set -e

ECOSYSTEM="${1:?Usage: $0 <ecosystem> <package-name>}"
PACKAGE="${2:?Usage: $0 <ecosystem> <package-name>}"

echo "=== Security Analysis: $PACKAGE ($ECOSYSTEM) ==="
echo ""

# Map ecosystem to OSV ecosystem name
case "$ECOSYSTEM" in
  npm) OSV_ECOSYSTEM="npm" ;;
  pypi|pip) OSV_ECOSYSTEM="PyPI" ;;
  cargo) OSV_ECOSYSTEM="crates.io" ;;
  maven) OSV_ECOSYSTEM="Maven" ;;
  rubygems|gem) OSV_ECOSYSTEM="RubyGems" ;;
  nuget) OSV_ECOSYSTEM="NuGet" ;;
  go) OSV_ECOSYSTEM="Go" ;;
  *) OSV_ECOSYSTEM="$ECOSYSTEM" ;;
esac

# 1. OSV (Open Source Vulnerabilities) Database
echo "## OSV Database (osv.dev)"
echo "Checking Open Source Vulnerabilities database..."
OSV_RESPONSE=$(curl -s -X POST "https://api.osv.dev/v1/query" \
  -H "Content-Type: application/json" \
  -d "{\"package\": {\"name\": \"$PACKAGE\", \"ecosystem\": \"$OSV_ECOSYSTEM\"}}" 2>/dev/null)

if echo "$OSV_RESPONSE" | jq -e '.vulns' >/dev/null 2>&1; then
  VULN_COUNT=$(echo "$OSV_RESPONSE" | jq '.vulns | length')
  if [ "$VULN_COUNT" -gt 0 ]; then
    echo "WARNING: Found $VULN_COUNT vulnerabilities!"
    echo ""
    echo "$OSV_RESPONSE" | jq -r '.vulns[] | "[\(.severity // "UNKNOWN")] \(.id): \(.summary // "No summary")\n  Affected: \(.affected[0].ranges[0].events | map(select(.introduced or .fixed) | if .introduced then ">=\(.introduced)" else "<\(.fixed)" end) | join(" "))\n  More info: https://osv.dev/vulnerability/\(.id)\n"' 2>/dev/null | head -50
  else
    echo "No known vulnerabilities found in OSV database."
  fi
else
  echo "No vulnerabilities found or package not in OSV database."
fi
echo ""

# 2. GitHub Advisory Database
echo "## GitHub Advisory Database"
case "$ECOSYSTEM" in
  npm)
    GHSA_ECOSYSTEM="NPM"
    ;;
  pypi|pip)
    GHSA_ECOSYSTEM="PIP"
    ;;
  maven)
    GHSA_ECOSYSTEM="MAVEN"
    ;;
  rubygems|gem)
    GHSA_ECOSYSTEM="RUBYGEMS"
    ;;
  nuget)
    GHSA_ECOSYSTEM="NUGET"
    ;;
  go)
    GHSA_ECOSYSTEM="GO"
    ;;
  cargo)
    GHSA_ECOSYSTEM="RUST"
    ;;
  *)
    GHSA_ECOSYSTEM=""
    ;;
esac

if [ -n "$GHSA_ECOSYSTEM" ]; then
  echo "Checking GitHub Security Advisories..."
  GHSA_RESPONSE=$(gh api graphql -f query="
    query {
      securityVulnerabilities(first: 20, ecosystem: $GHSA_ECOSYSTEM, package: \"$PACKAGE\") {
        nodes {
          advisory {
            ghsaId
            summary
            severity
            publishedAt
            permalink
          }
          vulnerableVersionRange
          firstPatchedVersion {
            identifier
          }
        }
      }
    }
  " 2>/dev/null || echo "{}")

  if echo "$GHSA_RESPONSE" | jq -e '.data.securityVulnerabilities.nodes[0]' >/dev/null 2>&1; then
    GHSA_COUNT=$(echo "$GHSA_RESPONSE" | jq '.data.securityVulnerabilities.nodes | length')
    echo "Found $GHSA_COUNT advisories:"
    echo ""
    echo "$GHSA_RESPONSE" | jq -r '.data.securityVulnerabilities.nodes[] | "[\(.advisory.severity)] \(.advisory.ghsaId): \(.advisory.summary)\n  Vulnerable: \(.vulnerableVersionRange)\n  Fixed in: \(.firstPatchedVersion.identifier // "No fix yet")\n  Link: \(.advisory.permalink)\n"' 2>/dev/null
  else
    echo "No advisories found in GitHub Advisory Database."
  fi
else
  echo "Ecosystem not supported for GitHub Advisory lookup."
fi
echo ""

# 3. Snyk Vulnerability Database (web link)
echo "## Snyk Database"
case "$ECOSYSTEM" in
  npm) SNYK_URL="https://snyk.io/vuln/npm:$PACKAGE" ;;
  pypi|pip) SNYK_URL="https://snyk.io/vuln/pip:$PACKAGE" ;;
  maven) SNYK_URL="https://snyk.io/vuln/maven:$PACKAGE" ;;
  rubygems|gem) SNYK_URL="https://snyk.io/vuln/rubygems:$PACKAGE" ;;
  nuget) SNYK_URL="https://snyk.io/vuln/nuget:$PACKAGE" ;;
  cargo) SNYK_URL="https://snyk.io/vuln/cargo:$PACKAGE" ;;
  go) SNYK_URL="https://snyk.io/vuln/golang:$PACKAGE" ;;
  *) SNYK_URL="" ;;
esac
if [ -n "$SNYK_URL" ]; then
  echo "Check Snyk for detailed vulnerability info:"
  echo "$SNYK_URL"
fi
echo ""

# 4. Socket.dev (for npm - supply chain security)
if [ "$ECOSYSTEM" = "npm" ]; then
  echo "## Socket.dev (Supply Chain Security)"
  echo "Check for supply chain issues:"
  echo "https://socket.dev/npm/package/$PACKAGE"
  echo ""
  echo "Socket checks for:"
  echo "  - Typosquatting"
  echo "  - Dependency confusion"
  echo "  - Malicious code patterns"
  echo "  - Install scripts"
  echo "  - Network access"
  echo "  - Filesystem access"
  echo "  - Shell access"
  echo ""
fi

# 5. Deps.dev (Google's dependency insights)
echo "## deps.dev (Google Open Source Insights)"
case "$ECOSYSTEM" in
  npm) DEPS_URL="https://deps.dev/npm/$PACKAGE" ;;
  pypi|pip) DEPS_URL="https://deps.dev/pypi/$PACKAGE" ;;
  maven) DEPS_URL="https://deps.dev/maven/$PACKAGE" ;;
  cargo) DEPS_URL="https://deps.dev/cargo/$PACKAGE" ;;
  go) DEPS_URL="https://deps.dev/go/$PACKAGE" ;;
  *) DEPS_URL="" ;;
esac
if [ -n "$DEPS_URL" ]; then
  echo "Google's dependency analysis:"
  echo "$DEPS_URL"
  echo ""
  echo "Includes:"
  echo "  - OpenSSF Scorecard"
  echo "  - Dependency graph"
  echo "  - Version advisories"
  echo "  - License info"
fi
echo ""

# 6. Package-specific security commands
echo "## Local Security Scan Commands"
case "$ECOSYSTEM" in
  npm)
    echo "Run these commands after installing:"
    echo "  npm audit"
    echo "  npx socket-security scan"
    echo "  npx snyk test"
    ;;
  pypi|pip)
    echo "Run these commands after installing:"
    echo "  pip-audit"
    echo "  safety check"
    echo "  snyk test --file=requirements.txt"
    ;;
  cargo)
    echo "Run these commands in your project:"
    echo "  cargo audit"
    echo "  cargo deny check"
    ;;
  go)
    echo "Run these commands in your project:"
    echo "  govulncheck ./..."
    echo "  go list -m -json all | nancy sleuth"
    ;;
  rubygems|gem)
    echo "Run these commands:"
    echo "  bundle audit"
    echo "  bundler-audit check"
    ;;
  maven)
    echo "Run these commands:"
    echo "  mvn org.owasp:dependency-check-maven:check"
    ;;
  nuget)
    echo "Run these commands:"
    echo "  dotnet list package --vulnerable"
    ;;
esac
echo ""

# 7. Summary
echo "## Security Summary"
echo "Automated checks completed. For comprehensive analysis:"
echo "1. Review any vulnerabilities found above"
echo "2. Check the linked resources (Snyk, Socket, deps.dev)"
echo "3. Run local security scans after installation"
echo "4. Review the package's security policy (SECURITY.md)"
echo "5. Check if maintainers respond quickly to security issues"
echo ""

echo "=== End of Security Analysis ==="
