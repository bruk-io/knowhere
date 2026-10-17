#!/usr/bin/env python3
"""hooktool - scaffold and validate Claude Code hooks.

A deterministic helper for the authoring-hooks skill. It generates valid hook
configuration and checks existing hook JSON, so the model spends its judgement on
*which* event and *what* to enforce, and leaves structure to code.

Subcommands:
  events     List every hook event (blocking behaviour, matcher field and closed values, context channels).
  fields     List every handler field (types that take it, required, type, default, effect).
  scaffold   Emit a valid hooks config block for settings.json.
  validate   Check a hooks config (file or stdin) for structural problems.
  claudemd   Print concise, model-facing docs for injection into a SKILL.md / CLAUDE.md.

Stdout carries data (JSON where applicable); diagnostics go to stderr.

Exit codes:
  0  success (for validate: no errors; warnings do not change the exit code)
  1  validate found errors (including input that is not valid JSON)
  2  usage error (bad or missing arguments) or unreadable input file
"""

from __future__ import annotations
import argparse
import json
import os
import re
import shlex
import sys
from typing import NamedTuple

DOCS_URL = "https://code.claude.com/docs/en/hooks"
# The event table and handler schema below were checked against this version's
# docs and binary. tests/test_hooktool.py pins the event list, so adding or
# removing an event is a deliberate edit there too.
VERIFIED_VERSION = "2.1.296"
VERIFIED_DATE = "2026-10-09"

# Which handler types an event runs. A handler of any other type is skipped.
_ALL = ("command", "http", "mcp_tool", "prompt", "agent")
_NO_AGENT = ("command", "http", "mcp_tool", "prompt")
_NO_LLM = ("command", "http", "mcp_tool")


def _ev(blocks, matcher, note, inject=False, context=False, types=_NO_LLM, values=None):
    return {"blocks": blocks, "matcher": matcher, "inject": inject, "context": context,
            "types": list(types), "values": values, "note": note}


# Every hook event Claude Code defines, in lifecycle order.
#   blocks:  does `exit 2` stop the action?
#   matcher: the field the matcher filters, or None if the event takes no matcher.
#   inject:  is plain stdout (exit 0) added to Claude's context?
#   context: does stdout JSON hookSpecificOutput.additionalContext reach Claude?
#   types:   handler types the event runs.
#   values:  the closed set of matcher values, where the docs give one.
#   note:    what exit 2 does.
EVENTS = {
    "SessionStart": _ev(False, "source", "cannot block; stderr goes to the user only.",
                        inject=True, context=True, types=("command", "mcp_tool"),
                        values=["startup", "resume", "clear", "compact", "fork"]),
    "Setup": _ev(False, "trigger", "exit code and stderr are ignored. Fires on --init-only, or --init/--maintenance with -p.",
                 types=("command",), values=["init", "maintenance"]),
    "UserPromptSubmit": _ev(True, None, "blocks the prompt; it never reaches Claude.",
                            inject=True, context=True, types=_ALL),
    "UserPromptExpansion": _ev(True, "command name", "blocks the /command expansion.",
                               inject=True, context=True, types=_ALL),
    "PreToolUse": _ev(True, "tool name", "blocks the tool call; stderr goes to Claude as the tool error.",
                      context=True, types=_ALL),
    "PermissionRequest": _ev(False, "tool name", "exit 2 is not honoured; deny with hookSpecificOutput.decision.behavior.",
                             types=_NO_AGENT),
    "PermissionDenied": _ev(False, "tool name", "exit code and stderr are ignored; hookSpecificOutput.retry lets the model retry.",
                            types=_ALL),
    "PostToolUse": _ev(False, "tool name", "cannot block (the tool already ran); stderr is shown to Claude.",
                       context=True, types=_ALL),
    "PostToolUseFailure": _ev(False, "tool name", "cannot block (the tool already failed); stderr is shown to Claude.",
                              context=True, types=_ALL),
    "PostToolBatch": _ev(True, None, "stops the agentic loop before the next model call.",
                         context=True, types=_ALL),
    "Notification": _ev(False, "notification type", "exit code and stderr are ignored."),
    "MessageDisplay": _ev(False, None, "cannot block; the original text is displayed."),
    "SubagentStart": _ev(False, "agent type", "cannot block; stderr goes to the subagent transcript only.",
                         context=True),
    "SubagentStop": _ev(True, "agent type", "prevents the subagent from stopping; stderr is its next instruction.",
                        context=True, types=_ALL),
    "TaskCreated": _ev(True, None, "rolls back the task creation.", types=_ALL),
    "TaskCompleted": _ev(True, None, "prevents the task from being marked completed.", types=_ALL),
    "Stop": _ev(True, None, "prevents Claude from stopping; stderr tells it what is left to do.",
                context=True, types=_ALL),
    "StopFailure": _ev(False, "error type", "output and exit code are ignored."),
    "TeammateIdle": _ev(True, None, "prevents the teammate from going idle.", types=_ALL),
    "InstructionsLoaded": _ev(False, "load reason", "exit code is ignored.",
                              values=["session_start", "nested_traversal", "path_glob_match", "include", "compact"]),
    "ConfigChange": _ev(True, "config source", "blocks the configuration change (except policy_settings).",
                        values=["user_settings", "project_settings", "local_settings", "policy_settings", "skills"]),
    "CwdChanged": _ev(False, None, "cannot block; stderr goes to the user only."),
    "DirectoryAdded": _ev(False, "how added", "cannot block; stderr goes to the debug log.",
                          values=["slash_command", "register_repo_root"]),
    "FileChanged": _ev(False, "filenames", "cannot block. The matcher is a |-separated list of literal filenames to watch."),
    "WorktreeCreate": _ev(True, None, "any non-zero exit fails worktree creation; stdout is the worktree path."),
    "WorktreeRemove": _ev(True, None, "any non-zero exit fails the removal if the directory still exists."),
    "PreCompact": _ev(True, "trigger", "blocks compaction.", values=["manual", "auto"]),
    "PostCompact": _ev(False, "trigger", "cannot block; stderr goes to the user only.", values=["manual", "auto"]),
    "PreModelSwitch": _ev(True, "model name", "blocks the model switch; stderr goes to the user."),
    "PostModelSwitch": _ev(False, "model name", "cannot block (the model already switched).",
                           inject=True, context=True),
    "Elicitation": _ev(True, "MCP server", "declines the MCP elicitation; no dialog appears."),
    "ElicitationResult": _ev(True, "MCP server", "blocks the response (the action becomes decline)."),
    "SessionEnd": _ev(False, "reason", "cannot block; stderr goes to the user only.",
                      values=["clear", "resume", "logout", "prompt_input_exit", "other"]),
}

