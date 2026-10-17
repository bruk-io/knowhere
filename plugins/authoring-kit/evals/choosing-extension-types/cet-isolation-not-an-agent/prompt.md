---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [choosing-extension-types, capability]
---

I want Claude to be able to dig through our CI logs, find the failing test and report just its name and the error. The logs are huge, so this has to run in its own context and not flood my main conversation. I was going to write a subagent for it to get the isolation. Should this be a skill or a subagent?
