#!/bin/bash
# The demo intent, with a constraint that pulls against CLAUDE.md's rule that names are
# never logged. The spec has to flag that conflict, not settle it.
set -eu
bash "$(dirname "$0")/../../_scaffold/demo-repo.sh" intent
python3 - <<'PY'
from pathlib import Path
intent = Path("intent/demo/intent.md")
text = intent.read_text()
text = text.replace(
    '- `greet()` with no name keeps returning "Hello!".\n',
    '- `greet()` with no name keeps returning "Hello!".\n'
    "- Every greeting is logged with the person's name, for the audit team.\n",
)
intent.write_text(text)
PY
git commit -q -am "intent: log greetings for the audit"
git push -q origin main