# Events whose matcher is a tool name; the only events where a handler's `if` is evaluated.
TOOL_EVENTS = ("PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest", "PermissionDenied")
# Events where a hook can decide something, by exit 2 or by a JSON decision.
DECISION_EVENTS = tuple(e for e, m in EVENTS.items() if m["blocks"]) + ("PermissionRequest",)
# onFailure: "block" has no effect on these (exit 2 there means "keep working").
ON_FAILURE_INERT = ("Stop", "SubagentStop", "TaskCompleted", "TeammateIdle")
# Tool names that older configs match but the current tool list does not contain.
LEGACY_TOOLS = {"MultiEdit": "Edit"}

HANDLER_TYPES = set(_ALL)


class HandlerField(NamedTuple):
    """One handler field. `types` are the handler types that take it; `required` is the
    subset that must set it. `type` is a short label; "bool" and "string" also drive
    the validator's type checks."""
    name: str
    types: tuple
    required: tuple
    type: str
    default: str
    effect: str
    since: str = ""


# Rows are built positionally, hence a NamedTuple rather than a dataclass.
# The single source of truth for handler fields: `fields` prints it and `validate`
# derives its field sets from it. Fields taken by all five types come first.
FIELDS = (
    HandlerField("type", _ALL, (), "string", "-", "Selects the handler type. Required on every handler."),
    HandlerField("if", _ALL, (), "rule", "-",
                 "One permission rule that filters the handler by tool and arguments; tool events only."),
    HandlerField("timeout", _ALL, (), "number", "600; prompt 30; agent 60",
                 "Seconds. A timed-out hook renders no decision and does not block."),
    HandlerField("statusMessage", _ALL, (), "string", "-", "Text shown while the hook runs."),
    HandlerField("once", _ALL, (), "bool", "false",
                 "Removes the hook after its first successful run; honoured only in skill frontmatter."),
    HandlerField("command", ("command",), ("command",), "string", "-",
                 "The command line (shell form), or with args the one executable to spawn."),
    HandlerField("args", ("command",), (), "string[]", "-",
                 "Switches to exec form: command is spawned directly with these arguments, no shell."),
    HandlerField("shell", ("command",), (), "bash|powershell", "bash", "Shell for shell form; ignored in exec form."),
    HandlerField("async", ("command",), (), "bool", "false",
                 "Runs in the background; cannot block, and timeout is not enforced."),
    HandlerField("asyncRewake", ("command",), (), "bool", "false",
                 "Runs in the background and wakes Claude when the hook exits 2."),
    HandlerField("onFailure", ("command", "http"), (), "continue|block", "continue",
                 "block: a hook that fails to start, exits other than 0 or 2, times out or prints invalid JSON acts as exit 2.",
                 since="2.1.295"),
    HandlerField("url", ("http",), ("http",), "string", "-", "Endpoint that receives the payload as a POST."),
    HandlerField("headers", ("http",), (), "map<string>", "-",
                 "Request headers; $VAR references need the name in allowedEnvVars."),
    HandlerField("allowedEnvVars", ("http",), (), "string[]", "-",
                 "Environment variables that headers may interpolate; others become empty strings."),
    HandlerField("server", ("mcp_tool",), ("mcp_tool",), "string", "-", "Name of the MCP server."),
    HandlerField("tool", ("mcp_tool",), ("mcp_tool",), "string", "-", "Name of the MCP tool to call."),
    HandlerField("input", ("mcp_tool",), (), "object", "-",
                 "Tool arguments; strings take ${tool_input.file_path}-style substitution."),
    HandlerField("prompt", ("prompt", "agent"), ("prompt", "agent"), "string", "-",
                 "Prompt text; $ARGUMENTS is the event payload."),
    HandlerField("model", ("prompt", "agent"), (), "string", "-", "Model that judges."),
    HandlerField("continueOnBlock", ("prompt",), (), "bool", "false",
                 "On the events that honour it, true feeds an ok:false reason back to Claude and continues "
                 "instead of ending the turn."),
)

