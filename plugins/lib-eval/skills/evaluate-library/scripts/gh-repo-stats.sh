#!/bin/bash
# gh-repo-stats.sh - Fetch comprehensive GitHub repository statistics
# Usage: ./gh-repo-stats.sh owner/repo
#
# Requires: gh CLI authenticated

set -e

REPO="${1:?Usage: $0 owner/repo}"

echo "=== GitHub Repository Stats: $REPO ==="
echo ""

# Basic repo info
echo "## Basic Info"
gh repo view "$REPO" --json name,description,url,homepageUrl,createdAt,pushedAt,stargazerCount,forkCount,isArchived,isFork,licenseInfo,primaryLanguage \
  --template '
Name: {{.name}}
Description: {{.description}}
URL: {{.url}}
Homepage: {{.homepageUrl}}
Created: {{.createdAt}}
Last Push: {{.pushedAt}}
Stars: {{.stargazerCount}}
Forks: {{.forkCount}}
Archived: {{.isArchived}}
Is Fork: {{.isFork}}
License: {{if .licenseInfo}}{{.licenseInfo.name}}{{else}}None{{end}}
Primary Language: {{if .primaryLanguage}}{{.primaryLanguage.name}}{{else}}Unknown{{end}}
'

# Get topics separately
echo -n "Topics: "
gh api "repos/$REPO/topics" --jq '.names | join(", ")' 2>/dev/null || echo "None"
echo ""

# Issues stats
echo "## Issues"
gh api "repos/$REPO" --jq '{
  open_issues: .open_issues_count
}' 2>/dev/null | jq -r 'to_entries | .[] | "\(.key): \(.value)"' || echo "Unable to fetch"
echo ""

# Recent issues activity (last 30 days)
echo "## Recent Issue Activity (last 30 days)"
THIRTY_DAYS_AGO=$(date -v-30d +%Y-%m-%d 2>/dev/null || date -d "30 days ago" +%Y-%m-%d 2>/dev/null || echo "")
if [ -n "$THIRTY_DAYS_AGO" ]; then
  RECENT_ISSUES=$(gh issue list -R "$REPO" -s all --json createdAt -L 100 2>/dev/null | jq --arg date "$THIRTY_DAYS_AGO" '[.[] | select(.createdAt >= $date)] | length' || echo "N/A")
  echo "Issues opened in last 30 days: $RECENT_ISSUES"
fi
echo ""

# Pull requests
echo "## Pull Requests"
OPEN_PRS=$(gh pr list -R "$REPO" -s open --json number 2>/dev/null | jq 'length' || echo "N/A")
echo "Open PRs: $OPEN_PRS"
echo ""

# Contributors (top 10)
echo "## Top Contributors (by commits)"
gh api "repos/$REPO/contributors?per_page=10" --jq '.[] | "\(.login): \(.contributions) commits"' 2>/dev/null || echo "Unable to fetch contributors"
echo ""

# Total contributor count
CONTRIBUTOR_COUNT=$(gh api "repos/$REPO" --jq '.subscribers_count' 2>/dev/null || echo "N/A")
echo "Watchers/Subscribers: $CONTRIBUTOR_COUNT"
echo ""

# Commit activity
echo "## Commit Activity"
gh api "repos/$REPO/stats/commit_activity" --jq '
  (map(.total) | add) as $yearly_total |
  (if length > 0 then .[length-1].total else 0 end) as $last_week |
  (if length >= 4 then .[length-4:] | map(.total) | add else 0 end) as $last_month |
  "Commits last week: \($last_week)\nCommits last month: \($last_month)\nCommits last year: \($yearly_total)"
' 2>/dev/null || echo "Unable to fetch commit activity (may need to wait for GitHub to compute)"
echo ""

# Releases
echo "## Recent Releases (last 5)"
gh release list -R "$REPO" -L 5 2>/dev/null || echo "No releases found"
echo ""

# Latest release age
echo "## Latest Release Info"
gh api "repos/$REPO/releases/latest" --jq '
  "Tag: \(.tag_name)\nPublished: \(.published_at)\nName: \(.name)"
' 2>/dev/null || echo "No releases found"
echo ""

# Dependencies (if package.json exists for JS projects)
echo "## Project Type Detection"
gh api "repos/$REPO/contents/package.json" --jq '.name' >/dev/null 2>&1 && {
  echo "JavaScript/Node.js project detected (package.json)"
  echo ""
  echo "### package.json Dependencies"
  gh api "repos/$REPO/contents/package.json" --jq '.content' 2>/dev/null | base64 -d 2>/dev/null | jq '{
    dependencies: (.dependencies | keys | length // 0),
    devDependencies: (.devDependencies | keys | length // 0),
    peerDependencies: (.peerDependencies | keys | length // 0)
  }' 2>/dev/null || echo "Unable to parse package.json"
} || true

gh api "repos/$REPO/contents/pyproject.toml" --jq '.name' >/dev/null 2>&1 && echo "Python project detected (pyproject.toml)" || true
gh api "repos/$REPO/contents/Cargo.toml" --jq '.name' >/dev/null 2>&1 && echo "Rust project detected (Cargo.toml)" || true
gh api "repos/$REPO/contents/go.mod" --jq '.name' >/dev/null 2>&1 && echo "Go project detected (go.mod)" || true
gh api "repos/$REPO/contents/pom.xml" --jq '.name' >/dev/null 2>&1 && echo "Java/Maven project detected (pom.xml)" || true

echo ""

# Code frequency
echo "## Code Frequency (additions/deletions per week, last 4 weeks)"
gh api "repos/$REPO/stats/code_frequency" --jq 'if length >= 4 then .[-4:] | .[] | "Week: +\(.[1]) -\(if .[2] then .[2] * -1 else 0 end)" else "Not enough data" end' 2>/dev/null || echo "Unable to fetch code frequency"
echo ""

echo "=== End of Report ==="
