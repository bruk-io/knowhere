#!/bin/bash
set -euo pipefail

input=$(cat)
file_path=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" <<< "$input")
filename=$(basename "$file_path")

case "$filename" in
  Dockerfile|Dockerfile.*)
    cat <<'EOF'
{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Do not write Dockerfiles directly. Use the copier template from the containers plugin instead. See the dockerfile skill for the full copier command — templates are available for Python, Node.js, Go, and Rust with multi-stage builds, entrypoint.sh, and security hardening."}
EOF
    ;;
  entrypoint.sh)
    cat <<'EOF'
{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Do not write entrypoint.sh directly. It is generated alongside the Dockerfile by the containers plugin copier template. See the dockerfile skill."}
EOF
    ;;
esac