COMMON_FIELDS = {f.name for f in FIELDS if f.types == _ALL}
HANDLER_FIELDS = {t: {f.name for f in FIELDS if t in f.types and f.types != _ALL} for t in HANDLER_TYPES}
HANDLER_REQUIRED = {t: tuple(f.name for f in FIELDS if t in f.required) for t in HANDLER_TYPES}
BOOL_FIELDS = tuple(f.name for f in FIELDS if f.type == "bool")
# Optional free-text fields; the required string fields have their own message.
STRING_FIELDS = tuple(f.name for f in FIELDS
                      if f.type == "string" and not f.required and f.name != "type")
SHELLS = ("bash", "powershell")
ON_FAILURE = ("continue", "block")

EXIT_OK, EXIT_INVALID, EXIT_USAGE = 0, 1, 2

# Plugin path variables that expand to an install path (which may contain spaces).
_PLUGIN_VAR = re.compile(r"\$(?:\{(CLAUDE_PLUGIN_(?:ROOT|DATA))\}|(CLAUDE_PLUGIN_(?:ROOT|DATA))\b)")
# A matcher made only of these characters is compared as exact strings, not as a regex.
_EXACT = re.compile(r"^[A-Za-z0-9_\- ,|]*$")
_EXACT_NARROW = re.compile(r"^[A-Za-z0-9_|]*$")  # FileChanged and StopFailure
# One permission rule: Tool or Tool(pattern).
_IF_RULE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.:-]*)(\(.*\))?$", re.S)
_IF_COMBINED = re.compile(r"\)\s*(\|\||\||&&|,)\s*[A-Za-z_][A-Za-z0-9_.:-]*\(")
_HEADER_VAR = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
# A script path written relative to wherever the session happens to be.
_RELATIVE_SCRIPT = re.compile(r"^(?:\./|\.claude/)")
# Commands whose first argument is the script they run.
_INTERPRETERS = ("sh", "bash", "zsh", "python", "python3", "node", "bun", "deno", "ruby", "perl", "pwsh")


def _eprint(*args):
    print(*args, file=sys.stderr)


# ---- events ---------------------------------------------------------------

def matcher_value_lines(events):
    """One line per event whose matcher takes a closed set of values."""
    return [f"  {name:<20} {meta['matcher']}: {', '.join(meta['values'])}"
            for name, meta in events.items() if meta["values"]]


def _types_label(field):
    """The handler types that take `field`, with `*` on those that require it."""
    if field.types == _ALL:
        return "all"
    return ",".join(t + ("*" if t in field.required else "") for t in field.types)


def field_rows(htype=None):
    """The FIELDS table as plain dicts, limited to one handler type when given."""
    return [{"field": f.name, "types": list(f.types), "required": list(f.required), "type": f.type,
             "default": f.default, "effect": f.effect, "since": f.since or None}
            for f in FIELDS if htype is None or htype in f.types]


def field_lines(htype=None):
    """Human output for `fields`: a header and one line per field."""
    rows = [f for f in FIELDS if htype is None or htype in f.types]
    width = max(len(_types_label(f)) for f in rows)
    lines = [f"  {'FIELD':<16} {'TYPES':<{width}} {'TYPE':<16} {'DEFAULT':<25} EFFECT"]
    for f in rows:
        since = f" (v{f.since}+)" if f.since else ""
        lines.append(f"  {f.name:<16} {_types_label(f):<{width}} {f.type:<16} {f.default:<25} {f.effect}{since}")
    return lines


def cmd_fields(args):
    if args.json:
        print(json.dumps(field_rows(args.type), indent=2))
        return 0
    scope = f"{args.type} handler" if args.type else "handler"
    print(f"Hook {scope} fields (as of v{VERIFIED_VERSION}; * = required for that type):\n")
    for line in field_lines(args.type):
        print(line)
    return 0


def cmd_events(args):
    if args.json:
        print(json.dumps([{"event": e, **meta} for e, meta in EVENTS.items()], indent=2))
        return 0

    def yn(b):
        return "yes" if b else "no"

    print(f"Claude Code hook events - all {len(EVENTS)}, as of v{VERIFIED_VERSION}:\n")
    print(f"  {'EVENT':<20} {'EXIT2-BLOCKS':<13} {'MATCHER':<18} {'STDOUT->CTX':<12} ADDL-CONTEXT")
    print(f"  {'-' * 20} {'-' * 13} {'-' * 18} {'-' * 12} {'-' * 12}")
    for e, m in EVENTS.items():
        print(f"  {e:<20} {yn(m['blocks']):<13} {str(m['matcher'] or '-'):<18} "
              f"{yn(m['inject']):<12} {yn(m['context'])}")
    print("\nClosed matcher values (any other value never matches):")
    for line in matcher_value_lines(EVENTS):
        print(line)
    print("\nEXIT2-BLOCKS: exit 2 stops the action. MATCHER: the field a matcher filters ('-' = takes none).\n"
          "STDOUT->CTX: plain stdout on exit 0 is added to Claude's context. ADDL-CONTEXT: stdout JSON\n"
          "hookSpecificOutput.additionalContext reaches Claude. `events --json` adds each event's handler\n"
          "types, closed matcher values, and what exit 2 does. Tool events match tool names (open set).")
    print(f"Schemas: {DOCS_URL}")
    return 0


