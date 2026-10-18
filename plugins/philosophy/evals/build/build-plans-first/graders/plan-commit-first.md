---
type: llm
---

PASS if the answer shows the branch's commits oldest first, and the first commit changes only a file under intent/demo/plans/ while a later commit changes greet.py.
FAIL if the first commit changes greet.py or any file outside intent/demo/plans/, if greet.py was never committed, or if no commit log is shown.
