---
type: llm
---

PASS if Claude advises against it, with the reason that structured outputs guarantee the shape of JSON that code will parse, and nothing parses this description - a human reads free text - so the extra API call and schema add latency, cost and a moving part without adding a guarantee anyone needs; and it suggests keeping the skill as it is (the model drafting prose in the session, with any format wishes stated in the skill's prompt).
FAIL if Claude endorses the idea or sketches a structured-outputs script as the recommended path.