# ---- scaffold -------------------------------------------------------------

def cmd_scaffold(args):
    event = args.event
    err = args.parser.error
    if event not in EVENTS:
        _eprint(f"warning: '{event}' is not a hook event as of v{VERIFIED_VERSION}; verify it against {DOCS_URL}")
        meta = None
    else:
        meta = EVENTS[event]
        if args.type not in meta["types"]:
            err(f"{event} does not run '{args.type}' handlers (it runs: {', '.join(meta['types'])})")

    handler = {"type": args.type}
    if args.if_:
        if meta is not None and event not in TOOL_EVENTS:
            err(f"--if is only evaluated on tool events ({', '.join(TOOL_EVENTS)}); on {event} the hook would never run")
        handler["if"] = args.if_
    needs = {"command": [("command", args.command)], "http": [("url", args.url)],
             "mcp_tool": [("server", args.server), ("tool", args.tool)],
             "prompt": [("prompt", args.prompt)], "agent": [("prompt", args.prompt)]}[args.type]
    for field, value in needs:
        if not value:
            err(f"--{field} is required for --type {args.type}")
        handler[field] = value
    if args.arg:
        if args.type != "command":
            err("--arg only applies to --type command")
        handler["args"] = list(args.arg)
    if args.type == "command":
        script = relative_script(args.command, args.arg or ())
        if script:
            _eprint(f"warning: {relative_script_warning(script)}")

    if args.timeout is not None:
        if args.timeout <= 0:
            err("--timeout must be a positive number of seconds")
        handler["timeout"] = args.timeout
    if args.async_:
        if args.type != "command":
            err("--async only applies to --type command")
        handler["async"] = True
        if event in DECISION_EVENTS:
            _eprint(f"note: an async handler cannot block; on {event} use --async only for side effects, never for a gate.")
    if args.on_failure:
        if args.type not in ("command", "http"):
            err("--on-failure only applies to --type command or http")
        handler["onFailure"] = args.on_failure

    group = {}
    if args.matcher:
        if meta is not None and meta["matcher"] is None:
            _eprint(f"note: {event} takes no matcher; dropping --matcher '{args.matcher}'.")
        else:
            group["matcher"] = args.matcher
    elif meta is not None and meta["matcher"] is not None:
        _eprint(f"note: no --matcher given; this hook will match all {meta['matcher']} values.")

    group["hooks"] = [handler]
    print(json.dumps({"hooks": {event: [group]}}, indent=2))
    return 0


# ---- validate -------------------------------------------------------------

def is_plugin_hooks_path(path):
    """True when `path` names a plugin's hooks file (.../hooks/hooks.json)."""
    if not path or path == "-":
        return False
    parts = [p for p in re.split(r"[\\/]+", path) if p not in ("", ".")]
    return parts[-2:] == ["hooks", "hooks.json"]


def unquoted_plugin_vars(command):
    """Names of CLAUDE_PLUGIN_ROOT / CLAUDE_PLUGIN_DATA references in a shell
    command string that are not inside double quotes."""
    found = []
    in_single = in_double = False
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if c == "\\" and not in_single:
            i += 2
            continue
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == "$" and not in_double:
            m = _PLUGIN_VAR.match(command, i)
            if m:
                name = m.group(1) or m.group(2)
                if name not in found:
                    found.append(name)
                i = m.end()
                continue
        i += 1
    return found


def relative_script(command, args=()):
    """The script a command handler names by a relative path starting `./` or
    `.claude/` - as the command itself or as an interpreter's first argument -
    or None. `args` is the exec-form argument list."""
    if args:
        words = [command.strip(), *args]
    else:
        try:
            words = shlex.split(command)
        except ValueError:               # unbalanced quotes: the shell will not run it either
            words = command.split()
    if not words:
        return None
    candidates = words[:2] if words[0] in _INTERPRETERS else words[:1]
    return next((w for w in candidates if _RELATIVE_SCRIPT.match(w)), None)


def relative_script_warning(script):
    """Why a relative script path is a problem, and what to write instead."""
    return (f"'command' runs {script!r} by a relative path; a hook runs in the session's current directory, which "
            "moves as Claude works, so the script is found only from the directory it is relative to - write "
            "\"${CLAUDE_PROJECT_DIR}/...\" (in a plugin, \"${CLAUDE_PLUGIN_ROOT}/...\").")


