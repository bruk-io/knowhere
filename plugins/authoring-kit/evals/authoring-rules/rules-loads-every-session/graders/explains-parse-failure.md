---
type: llm
---

PASS if the answer says the unquoted glob starting with `*` is not valid YAML, so the frontmatter fails to parse and is dropped, which turns the rule into an unscoped one that loads in every session, and the fix is to quote the glob.
FAIL if it says the glob is fine, blames the location or the body, or proposes a fix other than making the frontmatter parse (for example rewriting the glob as `src/**/*.sql` without saying why quoting matters).
