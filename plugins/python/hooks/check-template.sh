#!/bin/bash
set -euo pipefail

input=$(cat)
file_path=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" <<< "$input")
filename=$(basename "$file_path")

if [[ "$filename" == "pyproject.toml" ]]; then
  cat <<'EOF'
{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Do not write pyproject.toml directly. Use the copier template from the python plugin instead. See the pyproject skill for the full copier command and all available options (project_type, app_module, port, license, etc)."}
EOF
fi
