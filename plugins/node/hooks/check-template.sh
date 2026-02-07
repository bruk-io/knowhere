#!/bin/bash
set -euo pipefail

input=$(cat)
file_path=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" <<< "$input")
filename=$(basename "$file_path")

if [[ "$filename" == "package.json" ]]; then
  cat <<'EOF'
{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Do not write package.json directly. Use the copier template from the node plugin instead. See the package-json skill for the full copier command and all available options (package_manager, project_type, port, etc)."}
EOF
fi