def matcher_tokens(event, matcher):
    """The exact strings a matcher compares against, or None when the matcher
    matches everything or is evaluated as a regular expression."""
    if matcher in ("", "*"):
        return None
    exact = _EXACT_NARROW if event in ("FileChanged", "StopFailure") else _EXACT
    if not exact.match(matcher):
        return None
    return [t.strip() for t in re.split(r"[|,]", matcher) if t.strip()]


def _check_matcher(event, meta, matcher, loc, warnings):
    if meta is not None and meta["matcher"] is None:
        warnings.append(f"{loc}: {event} takes no matcher; 'matcher' will be ignored.")
        return
    if matcher in ("", "*") or event == "FileChanged":
        return
    tokens = matcher_tokens(event, matcher)
    if tokens is None:  # regex path (JavaScript, unanchored); Python's re is a close-enough syntax check
        try:
            re.compile(matcher)
        except re.error as ex:
            warnings.append(f"{loc}: 'matcher' {matcher!r} is not a valid regex ({ex}).")
        return
    if event in TOOL_EVENTS:
        for t in tokens:
            if t.startswith("mcp__") and t.count("__") < 2:
                warnings.append(f"{loc}: matcher value {t!r} is compared as an exact string and matches no tool; "
                                f"write '{t}__.*' to match every tool from that server.")
            elif t in LEGACY_TOOLS:
                warnings.append(f"{loc}: matcher value {t!r} is not a tool in current Claude Code "
                                f"(v{VERIFIED_VERSION}); '{LEGACY_TOOLS[t]}' covers it.")
    elif meta is not None and meta["values"]:
        for t in tokens:
            if t not in meta["values"]:
                warnings.append(f"{loc}: matcher value {t!r} never matches; {event} matches on "
                                f"{meta['matcher']}: {', '.join(meta['values'])}.")


def _check_handler(event, meta, group, h, hloc, plugin, errors, warnings):
    htype = h.get("type")
    if htype not in HANDLER_TYPES:
        errors.append(f"{hloc}: 'type' must be one of {sorted(HANDLER_TYPES)} (got {htype!r}).")
        return
    if meta is not None and htype not in meta["types"]:
        errors.append(f"{hloc}: {event} does not run '{htype}' handlers (it runs: {', '.join(meta['types'])}); "
                      "this hook would be skipped.")
    for req in HANDLER_REQUIRED[htype]:
        value = h.get(req)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{hloc}: '{htype}' handler requires '{req}' (a non-empty string).")
    for key in h:
        if key not in COMMON_FIELDS and key not in HANDLER_FIELDS[htype]:
            owners = sorted(t for t, fields in HANDLER_FIELDS.items() if key in fields)
            hint = f"it belongs to {'/'.join(owners)} handlers" if owners else "not a documented field"
            warnings.append(f"{hloc}: '{key}' has no effect on a '{htype}' handler ({hint}).")

    if "timeout" in h:
        t = h["timeout"]
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not t > 0:
            errors.append(f"{hloc}: 'timeout' must be a positive number of seconds (got {t!r}).")
    for key in BOOL_FIELDS:
        if key in h and not isinstance(h[key], bool):
            errors.append(f"{hloc}: '{key}' must be true or false (got {h[key]!r}).")
    for key in STRING_FIELDS:
        if key in h and not isinstance(h[key], str):
            errors.append(f"{hloc}: '{key}' must be a string.")

    if "if" in h:
        rule = h["if"]
        if not isinstance(rule, str) or not rule.strip():
            errors.append(f"{hloc}: 'if' must be a non-empty string holding one permission rule, e.g. \"Bash(git *)\".")
        elif meta is not None and event not in TOOL_EVENTS:
            errors.append(f"{hloc}: 'if' is only evaluated on tool events ({', '.join(TOOL_EVENTS)}); "
                          f"on {event} a hook with 'if' never runs.")
        else:
            m = _IF_RULE.match(rule.strip())
            if not m or _IF_COMBINED.search(rule):
                warnings.append(f"{hloc}: 'if' {rule!r} is not a single permission rule like \"Edit(*.ts)\"; there is "
                                "no list or ||/&& syntax - use one handler per rule.")
            elif isinstance(group.get("matcher"), str):
                tokens = matcher_tokens(event, group["matcher"])
                if tokens is not None and m.group(1) not in tokens:
                    warnings.append(f"{hloc}: 'if' names tool {m.group(1)!r} but the group's matcher "
                                    f"{group['matcher']!r} never passes that tool; this hook never runs.")
    if h.get("once") is True:
        warnings.append(f"{hloc}: 'once' is only honoured for hooks in skill frontmatter; "
                        "it is ignored in settings files, plugin hooks files and agent frontmatter.")

    background = h.get("async") is True or h.get("asyncRewake") is True
    if background and htype == "command" and event in DECISION_EVENTS:
        which = "async" if h.get("async") is True else "asyncRewake"
        warnings.append(f"{hloc}: async handler cannot block ('{which}' runs it in the background); {event} "
                        "is an event a hook can gate - if this is a gate, remove it.")
    if "onFailure" in h:
        if h["onFailure"] not in ON_FAILURE:
            errors.append(f"{hloc}: 'onFailure' must be \"continue\" or \"block\" (got {h['onFailure']!r}).")
        elif h["onFailure"] == "block" and htype in ("command", "http"):
            if event in ON_FAILURE_INERT:
                warnings.append(f"{hloc}: 'onFailure' has no effect on {event} hooks.")
            elif background:
                warnings.append(f"{hloc}: 'onFailure' has no effect on a background (async) hook.")

    if htype == "command":
        _check_command(h, hloc, plugin, errors, warnings)
    elif htype == "http":
        _check_http(h, hloc, errors, warnings)
    elif htype == "mcp_tool" and "input" in h and not isinstance(h["input"], dict):
        errors.append(f"{hloc}: 'input' must be an object of tool arguments.")


