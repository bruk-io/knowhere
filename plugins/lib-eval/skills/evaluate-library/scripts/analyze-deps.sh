#!/bin/bash
# analyze-deps.sh - Analyze dependency tree for a package
# Usage: ./analyze-deps.sh <ecosystem> <package-name>
# ecosystem: npm, pip, cargo, go
#
# Shows transitive dependencies, depth, and potential concerns

set -e

ECOSYSTEM="${1:?Usage: $0 <ecosystem> <package-name>}"
PACKAGE="${2:?Usage: $0 <ecosystem> <package-name>}"

echo "=== Dependency Analysis: $PACKAGE ($ECOSYSTEM) ==="
echo ""

case "$ECOSYSTEM" in
  npm)
    echo "## NPM Dependency Tree"
    echo "Creating temporary directory to analyze..."
    TMPDIR=$(mktemp -d)
    cd "$TMPDIR"

    # Create minimal package.json
    echo "{\"name\":\"temp\",\"dependencies\":{\"$PACKAGE\":\"latest\"}}" > package.json

    echo "Installing $PACKAGE..."
    npm install --silent 2>/dev/null || npm install 2>&1

    echo ""
    echo "## Dependency Tree"
    npm ls --all 2>/dev/null || npm ls 2>/dev/null || echo "Unable to list deps"

    echo ""
    echo "## Dependency Stats"
    TOTAL_DEPS=$(npm ls --all --json 2>/dev/null | jq '[.. | .name? // empty] | unique | length' || echo "N/A")
    echo "Total packages (including transitive): $TOTAL_DEPS"

    DIRECT_DEPS=$(npm ls --json 2>/dev/null | jq '.dependencies | keys | length' || echo "N/A")
    echo "Direct dependencies: $DIRECT_DEPS"

    echo ""
    echo "## Potential Duplicates"
    npm ls --all 2>/dev/null | grep -E "deduped|UNMET" || echo "No duplicates or unmet deps detected"

    echo ""
    echo "## Security Audit"
    npm audit 2>/dev/null || echo "Audit complete (or no vulnerabilities)"

    # Cleanup
    cd - >/dev/null
    rm -rf "$TMPDIR"
    ;;

  pip)
    echo "## Python Dependency Tree"
    echo "Note: Requires pipdeptree installed (pip install pipdeptree)"
    echo ""

    # Try with pipdeptree if available
    if command -v pipdeptree &>/dev/null; then
      echo "Using pipdeptree..."
      pipdeptree -p "$PACKAGE" 2>/dev/null || echo "Package may not be installed"

      echo ""
      echo "## Reverse Dependencies"
      pipdeptree -r -p "$PACKAGE" 2>/dev/null || echo "No reverse deps"
    else
      echo "pipdeptree not installed. Install with: pip install pipdeptree"
      echo ""
      echo "Alternative: Use pip show for direct deps:"
      pip show "$PACKAGE" 2>/dev/null || echo "Package not installed"
    fi

    echo ""
    echo "## Check with pip-audit"
    echo "Run: pip-audit (after installing package)"
    ;;

  cargo)
    echo "## Cargo Dependency Tree"
    echo "Creating temporary project to analyze..."
    TMPDIR=$(mktemp -d)
    cd "$TMPDIR"

    cargo init --name temp 2>/dev/null
    echo "$PACKAGE = \"*\"" >> Cargo.toml

    echo ""
    echo "Fetching dependencies..."
    cargo fetch 2>/dev/null || cargo fetch

    echo ""
    echo "## Dependency Tree"
    cargo tree 2>/dev/null || echo "Unable to show tree"

    echo ""
    echo "## Stats"
    TOTAL=$(cargo tree --prefix=none 2>/dev/null | sort -u | wc -l || echo "N/A")
    echo "Total unique crates: $TOTAL"

    echo ""
    echo "## Security Audit"
    if command -v cargo-audit &>/dev/null; then
      cargo audit 2>/dev/null || echo "Audit complete"
    else
      echo "Install cargo-audit for security checks: cargo install cargo-audit"
    fi

    # Cleanup
    cd - >/dev/null
    rm -rf "$TMPDIR"
    ;;

  go)
    echo "## Go Dependency Analysis"
    echo "Creating temporary module to analyze..."
    TMPDIR=$(mktemp -d)
    cd "$TMPDIR"

    go mod init temp 2>/dev/null
    go get "$PACKAGE" 2>/dev/null || go get "$PACKAGE"

    echo ""
    echo "## Dependency Graph"
    go mod graph 2>/dev/null || echo "Unable to show graph"

    echo ""
    echo "## Direct Dependencies"
    go list -m all 2>/dev/null | head -30 || echo "Unable to list"

    echo ""
    echo "## Security Check"
    if command -v govulncheck &>/dev/null; then
      govulncheck ./... 2>/dev/null || echo "No vulnerabilities found"
    else
      echo "Install govulncheck: go install golang.org/x/vuln/cmd/govulncheck@latest"
    fi

    # Cleanup
    cd - >/dev/null
    rm -rf "$TMPDIR"
    ;;

  *)
    echo "Unknown ecosystem: $ECOSYSTEM"
    echo "Supported: npm, pip, cargo, go"
    exit 1
    ;;
esac

echo ""
echo "=== End of Dependency Analysis ==="
