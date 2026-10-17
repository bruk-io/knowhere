---
type: llm
---

PASS if Claude tells the user that the citations feature and structured outputs (schema-constrained JSON) cannot be used in the same request, and that the tool therefore builds the JSON envelope itself in code from the citation blocks the API returns (json.dumps or equivalent), rather than asking the model to emit JSON.
FAIL if Claude combines citations with a JSON schema / structured output setting in one request, or asks the model via prompt to "respond in JSON" without explaining why the schema guarantee cannot be used here.
