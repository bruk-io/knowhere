"""The hook's gate: which paths are authoring artifacts, and what a hook
payload asks for, decided from the payload's bytes where that is safe.

Kept apart from claude_lint.py and importing nothing but `os` because hook
mode runs after every Read, Write and Edit, nearly always on a file that is not
an artifact. The launcher imports only this module for that case, so it costs
little more than starting the interpreter; the linter imports the same names,
so there is one definition of "artifact".
"""

import os

KINDS = ("skill", "rule", "agent", "memory", "hooks", "plugin")
MEMORY_NAMES = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")
# Every artifact's file name ends in one of these. `classify --extensions`
# prints them, and hooks/lint-on-write.sh gates on the same set (a test holds
# the two together), so a new artifact extension is added here first.
ARTIFACT_SUFFIXES = (".md", ".json")


# ---- classification (the single definition of "authoring artifact") ---------
#
# The launcher imports this module alone to decide a hook payload, so nothing
# here may import more than `os` at module level (a test holds that).

def _is_plugin_root(directory):
    return os.path.isdir(os.path.join(directory, ".claude-plugin"))


def in_claude_dir(path, sub):
    """Is the file somewhere under a `.claude/<sub>/` directory?"""
    dirs = os.path.abspath(path).split(os.sep)[:-1]
    return any(a == ".claude" and b == sub for a, b in zip(dirs, dirs[1:]))


def classify(path):
    """Return the artifact kind for a path, or None. Used by lint, the tree
    walk and hook mode alike, so there is exactly one path list."""
    p = os.path.abspath(path)
    parts = p.split(os.sep)
    base = parts[-1]
    parent = parts[-2] if len(parts) >= 2 else ""
    grand = os.path.dirname(os.path.dirname(p))

    def under_claude(sub):
        return in_claude_dir(p, sub)

    if not base.endswith(ARTIFACT_SUFFIXES):
        return None
    if base.endswith(".md"):
        if base == "SKILL.md" or under_claude("commands"):
            return "skill"
        if under_claude("rules"):
            return "rule"
        if under_claude("agents"):
            return "agent"
        if base in MEMORY_NAMES:
            # AGENTS.md is read as project memory (and its @imports expanded)
            # when no CLAUDE.md is present - Claude Code 2.1.277 and later.
            return "memory"
        if parent == "commands" and _is_plugin_root(grand):
            return "skill"
        if parent == "rules" and _is_plugin_root(grand):
            return "rule"
        if parent == "agents" and _is_plugin_root(grand):
            return "agent"
        return None
    if base.endswith(".json"):
        if parent == ".claude-plugin" and base == "plugin.json":
            return "plugin"
        if parent == "hooks" and base == "hooks.json":
            return "hooks"
        if parent == ".claude" and (base == "settings.json" or (
                base.startswith("settings.") and len(base) > len("settings..json"))):
            return "hooks"
    return None


HOOK_PEEK_BYTES = 65536
# The plugin's read-only auditor agent, as its `name` states it. A hook payload
# from it carries "agent_type":"<plugin>:authoring-auditor" (observed on
# 2.1.296; bare, without the plugin prefix, when the file is copied into a
# project), so a payload without these bytes is not the auditor's.
AUDITOR_AGENT = "authoring-auditor"
_AUDITOR_TAIL = AUDITOR_AGENT.encode() + b'"'
# The event name of a call that has not run yet, compact and spaced. As with
# the file path leads below, the quotes make these the real key: file content
# riding in another event cannot contain them unescaped.
_PRE_TOOL_LEADS = (b'"hook_event_name":"PreToolUse"', b'"hook_event_name": "PreToolUse"')
# How Claude Code (compact) and json.dumps (spaced) write the start of a file
# tool's input. Inside a JSON string a quote is written \", so neither byte
# sequence can occur in file content: a match is the real key.
_FILE_PATH_LEADS = (b'"tool_input":{"file_path":"', b'"tool_input": {"file_path": "')


def peek_file_path(raw):
    """The file path a hook payload names, read from its first bytes without
    parsing it; None when that cannot be done safely and the caller must parse.

    A Read payload carries the whole file in tool_response, after tool_input,
    so for the usual case - a file that is not an artifact - the megabytes
    behind the path are never decoded."""
    head = raw[:HOOK_PEEK_BYTES]
    for lead in _FILE_PATH_LEADS:
        at = head.find(lead)
        if at < 0:
            continue
        start = at + len(lead)
        end = head.find(b'"', start)
        if end < 0 or b"\\" in head[start:end]:
            return None                  # cut off, or escaped: leave it to the parser
        try:
            return head[start:end].decode("utf-8")
        except UnicodeDecodeError:
            return None
    return None


def read_hook_payload(raw):
    """What hook mode has to do with a payload, decided as cheaply as possible:

      ("reset", event)                    a SessionStart event
      ("guard", event)                    a Bash call about to run in an agent whose name ends
                                          like the auditor's (the caller checks the plugin)
      ("touch", event, file_path, path)   a file tool used on an existing artifact
      None                                anything else

    file_path is the path as the payload gives it, path the resolved one.
    Never raises."""
    try:
        if isinstance(raw, str):
            raw = raw.encode("utf-8", "replace")
        starting = b"SessionStart" in raw[:HOOK_PEEK_BYTES]
        if not starting and any(lead in raw for lead in _PRE_TOOL_LEADS):
            if _AUDITOR_TAIL not in raw:
                return None
            import json
            event = json.loads(raw)
            guarded = (event.get("hook_event_name") == "PreToolUse" and event.get("tool_name") == "Bash"
                       and isinstance(event.get("agent_type"), str)
                       and event["agent_type"].rpartition(":")[2] == AUDITOR_AGENT)
            return ("guard", event) if guarded else None
        # A JSON string that ends in an artifact suffix is followed at once by
        # its closing quote, so a payload with no `.md"` or `.json"` in it
        # cannot name an artifact - and need not even be parsed (parsing means
        # importing json, which is a fifth of this path's cost).
        if not starting and not any(suffix.encode() + b'"' in raw for suffix in ARTIFACT_SUFFIXES):
            return None
        if not starting:
            peeked = peek_file_path(raw)
            if peeked is not None and os.path.isabs(peeked) and classify(peeked) is None:
                return None
        import json
        event = json.loads(raw)
        if event.get("hook_event_name") == "SessionStart":
            return ("reset", event)
        file_path = event["tool_input"]["file_path"]
        if not isinstance(file_path, str) or not file_path:
            return None
        path = file_path
        if not os.path.isabs(path) and isinstance(event.get("cwd"), str):
            path = os.path.join(event["cwd"], path)
        if classify(path) is None or not os.path.isfile(path):
            return None
        return ("touch", event, file_path, path)
    except Exception:  # noqa: BLE001 - a hook must never fail the tool call
        return None


def hook_target(raw):
    """(file_path as given, resolved path) when a file-tool payload names an
    existing artifact, else None. Never raises."""
    step = read_hook_payload(raw)
    return (step[2], step[3]) if step and step[0] == "touch" else None
