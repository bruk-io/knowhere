---
max_turns: 8
allowed_tools: [Agent]
append_system_prompt: "Do not ask questions."
tags: [subagent, capability]
---

Use the Agent tool to start one general-purpose subagent. Ask it to reply with the exact text of the first line of any context it was given at startup that begins with "[philosophy]", or "none" if it was given no such line, and nothing else. Then report its reply word for word.