def _check_command(h, hloc, plugin, errors, warnings):
    command = h.get("command")
    exec_form = "args" in h
    if exec_form:
        args = h["args"]
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            errors.append(f"{hloc}: 'args' must be an array of strings.")
        elif isinstance(command, str) and re.search(r"\s", command.strip()) and not re.search(r"[\\/]", command):
            warnings.append(f"{hloc}: with 'args', 'command' is one executable and no shell runs; "
                            f"{command!r} will not be found - move the extra words into 'args'.")
    if "shell" in h:
        if h["shell"] not in SHELLS:
            errors.append(f"{hloc}: 'shell' must be \"bash\" or \"powershell\" (got {h['shell']!r}).")
        elif exec_form:
            warnings.append(f"{hloc}: 'shell' is ignored when 'args' is set (exec form runs no shell).")
    if not isinstance(command, str):
        return
    args = h["args"] if exec_form and isinstance(h["args"], list) and all(isinstance(a, str) for a in h["args"]) else ()
    script = relative_script(command, args)
    if script:
        warnings.append(f"{hloc}: {relative_script_warning(script)}")
    if exec_form:
        return
    if h.get("shell") != "powershell":
        for name in unquoted_plugin_vars(command):
            warnings.append(f"{hloc}: ${{{name}}} is not inside double quotes; the command breaks when "
                            f"the install path contains spaces - write \"${{{name}}}/...\", or use 'args'.")
    if plugin and "${user_config." in command:
        errors.append(f"{hloc}: a shell-form plugin hook that references ${{user_config.*}} fails instead of running; "
                      "use 'args' (exec form) or read $CLAUDE_PLUGIN_OPTION_<KEY>.")


def _check_http(h, hloc, errors, warnings):
    allowed = h.get("allowedEnvVars", [])
    if not isinstance(allowed, list) or not all(isinstance(a, str) for a in allowed):
        errors.append(f"{hloc}: 'allowedEnvVars' must be an array of variable names.")
        allowed = []
    headers = h.get("headers", {})
    if not isinstance(headers, dict) or not all(isinstance(v, str) for v in headers.values()):
        errors.append(f"{hloc}: 'headers' must be an object of string values.")
        return
    missing = []
    for value in headers.values():
        for m in _HEADER_VAR.finditer(value):
            name = m.group(1) or m.group(2)
            if name not in allowed and name not in missing:
                missing.append(name)
    for name in missing:
        warnings.append(f"{hloc}: header references ${name} but it is not in 'allowedEnvVars'; "
                        "it is replaced with an empty string.")


