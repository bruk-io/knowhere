#!/bin/bash
set -euo pipefail

input=$(cat)
file_path=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" <<< "$input")
cwd=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))" <<< "$input")
filename=$(basename "$file_path")

if [[ "$filename" == "Makefile" ]]; then
  # Only intercept in Rust projects
  target_dir=$(dirname "$file_path")
  if [[ -f "$target_dir/Cargo.toml" ]] || [[ -f "$cwd/Cargo.toml" ]]; then
    cat <<'EOF'
{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Do not write Makefile directly in Rust projects. Use the copier template from the rust plugin instead. See the makefile skill for the full copier command and options (app_name, project_type, port)."}
EOF
  fi
fi
