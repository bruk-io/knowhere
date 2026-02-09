#!/bin/bash
set -euo pipefail

input=$(cat)
file_path=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" <<< "$input")
filename=$(basename "$file_path")

if [[ "$filename" == "pyproject.toml" && ! -f "$file_path" ]]; then
  cat <<'EOF'
{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Do not create pyproject.toml from scratch. Use the copier template from the python plugin instead. See the project skill for the full copier command and all available options (project_type, has_mcp, has_tui, is_async, etc)."}
EOF
fi