def validate_config(data, plugin=False):
    """Check a parsed hooks config. Returns (errors, warnings) as lists of str.

    plugin=True applies the rules for a plugin's hooks/hooks.json: the outer
    {"hooks": {...}} wrapper is required and a top-level 'description' is allowed.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return ["top level must be a JSON object."], warnings

    # Accept either a full settings object ({"hooks": {...}}) or a bare hooks map.
    if isinstance(data.get("hooks"), dict):
        hooks = data["hooks"]
    elif "hooks" in data:
        return ["top-level 'hooks' must be an object mapping event names to arrays of groups."], warnings
    else:
        hooks = data
        if plugin:
            errors.append("plugin hooks config requires the outer {\"hooks\": {...}} wrapper; "
                          "without it the hooks silently fail to register.")
            hooks = {k: v for k, v in data.items() if k != "description"}
        else:
            warnings.append("no top-level 'hooks' key; assuming this object is the hooks map itself.")

    if not hooks:
        warnings.append("no events defined.")

    for event, groups in hooks.items():
        meta = EVENTS.get(event)
        if meta is None:
            warnings.append(f"'{event}': not a hook event as of Claude Code v{VERIFIED_VERSION} "
                            "(a typo, or newer than this tool - verify against the docs).")
        if not isinstance(groups, list):
            errors.append(f"'{event}': value must be an array of hook groups.")
            continue
        for i, group in enumerate(groups):
            loc = f"{event}[{i}]"
            if not isinstance(group, dict):
                errors.append(f"{loc}: each group must be an object.")
                continue
            if "matcher" in group:
                matcher = group["matcher"]
                if not isinstance(matcher, str):
                    errors.append(f"{loc}: 'matcher' must be a string (got {type(matcher).__name__}).")
                else:
                    _check_matcher(event, meta, matcher, loc, warnings)
            handlers = group.get("hooks")
            if not isinstance(handlers, list) or not handlers:
                errors.append(f"{loc}: missing non-empty 'hooks' array.")
                continue
            for j, h in enumerate(handlers):
                hloc = f"{loc}.hooks[{j}]"
                if not isinstance(h, dict):
                    errors.append(f"{hloc}: handler must be an object.")
                    continue
                _check_handler(event, meta, group, h, hloc, plugin, errors, warnings)

    return errors, warnings


def cmd_validate(args):
    try:
        raw = _read_input(args.path)
    except (OSError, UnicodeDecodeError) as ex:
        _eprint(f"hooktool: error: cannot read {args.path}: {ex}")
        return EXIT_USAGE

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as ex:
        return _report(False, [f"invalid JSON: {ex}"], [], args.json)

    plugin = args.plugin or is_plugin_hooks_path(args.path)
    errors, warnings = validate_config(data, plugin=plugin)
    return _report(len(errors) == 0, errors, warnings, args.json)


def _read_input(path):
    if path and path != "-":
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def _report(valid, errors, warnings, as_json):
    if as_json:
        print(json.dumps({"valid": valid, "errors": errors, "warnings": warnings}, indent=2))
    else:
        for w in warnings:
            _eprint(f"  warning: {w}")
        if errors:
            for e in errors:
                _eprint(f"  error:   {e}")
            _eprint(f"\nx invalid: {len(errors)} error(s), {len(warnings)} warning(s).")
        else:
            print(f"ok valid ({len(warnings)} warning(s)).")
    return EXIT_OK if valid else EXIT_INVALID


# ---- claudemd -------------------------------------------------------------

def claudemd_text(script_path):
    """The model-facing docs, with every command written as a runnable invocation of `script_path`."""
    run = f'python3 "{script_path}"'
    return f"""\
`hooktool` - scaffold and validate Claude Code hooks (bundled with this skill; event table verified against v{VERIFIED_VERSION}). It is not on PATH; run it as shown.

- `{run} events [--json]` - every hook event: whether exit 2 blocks, what the matcher filters, whether plain stdout or `additionalContext` reaches Claude, and the closed matcher values. `--json` adds handler types and the exit-2 effect per event.
- `{run} fields [TYPE] [--json]` - every handler field: which handler types take it, required or optional, type, default, effect.
- `{run} scaffold --event E [--matcher M] [--if RULE] [--type T] [--command C [--arg A]... | --url U | --server S --tool T | --prompt P] [--async] [--on-failure block] [--timeout N]` - emit a valid hooks config block (JSON on stdout) to paste into settings.json.
- `{run} validate [FILE] [--plugin] [--json]` - check a hooks config (file, or stdin when FILE is `-` or omitted). `--plugin` applies plugin rules (the outer `hooks` wrapper becomes required); it is automatic when FILE ends in `hooks/hooks.json`. `--json` prints `{{"valid", "errors", "warnings"}}`.
- `{run} claudemd` - print this.

Exit codes: 0 valid (warnings allowed), 1 validation errors, 2 usage error or unreadable file. Errors include a hook that can never run: a handler type the event does not run, or `if` outside a tool event. Warnings are worth reading: async on a gate, an unquoted plugin-root variable, a script named by a relative path, a matcher value that never matches, a field with no effect.

stdin carries the event JSON; exit 2 blocks on blocking events with stderr as the reason; stdout JSON gives structured control. Full schema: {DOCS_URL}
"""


def cmd_claudemd(args):
    print(claudemd_text(os.path.abspath(__file__)), end="")
    return 0


# ---- cli ------------------------------------------------------------------

EPILOG = """\
exit codes:
  0  success (validate: no errors; warnings do not change the exit code)
  1  validate found errors (including input that is not valid JSON)
  2  usage error (bad or missing arguments) or unreadable input file

Data goes to stdout (JSON for scaffold, and for events/fields/validate with --json);
notes, warnings and errors go to stderr.

examples:
  hooktool events
  hooktool fields command
  hooktool scaffold --event PostToolUse --matcher "Edit|Write" --command '"${CLAUDE_PROJECT_DIR}/.claude/hooks/format.sh"'
  hooktool scaffold --event PreToolUse --matcher Bash --if "Bash(git push *)" --command '"${CLAUDE_PROJECT_DIR}/check-push.sh"'
  hooktool validate .claude/settings.json
  hooktool validate hooks/hooks.json            # plugin rules applied automatically
  hooktool scaffold --event Stop --command '"${CLAUDE_PROJECT_DIR}/check.sh"' | hooktool validate - --json
