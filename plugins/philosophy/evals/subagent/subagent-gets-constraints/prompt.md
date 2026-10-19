---
max_turns: 8
allowed_tools: [Agent]
append_system_prompt: "Do not ask questions."
tags: [subagent, capability, advisory]
---

Use the Agent tool to start one general-purpose subagent. Ask it to reply with the full text of any context a hook or plugin gave it at startup, word for word, or "none" if it was given none, and nothing else. Then report its reply word for word.
