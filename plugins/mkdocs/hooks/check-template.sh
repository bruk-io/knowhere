#!/bin/bash
set -euo pipefail

input=$(cat)
file_path=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" <<< "$input")
filename=$(basename "$file_path")

if [[ "$filename" == "mkdocs.yml" || "$filename" == "mkdocs.yaml" ]] && [[ ! -f "$file_path" ]]; then
  cat <<'EOF'
{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Do not create mkdocs.yml from scratch. Use the copier template from the mkdocs plugin instead. See the docs skill for the full copier command and all available options (project_name, description, theme options, etc)."}
EOF
fi