"""


def build_parser():
    raw = argparse.RawDescriptionHelpFormatter
    p = argparse.ArgumentParser(prog="hooktool", description="Scaffold and validate Claude Code hooks.",
                                epilog=EPILOG, formatter_class=raw)
    sub = p.add_subparsers(dest="cmd", required=True, metavar="{events,fields,scaffold,validate,claudemd}")

    pe = sub.add_parser("events", help="list every hook event",
                        description=f"List every hook event (as of Claude Code v{VERIFIED_VERSION}): whether exit 2 "
                                    "blocks, what the matcher filters, and whether plain stdout or "
                                    "additionalContext reaches Claude.")
    pe.add_argument("--json", action="store_true",
                    help="emit a JSON array of {event, blocks, matcher, inject, context, types, values, note}")
    pe.set_defaults(func=cmd_events)

    pf = sub.add_parser("fields", help="list every handler field",
                        description="List every handler field: which handler types take it (* = required), its "
                                    "type, default and effect. Limit the table to one handler type with TYPE.")
    pf.add_argument("type", nargs="?", choices=sorted(HANDLER_TYPES), metavar="TYPE",
                    help="show only the fields this handler type takes: " + ", ".join(sorted(HANDLER_TYPES)))
    pf.add_argument("--json", action="store_true",
                    help="emit a JSON array of {field, types, required, type, default, effect, since}")
    pf.set_defaults(func=cmd_fields)

    ps = sub.add_parser("scaffold", help="emit a valid hooks config block",
                        description="Emit a {\"hooks\": {EVENT: [...]}} block as JSON on stdout. Notes go to stderr. "
                                    "Exits 2 when a required option for the handler type is missing, or when the "
                                    "event does not run that handler type.")
    ps.add_argument("--event", required=True, help="hook event, e.g. PreToolUse (see 'hooktool events')")
    ps.add_argument("--matcher", help="matcher, e.g. 'Edit|Write'; dropped for events that take none")
    ps.add_argument("--if", dest="if_", metavar="RULE",
                    help="one permission rule that narrows a tool-event hook, e.g. 'Edit(*.ts)' or 'Bash(git *)'")
    ps.add_argument("--type", default="command", choices=sorted(HANDLER_TYPES),
                    help="handler type (default: command)")
    ps.add_argument("--command", help="shell command, or with --arg the executable (required for --type command)")
    ps.add_argument("--arg", action="append", metavar="A",
                    help="exec-form argument, repeatable (write --arg=--flag for a value starting with -); "
                         "no shell runs, so paths need no quoting")
    ps.add_argument("--url", help="endpoint URL (required for --type http)")
    ps.add_argument("--server", help="MCP server name (required for --type mcp_tool)")
    ps.add_argument("--tool", help="MCP tool name (required for --type mcp_tool)")
    ps.add_argument("--prompt", help="prompt text (required for --type prompt and agent)")
    ps.add_argument("--timeout", type=int, help="handler timeout in seconds (positive integer)")
    ps.add_argument("--async", dest="async_", action="store_true",
                    help="run non-blocking (command handlers, side effects only - an async handler cannot block)")
    ps.add_argument("--on-failure", choices=ON_FAILURE,
                    help="what a failed or timed-out command/http hook does to the action (default: continue)")
    ps.set_defaults(func=cmd_scaffold, parser=ps)

    pv = sub.add_parser("validate", help="check a hooks config (file or stdin)", formatter_class=raw,
                        description="Check a hooks config for structural problems.\n\n"
                                    "Errors (exit 1): invalid JSON, wrong shapes, unknown handler type, a missing\n"
                                    "required field (command; url; server and tool; prompt), a handler type the\n"
                                    "event does not run, 'if' outside a tool event, wrong field types (timeout,\n"
                                    "args, shell, onFailure, async, once, headers), non-string matcher, and - in\n"
                                    "plugin mode - a missing outer \"hooks\" wrapper or ${user_config.*} in a\n"
                                    "shell-form command.\n"
                                    "Warnings (exit 0): unknown event, matcher on a matcher-less event, matcher\n"
                                    "that is not a valid regex or names a value that never matches, async on a\n"
                                    "handler under an event that can gate, 'once' outside skill frontmatter,\n"
                                    "fields with no effect on the handler type, an 'if' that is not one rule or\n"
                                    "contradicts the matcher, CLAUDE_PLUGIN_ROOT/DATA used outside double quotes,\n"
                                    "a script named by a relative path (./x.sh, .claude/hooks/x.sh).",
                        epilog="exit codes: 0 valid, 1 validation errors, 2 usage error or unreadable file.\n"
                               "Without --json: 'ok valid (N warning(s)).' on stdout, diagnostics on stderr.\n"
                               "With --json: {\"valid\": bool, \"errors\": [str], \"warnings\": [str]} on stdout.")
    pv.add_argument("path", nargs="?", help="path to settings.json or hooks.json ('-' or omitted reads stdin)")
    pv.add_argument("--plugin", action="store_true",
                    help="apply plugin rules: the outer {\"hooks\": {...}} wrapper is required and a top-level "
                         "'description' is allowed (automatic when PATH ends in hooks/hooks.json)")
    pv.add_argument("--json", action="store_true", help="emit the report as JSON on stdout")
    pv.set_defaults(func=cmd_validate)

    pc = sub.add_parser("claudemd", help="print concise model-facing docs",
                        description="Print concise, model-facing usage docs for injection into a SKILL.md or CLAUDE.md.")
    pc.set_defaults(func=cmd_claudemd)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
