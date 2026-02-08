#!/bin/bash
set -euo pipefail

input=$(cat)
file_path=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" <<< "$input")
filename=$(basename "$file_path")

# Guard files that match copier template outputs
if [[ "$filename" =~ ^.*\.py$ ]] && [[ "$file_path" =~ \.tcss$ || "$filename" == "screens.py" ]]; then
  # Only guard if the file looks like a Textual app scaffold
  :
fi

# Check for .tcss files (Textual CSS stylesheets)
if [[ "$filename" =~ \.tcss$ ]]; then
  cat <<'EOF'
{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Do not write .tcss files directly. Use the copier template from the textual plugin instead. See the app skill for the full copier command and all available options (app_name, app_class, include_header, etc)."}
EOF
fi
