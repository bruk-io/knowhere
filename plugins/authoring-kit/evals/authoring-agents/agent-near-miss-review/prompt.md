---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
tags: [authoring-agents, regression]
---

I need a careful read-only security review of this function - just tell me what is wrong with it, do not change anything.

```python
import sqlite3

def find_user(conn: sqlite3.Connection, name: str):
    cur = conn.cursor()
    cur.execute(f"SELECT id, email FROM users WHERE name = '{name}'")
    return cur.fetchall()
```
