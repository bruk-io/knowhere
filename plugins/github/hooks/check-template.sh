#!/bin/bash
set -euo pipefail

input=$(cat)
file_path=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" <<< "$input")
filename=$(basename "$file_path")

if [[ "$filename" == "ci.yml" || "$filename" == "ci.yaml" ]] && [[ ! -f "$file_path" ]]; then
  cat <<'EOF'
{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Do not create CI workflow files from scratch. Use the copier template from the github plugin instead. See the ci skill for the full copier command and all available options (language, project_type, package_name, etc)."}
EOF
fi
