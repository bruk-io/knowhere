---
type: llm
---

PASS if the answer says the rule did not load because Grep (or Glob, or a shell search) does not trigger a path-scoped rule - only Read, Write or Edit of a matching file does - and so the rule will appear once Claude reads or edits a migration file.
FAIL if it blames the glob, the file name, the body, or YAML syntax as the main cause, or if it does not say which tools trigger loading.
