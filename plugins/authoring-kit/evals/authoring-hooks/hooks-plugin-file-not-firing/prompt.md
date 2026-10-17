---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-hooks, regression]
---

My plugin's hook never fires. The file hooks/hooks.json in the plugin root is:

```json
{
  "PostToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        { "type": "command", "command": "sh \"${CLAUDE_PLUGIN_ROOT}/hooks/format.sh\"", "timeout": 30 }
      ]
    }
  ]
}
```

The script is executable and works when I run it by hand with a sample payload on stdin. I restarted Claude Code, the plugin is enabled, but /hooks does not list it and nothing appears in the transcript after an edit. What is wrong?
