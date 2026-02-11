#!/bin/bash
# find-alternatives.sh - Find and compare alternative libraries
# Usage: ./find-alternatives.sh <ecosystem> <package-name> [category]
# ecosystem: npm, pypi, cargo, maven, rubygems, nuget, go
#
# Uses libraries.io, npm trends, and awesome lists to find alternatives

set -e

ECOSYSTEM="${1:?Usage: $0 <ecosystem> <package-name> [category]}"
PACKAGE="${2:?Usage: $0 <ecosystem> <package-name> [category]}"
CATEGORY="${3:-}"

echo "=== Finding Alternatives to: $PACKAGE ($ECOSYSTEM) ==="
echo ""

# 1. Libraries.io - related projects
echo "## Libraries.io Related Projects"
LIBIO_ECOSYSTEM=""
case "$ECOSYSTEM" in
  npm) LIBIO_ECOSYSTEM="npm" ;;
  pypi|pip) LIBIO_ECOSYSTEM="pypi" ;;
  cargo) LIBIO_ECOSYSTEM="cargo" ;;
  maven) LIBIO_ECOSYSTEM="maven" ;;
  rubygems|gem) LIBIO_ECOSYSTEM="rubygems" ;;
  nuget) LIBIO_ECOSYSTEM="nuget" ;;
  go) LIBIO_ECOSYSTEM="go" ;;
esac

if [ -n "$LIBIO_ECOSYSTEM" ]; then
  echo "Check: https://libraries.io/$LIBIO_ECOSYSTEM/$PACKAGE"
  echo ""

  # Try to get package info from libraries.io (may need API key for full data)
  LIBIO_RESPONSE=$(curl -s "https://libraries.io/api/$LIBIO_ECOSYSTEM/$PACKAGE" 2>/dev/null || echo "{}")
  if echo "$LIBIO_RESPONSE" | jq -e '.keywords' >/dev/null 2>&1; then
    KEYWORDS=$(echo "$LIBIO_RESPONSE" | jq -r '.keywords // [] | join(", ")')
    echo "Keywords: $KEYWORDS"
    echo "Use these keywords to search for alternatives."
  fi
fi
echo ""

# 2. Ecosystem-specific comparison tools
echo "## Comparison Tools"
case "$ECOSYSTEM" in
  npm)
    echo "npm trends: https://npmtrends.com/$PACKAGE"
    echo "npm compare: https://npm-compare.com/$PACKAGE"
    echo "Moiva: https://moiva.io/?npm=$PACKAGE"
    echo ""

    # Try to get similar packages from npm search
    echo "### Similar npm packages"
    SEARCH=$(curl -s "https://registry.npmjs.org/-/v1/search?text=$PACKAGE&size=10" 2>/dev/null)
    echo "$SEARCH" | jq -r '.objects[] | "\(.package.name) - \(.package.description // "no description") (\(.package.links.npm))"' 2>/dev/null | head -10
    ;;

  pypi|pip)
    echo "Libraries.io: https://libraries.io/search?q=$PACKAGE&platforms=Pypi"
    echo "PyPI search: https://pypi.org/search/?q=$PACKAGE"
    echo ""

    # Search PyPI
    echo "### Similar PyPI packages"
    curl -s "https://pypi.org/simple/" 2>/dev/null | grep -i "$PACKAGE" | head -10 || echo "Search PyPI directly"
    ;;

  cargo)
    echo "Lib.rs: https://lib.rs/search?q=$PACKAGE"
    echo "Crates.io: https://crates.io/search?q=$PACKAGE"
    echo ""

    echo "### Similar crates"
    SEARCH=$(curl -s "https://crates.io/api/v1/crates?q=$PACKAGE&per_page=10&sort=downloads" 2>/dev/null)
    echo "$SEARCH" | jq -r '.crates[] | "\(.name): \(.description // "no description") - \(.downloads) downloads"' 2>/dev/null | head -10
    ;;

  maven)
    echo "MVN Repository: https://mvnrepository.com/search?q=$PACKAGE"
    echo "Search Maven: https://search.maven.org/search?q=$PACKAGE"
    ;;

  rubygems|gem)
    echo "Ruby Toolbox: https://www.ruby-toolbox.com/search?q=$PACKAGE"
    echo "RubyGems: https://rubygems.org/search?query=$PACKAGE"
    echo ""

    echo "### Similar gems"
    SEARCH=$(curl -s "https://rubygems.org/api/v1/search.json?query=$PACKAGE" 2>/dev/null)
    echo "$SEARCH" | jq -r '.[:10][] | "\(.name): \(.info // "no description" | .[0:80])..."' 2>/dev/null
    ;;

  nuget)
    echo "NuGet: https://www.nuget.org/packages?q=$PACKAGE"
    echo "NuGet Trends: https://nugettrends.com/packages?ids=$PACKAGE"
    ;;

  go)
    echo "pkg.go.dev: https://pkg.go.dev/search?q=$PACKAGE"
    echo "Go Report Card: https://goreportcard.com/report/$PACKAGE"
    ;;
esac
echo ""

# 3. GitHub Awesome Lists
echo "## Awesome Lists (curated alternatives)"
if [ -n "$CATEGORY" ]; then
  echo "Search for: awesome-$CATEGORY"
  echo "GitHub: https://github.com/search?q=awesome-$CATEGORY&type=repositories"
else
  echo "Search GitHub for curated lists:"
  echo "  - awesome-$PACKAGE"
  echo "  - awesome-{category} (e.g., awesome-react, awesome-python)"
  echo ""
  echo "Popular awesome lists:"
  echo "  https://github.com/sindresorhus/awesome"
fi
echo ""

# 4. AlternativeTo
echo "## AlternativeTo"
echo "https://alternativeto.net/software/$PACKAGE/"
echo ""

# 5. StackShare
echo "## StackShare"
echo "https://stackshare.io/search/q=$PACKAGE"
echo ""

# 6. GitHub search for similar
echo "## GitHub Search"
echo "Find similar projects:"
echo "https://github.com/search?q=$PACKAGE+alternative&type=repositories"
echo "https://github.com/search?q=$PACKAGE&type=repositories&s=stars&o=desc"
echo ""

# 7. Quick comparison template
echo "## Comparison Template"
echo ""
echo "When comparing alternatives, evaluate:"
echo ""
echo "| Criteria | $PACKAGE | Alternative 1 | Alternative 2 |"
echo "|----------|----------|---------------|---------------|"
echo "| Stars | | | |"
echo "| Downloads/week | | | |"
echo "| Last release | | | |"
echo "| Maintainers | | | |"
echo "| Dependencies | | | |"
echo "| Bundle size | | | |"
echo "| TypeScript | | | |"
echo "| License | | | |"
echo ""

echo "=== End of Alternatives Search ==="
