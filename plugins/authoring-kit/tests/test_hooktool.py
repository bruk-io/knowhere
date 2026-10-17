"""Unit tests for skills/authoring-hooks/scripts/hooktool.py.

Run from the plugin root:  python3 -m unittest discover -s tests -v
"""

import importlib.util
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKTOOL = os.path.join(ROOT, "skills", "authoring-hooks", "scripts", "hooktool.py")
PLUGIN_HOOKS = os.path.join(ROOT, "hooks", "hooks.json")

_spec = importlib.util.spec_from_file_location("hooktool", HOOKTOOL)
hooktool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hooktool)


def run(*args, stdin=None, cwd=None):
    """Run hooktool as a subprocess; returns (exit code, stdout, stderr)."""
    p = subprocess.run([sys.executable, HOOKTOOL, *args], input=stdin,
                       capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def config(handler, event="PreToolUse", matcher="Bash", wrap=True):
    group = {"hooks": [handler]}
    if matcher is not None:
        group["matcher"] = matcher
    hooks = {event: [group]}
    return {"hooks": hooks} if wrap else hooks


def cmd(command="gate.sh", **extra):
    return {"type": "command", "command": command, **extra}


def any_matcher(event):
    """A matcher value the event accepts, or None when it takes no matcher."""
    meta = hooktool.EVENTS[event]
    if meta["matcher"] is None:
        return None
    return (meta["values"] or ["x"])[0]


def has(messages, fragment):
    return any(fragment in m for m in messages)


class RealPluginConfig(unittest.TestCase):
    def test_plugin_hooks_json_is_valid(self):
        code, out, err = run("validate", PLUGIN_HOOKS, "--json")
        report = json.loads(out)
        self.assertEqual(report["errors"], [], err)
        self.assertTrue(report["valid"])
        self.assertEqual(code, 0)


class AsyncChecks(unittest.TestCase):
    def test_async_on_blocking_event_warns_but_is_valid(self):
        errors, warnings = hooktool.validate_config(config(cmd(**{"async": True})))
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "async handler cannot block"), warnings)

    def test_async_on_every_blocking_event_warns(self):
        for event, meta in hooktool.EVENTS.items():
            if not meta["blocks"]:
                continue
            matcher = any_matcher(event)
            _, warnings = hooktool.validate_config(config(cmd(**{"async": True}), event=event, matcher=matcher))
            self.assertTrue(has(warnings, "async handler cannot block"), event)

    def test_async_on_non_blocking_event_is_quiet(self):
        for event in ("PostToolUse", "SessionEnd", "PostCompact", "Notification"):
            matcher = any_matcher(event)
            errors, warnings = hooktool.validate_config(config(cmd(**{"async": True}), event=event, matcher=matcher))
            self.assertEqual((errors, warnings), ([], []), event)

    def test_async_false_or_absent_is_quiet(self):
        for handler in (cmd(), cmd(**{"async": False})):
            self.assertEqual(hooktool.validate_config(config(handler)), ([], []))

    def test_async_on_non_command_handler_warns(self):
        handler = {"type": "http", "url": "http://localhost/x", "async": True}
        errors, warnings = hooktool.validate_config(config(handler, event="PostToolUse"))
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "'async' has no effect on a 'http' handler"), warnings)

    def test_async_on_permission_request_warns(self):
        # exit 2 does not block there, but a JSON decision does - and an async hook cannot give one
        _, warnings = hooktool.validate_config(config(cmd(**{"async": True}), event="PermissionRequest"))
        self.assertTrue(has(warnings, "async handler cannot block"), warnings)

    def test_async_rewake_on_gate_warns(self):
        _, warnings = hooktool.validate_config(config(cmd(asyncRewake=True)))
        self.assertTrue(has(warnings, "async handler cannot block"), warnings)

    def test_task_example_via_stdin(self):
        raw = '{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"gate.sh","async":true}]}]}}'
        code, out, _ = run("validate", "-", "--json", stdin=raw)
        report = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(report["valid"])
        self.assertEqual(len(report["warnings"]), 1)


class WrapperChecks(unittest.TestCase):
    BARE = config(cmd(), wrap=False)
    WRAPPED = config(cmd())

    def test_bare_map_warns_without_plugin(self):
        errors, warnings = hooktool.validate_config(self.BARE)
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "no top-level 'hooks' key"), warnings)

    def test_bare_map_is_error_with_plugin(self):
        errors, _ = hooktool.validate_config(self.BARE, plugin=True)
        self.assertTrue(has(errors, "wrapper"), errors)

    def test_wrapped_is_clean_in_both_modes(self):
        self.assertEqual(hooktool.validate_config(self.WRAPPED), ([], []))
        self.assertEqual(hooktool.validate_config(self.WRAPPED, plugin=True), ([], []))

    def test_plugin_allows_top_level_description(self):
        data = dict(self.WRAPPED, description="what these hooks do")
        self.assertEqual(hooktool.validate_config(data, plugin=True), ([], []))

    def test_plugin_bare_map_with_description_reports_only_the_wrapper(self):
        data = dict(self.BARE, description="what these hooks do")
        errors, warnings = hooktool.validate_config(data, plugin=True)
        self.assertEqual(len(errors), 1, errors)
        self.assertEqual(warnings, [])

    def test_hooks_key_of_wrong_type_is_error(self):
        errors, _ = hooktool.validate_config({"hooks": []})
        self.assertTrue(has(errors, "'hooks' must be an object"), errors)

    def test_cli_plugin_flag(self):
        raw = json.dumps(self.BARE)
        code, out, _ = run("validate", "-", "--json", stdin=raw)
        self.assertEqual((code, json.loads(out)["valid"]), (0, True))
        code, out, _ = run("validate", "-", "--plugin", "--json", stdin=raw)
        self.assertEqual((code, json.loads(out)["valid"]), (1, False))

    def test_path_auto_detects_plugin_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, "hooks"))
            plugin_path = os.path.join(tmp, "hooks", "hooks.json")
            settings_path = os.path.join(tmp, "settings.json")
            for path in (plugin_path, settings_path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.BARE, f)
            self.assertEqual(run("validate", plugin_path)[0], 1)
            self.assertEqual(run("validate", settings_path)[0], 0)
            # relative spelling is detected too
            self.assertEqual(run("validate", "hooks/hooks.json", cwd=tmp)[0], 1)

    def test_is_plugin_hooks_path(self):
        yes = ["hooks/hooks.json", "./hooks/hooks.json", "/a b/plugin/hooks/hooks.json", "x\\hooks\\hooks.json"]
        no = ["hooks.json", "-", None, "", ".claude/settings.json", "myhooks/hooks.json", "hooks/hooks.json.bak"]
        for p in yes:
            self.assertTrue(hooktool.is_plugin_hooks_path(p), p)
        for p in no:
            self.assertFalse(hooktool.is_plugin_hooks_path(p), p)


class PluginRootQuoting(unittest.TestCase):
    UNQUOTED = [
        "sh ${CLAUDE_PLUGIN_ROOT}/hooks/x.sh",
        "sh $CLAUDE_PLUGIN_ROOT/hooks/x.sh",
        "${CLAUDE_PLUGIN_ROOT}/hooks/x.sh",
        "sh '${CLAUDE_PLUGIN_ROOT}/hooks/x.sh'",
        'echo "start" && sh ${CLAUDE_PLUGIN_ROOT}/x.sh',
    ]
    QUOTED = [
        'sh "${CLAUDE_PLUGIN_ROOT}/hooks/x.sh"',
        'sh "$CLAUDE_PLUGIN_ROOT/hooks/x.sh"',
        '"${CLAUDE_PLUGIN_ROOT}"/hooks/x.sh --flag',
        'echo "it\'s" && sh "${CLAUDE_PLUGIN_ROOT}/x.sh"',
        '"${CLAUDE_PROJECT_DIR}/.claude/hooks/format.sh"',
        "echo $CLAUDE_PLUGIN_ROOTED",
    ]

    def test_unquoted_warns(self):
        for command in self.UNQUOTED:
            errors, warnings = hooktool.validate_config(config(cmd(command), event="PostToolUse"))
            self.assertEqual(errors, [], command)
            self.assertTrue(has(warnings, "not inside double quotes"), command)

    def test_quoted_is_quiet(self):
        for command in self.QUOTED:
            self.assertEqual(hooktool.validate_config(config(cmd(command), event="PostToolUse")), ([], []), command)

    def test_one_warning_per_variable(self):
        command = "sh ${CLAUDE_PLUGIN_ROOT}/a.sh ${CLAUDE_PLUGIN_ROOT}/b ${CLAUDE_PLUGIN_DATA}/c"
        self.assertEqual(hooktool.unquoted_plugin_vars(command), ["CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA"])


class RelativeScriptPath(unittest.TestCase):
    """A hook runs in the session's current directory, so a script named by a relative path is found only there."""
    RELATIVE = [
        ("./check.sh", (), "./check.sh"),
        (".claude/hooks/format.sh --fix", (), ".claude/hooks/format.sh"),
        ("./.claude/hooks/format.sh", (), "./.claude/hooks/format.sh"),
        ("sh ./check.sh", (), "./check.sh"),
        ("python3 .claude/hooks/gate.py", (), ".claude/hooks/gate.py"),
        ('"./my hooks/x.sh" --fix', (), "./my hooks/x.sh"),

        ("node", (".claude/hooks/check.js", "--strict"), ".claude/hooks/check.js"),
        ("./check.sh", ("--strict",), "./check.sh"),
    ]
    ANCHORED = [
        ('"${CLAUDE_PROJECT_DIR}/.claude/hooks/format.sh"', ()),
        ('sh "${CLAUDE_PLUGIN_ROOT}/hooks/x.sh"', ()),
        ("node", ("${CLAUDE_PROJECT_DIR}/.claude/hooks/check.js",)),
        ('cd "$CLAUDE_PROJECT_DIR" && ./run.sh', ()),          # relative to a directory the command chose
        ("npx prettier --write ./src", ()),                     # an argument, not the script
        ("gate.sh", ()),                                        # found on PATH
        ("/usr/local/bin/gate.sh", ()),
        ("", ()),
    ]

    def test_pure_detection(self):
        for command, args, script in self.RELATIVE:
            self.assertEqual(hooktool.relative_script(command, args), script, command)
        self.assertIsNone(hooktool.relative_script("'./unbalanced quote"))       # never raises
        for command, args in self.ANCHORED:
            self.assertIsNone(hooktool.relative_script(command, args), command)

    def test_validate_warns_with_the_reason_and_the_fix(self):
        for command, args, script in self.RELATIVE:
            handler = cmd(command, args=list(args)) if args else cmd(command)
            errors, warnings = hooktool.validate_config(config(handler, event="PostToolUse", matcher="Edit"))
            self.assertEqual(errors, [], command)
            (warning,) = [w for w in warnings if "relative path" in w]
            self.assertIn(repr(script), warning)
            self.assertIn("session's current directory", warning)
            self.assertIn('"${CLAUDE_PROJECT_DIR}/..."', warning)
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}/..."', warning)
        for command, args in self.ANCHORED[:-1]:
            handler = cmd(command, args=list(args)) if args else cmd(command)
            _, warnings = hooktool.validate_config(config(handler, event="PostToolUse", matcher="Edit"))
            self.assertFalse(has(warnings, "relative path"), command)

    def test_scaffold_warns_on_stderr_and_still_emits(self):
        code, out, err = run("scaffold", "--event", "Stop", "--command", "./check.sh")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hooks"]["Stop"][0]["hooks"][0]["command"], "./check.sh")
        self.assertIn("warning: 'command' runs './check.sh' by a relative path", err)
        code, _, err = run("scaffold", "--event", "Stop", "--command", "node", "--arg", ".claude/hooks/x.js")
        self.assertIn("'.claude/hooks/x.js' by a relative path", err)
        code, _, err = run("scaffold", "--event", "Stop", "--command", '"${CLAUDE_PROJECT_DIR}/check.sh"')
        self.assertEqual((code, err), (0, ""))
        self.assertNotIn("--command ./", run("--help")[1])       # the examples follow the advice


class TimeoutAndMatcher(unittest.TestCase):
    def test_bad_timeouts_are_errors(self):
        for bad in (0, -5, "30", True, None, [30]):
            errors, _ = hooktool.validate_config(config(cmd(timeout=bad)))
            self.assertTrue(has(errors, "'timeout' must be a positive number"), repr(bad))

    def test_good_timeouts_pass(self):
        for good in (1, 30, 0.5):
            self.assertEqual(hooktool.validate_config(config(cmd(timeout=good))), ([], []), repr(good))

    def test_non_string_matcher_is_error(self):
        for bad in (["Edit", "Write"], 1, None, {"tool": "Bash"}):
            data = config(cmd())
            data["hooks"]["PreToolUse"][0]["matcher"] = bad
            errors, _ = hooktool.validate_config(data)
            self.assertTrue(has(errors, "'matcher' must be a string"), repr(bad))

    def test_invalid_regex_matcher_warns(self):
        errors, warnings = hooktool.validate_config(config(cmd(), matcher="Edit|(Write"))
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "not a valid regex"), warnings)

    def test_valid_and_match_all_matchers_are_quiet(self):
        for matcher in ("Bash", "Edit|Write", "Edit, Write", "mcp__.*", "mcp__memory__create_entities",
                        "^Notebook", "*", ""):
            self.assertEqual(hooktool.validate_config(config(cmd(), matcher=matcher)), ([], []), matcher)

    def test_matcher_on_matcherless_event_warns(self):
        _, warnings = hooktool.validate_config(config(cmd(), event="Stop", matcher="Bash"))
        self.assertTrue(has(warnings, "takes no matcher"), warnings)


class StructuralChecks(unittest.TestCase):
    def test_structural_errors(self):
        cases = {
            "must be a JSON object": [],
            "array of hook groups": {"hooks": {"PreToolUse": {}}},
            "each group must be an object": {"hooks": {"PreToolUse": ["x"]}},
            "missing non-empty 'hooks' array": {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]}},
            "'type' must be one of": config({"type": "shell", "command": "x"}),
            "requires 'command'": config({"type": "command"}),
            "'command' handler requires 'command'": config({"type": "command", "command": "  "}),
            "requires 'url'": config({"type": "http"}),
            "requires 'server'": config({"type": "mcp_tool", "tool": "t"}),
            "requires 'tool'": config({"type": "mcp_tool", "server": "s"}),
            "'prompt' handler requires 'prompt'": config({"type": "prompt"}),
            "'agent' handler requires 'prompt'": config({"type": "agent"}),
        }
        for fragment, data in cases.items():
            errors, _ = hooktool.validate_config(data)
            self.assertTrue(has(errors, fragment), (fragment, errors))

    def test_unknown_event_warns(self):
        errors, warnings = hooktool.validate_config(config(cmd(), event="FutureEvent"))
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "not a hook event"), warnings)


class Scaffold(unittest.TestCase):
    def assert_round_trips(self, *args):
        code, out, _ = run("scaffold", *args)
        self.assertEqual(code, 0, args)
        data = json.loads(out)
        vcode, vout, _ = run("validate", "-", "--plugin", "--json", stdin=out)
        report = json.loads(vout)
        self.assertEqual((vcode, report["valid"], report["errors"]), (0, True, []), args)
        return data, report

    def test_round_trips_through_validate(self):
        command = '"${CLAUDE_PROJECT_DIR}/.claude/hooks/format.sh"'
        data, report = self.assert_round_trips("--event", "PostToolUse", "--matcher", "Edit|Write",
                                               "--command", command, "--timeout", "30")
        self.assertEqual(report["warnings"], [])
        self.assertEqual(data, {"hooks": {"PostToolUse": [{
            "matcher": "Edit|Write",
            "hooks": [{"type": "command", "command": command, "timeout": 30}]}]}})

    def test_every_known_event_and_type_round_trips(self):
        for event in hooktool.EVENTS:
            self.assert_round_trips("--event", event, "--command", "x.sh")
        self.assert_round_trips("--event", "PostToolUse", "--type", "http", "--url", "http://localhost:1/h")
        self.assert_round_trips("--event", "PreToolUse", "--type", "mcp_tool", "--server", "s", "--tool", "t")
        for htype in ("prompt", "agent"):
            self.assert_round_trips("--event", "PreToolUse", "--type", htype, "--prompt", "Is it safe? $ARGUMENTS")

    def test_every_supported_type_on_every_event_validates_clean(self):
        flags = {"command": ["--command", "x.sh"], "http": ["--url", "http://localhost:1/h"],
                 "mcp_tool": ["--server", "s", "--tool", "t"], "prompt": ["--prompt", "p"], "agent": ["--prompt", "p"]}
        for event, meta in hooktool.EVENTS.items():
            for htype in sorted(hooktool.HANDLER_TYPES):
                code, out, err = run("scaffold", "--event", event, "--type", htype, *flags[htype])
                if htype in meta["types"]:
                    self.assertEqual(code, 0, (event, htype, err))
                    self.assertEqual(hooktool.validate_config(json.loads(out)), ([], []), (event, htype))
                else:
                    self.assertEqual((code, out), (2, ""), (event, htype))
                    self.assertIn("does not run", err)

    def test_if_exec_form_and_on_failure_flags(self):
        data, report = self.assert_round_trips(
            "--event", "PreToolUse", "--matcher", "Bash", "--if", "Bash(git push *)",
            "--command", "node", "--arg", "${CLAUDE_PROJECT_DIR}/.claude/hooks/check.js", "--arg=--strict",
            "--on-failure", "block")
        self.assertEqual(report["warnings"], [])
        self.assertEqual(data["hooks"]["PreToolUse"][0]["hooks"][0], {
            "type": "command", "if": "Bash(git push *)", "command": "node",
            "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/check.js", "--strict"], "onFailure": "block"})

    def test_drops_matcher_on_stop(self):
        code, out, err = run("scaffold", "--event", "Stop", "--matcher", "Bash", "--command", "check.sh")
        self.assertEqual(code, 0)
        self.assertNotIn("matcher", json.loads(out)["hooks"]["Stop"][0])
        self.assertIn("takes no matcher", err)

    def test_async_on_blocking_event_notes_on_stderr_and_validate_warns(self):
        code, out, err = run("scaffold", "--event", "PreToolUse", "--matcher", "Bash", "--command", "x", "--async")
        self.assertEqual(code, 0)
        self.assertIn("cannot block", err)
        self.assertTrue(has(json.loads(run("validate", "-", "--json", stdin=out)[1])["warnings"], "async"))

    def test_usage_errors_exit_2_with_empty_stdout(self):
        for args in (
            ["--event", "PreToolUse"],                                    # no --command
            ["--event", "PreToolUse", "--type", "http"],                  # no --url
            ["--event", "PreToolUse", "--type", "bogus", "--command", "x"],
            ["--event", "PreToolUse", "--command", "x", "--timeout", "0"],
            ["--event", "PostToolUse", "--type", "http", "--url", "u", "--async"],
            ["--command", "x"],                                           # no --event
            ["--event", "PreToolUse", "--type", "mcp_tool", "--server", "s"],   # no --tool
            ["--event", "PreToolUse", "--type", "prompt"],                # no --prompt
            ["--event", "SessionStart", "--type", "prompt", "--prompt", "p"],   # event does not run prompt hooks
            ["--event", "Stop", "--command", "x", "--if", "Bash(git *)"],        # --if outside a tool event
            ["--event", "PreToolUse", "--type", "http", "--url", "u", "--arg", "a"],
            ["--event", "PreToolUse", "--type", "prompt", "--prompt", "p", "--on-failure", "block"],
        ):
            code, out, err = run("scaffold", *args)
            self.assertEqual((code, out), (2, ""), args)
            self.assertTrue(err.strip(), args)


class Cli(unittest.TestCase):
    def test_events_json_parses(self):
        code, out, _ = run("events", "--json")
        self.assertEqual(code, 0)
        events = json.loads(out)
        self.assertEqual({e["event"] for e in events}, set(hooktool.EVENTS))
        for e in events:
            self.assertEqual(set(e), {"event", "blocks", "matcher", "inject", "context", "types", "values", "note"})
            self.assertIsInstance(e["blocks"], bool)

    def test_events_table(self):
        code, out, _ = run("events")
        self.assertEqual(code, 0)
        for event in hooktool.EVENTS:
            self.assertRegex(out, r"(?m)^  %s " % event)
        self.assertNotIn("not exhaustive", out)

    def test_validate_json_shape(self):
        for raw in (json.dumps(config(cmd())), json.dumps(config({"type": "nope"})), "{not json"):
            _, out, _ = run("validate", "-", "--json", stdin=raw)
            report = json.loads(out)
            self.assertEqual(list(report), ["valid", "errors", "warnings"])
            self.assertIsInstance(report["valid"], bool)
            self.assertIsInstance(report["errors"], list)
            self.assertIsInstance(report["warnings"], list)

    def test_exit_codes(self):
        good = json.dumps(config(cmd()))
        bad = json.dumps(config({"type": "nope"}))
        self.assertEqual(run("validate", "-", stdin=good)[0], 0)
        self.assertEqual(run("validate", stdin=good)[0], 0)            # path omitted reads stdin
        self.assertEqual(run("validate", "-", stdin=bad)[0], 1)
        self.assertEqual(run("validate", "-", stdin="{not json")[0], 1)
        self.assertEqual(run()[0], 2)                                  # no subcommand
        self.assertEqual(run("nosuch")[0], 2)
        self.assertEqual(run("validate", "--bogus")[0], 2)
        self.assertEqual(run("--help")[0], 0)

    def test_missing_file_exits_2_without_traceback(self):
        code, out, err = run("validate", os.path.join(ROOT, "no", "such", "file.json"), "--json")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot read", err)
        self.assertNotIn("Traceback", err)

    def test_human_output_streams(self):
        code, out, err = run("validate", "-", stdin=json.dumps(config(cmd(**{"async": True}))))
        self.assertEqual(code, 0)
        self.assertEqual(out, "ok valid (1 warning(s)).\n")
        self.assertIn("warning:", err)
        code, out, err = run("validate", "-", stdin=json.dumps(config({"type": "nope"})))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("error:", err)

    def test_help_documents_exit_codes_and_plugin_flag(self):
        self.assertIn("exit codes", run("--help")[1])
        vhelp = run("validate", "--help")[1]
        self.assertIn("--plugin", vhelp)
        self.assertIn("exit codes", vhelp)

    def test_claudemd_mentions_every_subcommand_and_plugin(self):
        code, out, _ = run("claudemd")
        self.assertEqual(code, 0)
        for token in (" events", " fields", " scaffold", " validate", " claudemd", "--plugin", "--json"):
            self.assertIn(token, out)


# The complete event list as of Claude Code v2.1.295: the summary table at
# https://code.claude.com/docs/en/hooks and the event enum in the binary agree on
# these 33. If Claude Code adds or drops an event, edit this list and EVENTS together.
PINNED_EVENTS = [
    "SessionStart", "Setup", "UserPromptSubmit", "UserPromptExpansion", "PreToolUse", "PermissionRequest",
    "PermissionDenied", "PostToolUse", "PostToolUseFailure", "PostToolBatch", "Notification", "MessageDisplay",
    "SubagentStart", "SubagentStop", "TaskCreated", "TaskCompleted", "Stop", "StopFailure", "TeammateIdle",
    "InstructionsLoaded", "ConfigChange", "CwdChanged", "DirectoryAdded", "FileChanged", "WorktreeCreate",
    "WorktreeRemove", "PreCompact", "PostCompact", "PreModelSwitch", "PostModelSwitch", "Elicitation",
    "ElicitationResult", "SessionEnd",
]
PINNED_BLOCKING = {
    "PreToolUse", "UserPromptSubmit", "UserPromptExpansion", "Stop", "SubagentStop", "TeammateIdle", "TaskCreated",
    "TaskCompleted", "ConfigChange", "PostToolBatch", "PreCompact", "PreModelSwitch", "Elicitation",
    "ElicitationResult", "WorktreeCreate", "WorktreeRemove",
}
PINNED_NO_MATCHER = {
    "UserPromptSubmit", "PostToolBatch", "Stop", "TeammateIdle", "TaskCreated", "TaskCompleted", "WorktreeCreate",
    "WorktreeRemove", "MessageDisplay", "CwdChanged",
}
PINNED_STDOUT_INJECTS = {"SessionStart", "UserPromptSubmit", "UserPromptExpansion", "PostModelSwitch"}
PINNED_ADDITIONAL_CONTEXT = PINNED_STDOUT_INJECTS | {
    "SubagentStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch", "Stop", "SubagentStop",
}
PINNED_ALL_TYPES = {
    "PermissionDenied", "PostToolBatch", "PostToolUse", "PostToolUseFailure", "PreToolUse", "Stop", "SubagentStop",
    "TaskCompleted", "TaskCreated", "TeammateIdle", "UserPromptExpansion", "UserPromptSubmit",
}


class EventTable(unittest.TestCase):
    def test_event_list_is_pinned(self):
        self.assertEqual(list(hooktool.EVENTS), PINNED_EVENTS)
        self.assertEqual(len(PINNED_EVENTS), 33)

    def test_blocking_matcher_and_context_columns_are_pinned(self):
        ev = hooktool.EVENTS
        self.assertEqual({e for e, m in ev.items() if m["blocks"]}, PINNED_BLOCKING)
        self.assertEqual({e for e, m in ev.items() if m["matcher"] is None}, PINNED_NO_MATCHER)
        self.assertEqual({e for e, m in ev.items() if m["inject"]}, PINNED_STDOUT_INJECTS)
        self.assertEqual({e for e, m in ev.items() if m["context"]}, PINNED_ADDITIONAL_CONTEXT)

    def test_handler_type_support_is_pinned(self):
        ev = hooktool.EVENTS
        all_five = ["command", "http", "mcp_tool", "prompt", "agent"]
        self.assertEqual({e for e, m in ev.items() if m["types"] == all_five}, PINNED_ALL_TYPES)
        self.assertEqual(ev["PermissionRequest"]["types"], ["command", "http", "mcp_tool", "prompt"])
        self.assertEqual(ev["SessionStart"]["types"], ["command", "mcp_tool"])
        self.assertEqual(ev["Setup"]["types"], ["command"])
        for event, meta in ev.items():
            if event not in PINNED_ALL_TYPES | {"PermissionRequest", "SessionStart", "Setup"}:
                self.assertEqual(meta["types"], ["command", "http", "mcp_tool"], event)

    def test_tool_events_and_matcher_values(self):
        self.assertEqual(set(hooktool.TOOL_EVENTS), {"PreToolUse", "PostToolUse", "PostToolUseFailure",
                                                     "PermissionRequest", "PermissionDenied"})
        self.assertEqual(hooktool.EVENTS["SessionStart"]["values"], ["startup", "resume", "clear", "compact", "fork"])
        self.assertEqual(hooktool.EVENTS["PreCompact"]["values"], ["manual", "auto"])
        for event in hooktool.TOOL_EVENTS:
            self.assertEqual(hooktool.EVENTS[event]["matcher"], "tool name")

    def test_handler_schema_is_pinned(self):
        self.assertEqual(hooktool.HANDLER_TYPES, {"command", "http", "mcp_tool", "prompt", "agent"})
        self.assertEqual(hooktool.HANDLER_REQUIRED, {"command": ("command",), "http": ("url",),
                                                     "mcp_tool": ("server", "tool"), "prompt": ("prompt",),
                                                     "agent": ("prompt",)})


class HandlerTypeSupport(unittest.TestCase):
    def test_unsupported_type_is_an_error(self):
        for event, handler in (("SessionStart", {"type": "prompt", "prompt": "p"}),
                               ("SessionStart", {"type": "http", "url": "http://x"}),
                               ("Setup", {"type": "mcp_tool", "server": "s", "tool": "t"}),
                               ("PermissionRequest", {"type": "agent", "prompt": "p"}),
                               ("PreCompact", {"type": "prompt", "prompt": "p"})):
            errors, _ = hooktool.validate_config(config(handler, event=event, matcher=None))
            self.assertTrue(has(errors, f"{event} does not run '{handler['type']}' handlers"), (event, errors))

    def test_supported_types_are_quiet(self):
        for event, handler in (("SessionStart", {"type": "mcp_tool", "server": "s", "tool": "t"}),
                               ("Stop", {"type": "agent", "prompt": "p"}),
                               ("PermissionRequest", {"type": "prompt", "prompt": "p"})):
            self.assertEqual(hooktool.validate_config(config(handler, event=event, matcher=None)), ([], []), event)


class IfField(unittest.TestCase):
    def test_if_on_tool_events_is_quiet(self):
        for event in hooktool.TOOL_EVENTS:
            data = config(cmd(**{"if": "Write(**/SKILL.md)"}), event=event, matcher="Read|Write|Edit")
            self.assertEqual(hooktool.validate_config(data), ([], []), event)
        for rule in ("Bash(git *)", "Edit(*.ts)", "Bash", "mcp__plugin_my-plugin_db__query", "Bash(echo (a) | cat)"):
            self.assertEqual(hooktool.validate_config(config(cmd(**{"if": rule}), matcher="*")), ([], []), rule)

    def test_if_outside_tool_events_is_an_error(self):
        for event in ("SessionStart", "Stop", "UserPromptSubmit", "PostToolBatch"):
            errors, _ = hooktool.validate_config(config(cmd(**{"if": "Bash(git *)"}), event=event, matcher=None))
            self.assertTrue(has(errors, "never runs"), event)

    def test_if_must_be_a_non_empty_string(self):
        for bad in ("", "  ", ["Bash(git *)"], True, None):
            errors, _ = hooktool.validate_config(config(cmd(**{"if": bad})))
            self.assertTrue(has(errors, "'if' must be a non-empty string"), repr(bad))

    def test_combined_rules_warn(self):
        for rule in ("Write(**/SKILL.md)|Edit(**/SKILL.md)", "Write(a) && Edit(b)", "Write(a), Edit(b)", "(git *)"):
            errors, warnings = hooktool.validate_config(config(cmd(**{"if": rule}), matcher="*"))
            self.assertEqual(errors, [], rule)
            self.assertTrue(has(warnings, "not a single permission rule"), rule)

    def test_if_tool_outside_matcher_warns(self):
        _, warnings = hooktool.validate_config(config(cmd(**{"if": "Bash(git *)"}), matcher="Read|Write|Edit"))
        self.assertTrue(has(warnings, "never passes that tool"), warnings)
        # a regex matcher is not second-guessed
        self.assertEqual(hooktool.validate_config(config(cmd(**{"if": "NotebookEdit(*)"}), matcher="Edit.*")), ([], []))


class HandlerFields(unittest.TestCase):
    def test_once_warns_outside_skill_frontmatter(self):
        errors, warnings = hooktool.validate_config(config(cmd(once=True)))
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "only honoured for hooks in skill frontmatter"), warnings)
        self.assertEqual(hooktool.validate_config(config(cmd(once=False))), ([], []))

    def test_boolean_fields_must_be_booleans(self):
        for key in ("async", "asyncRewake", "once"):
            errors, _ = hooktool.validate_config(config(cmd(**{key: "true"}), event="PostToolUse"))
            self.assertTrue(has(errors, f"'{key}' must be true or false"), key)

    def test_exec_form(self):
        ok = cmd("node", args=["${CLAUDE_PLUGIN_ROOT}/scripts/format.js", "--fix"])
        self.assertEqual(hooktool.validate_config(config(ok), plugin=True), ([], []))
        # no shell runs, so an unquoted plugin variable in `command` is fine with args
        self.assertEqual(hooktool.validate_config(config(cmd("${CLAUDE_PLUGIN_ROOT}/scripts/x.sh", args=[]))), ([], []))
        for bad in ("--fix", [1], [["a"]], None):
            errors, _ = hooktool.validate_config(config(cmd("node", args=bad)))
            self.assertTrue(has(errors, "'args' must be an array of strings"), repr(bad))
        _, warnings = hooktool.validate_config(config(cmd("node script.js", args=["--fix"])))
        self.assertTrue(has(warnings, "move the extra words into 'args'"), warnings)
        self.assertEqual(hooktool.validate_config(config(cmd("C:\\Program Files\\nodejs\\node.exe", args=[]))), ([], []))

    def test_shell(self):
        self.assertEqual(hooktool.validate_config(config(cmd(shell="bash"))), ([], []))
        errors, _ = hooktool.validate_config(config(cmd(shell="zsh")))
        self.assertTrue(has(errors, "'shell' must be"), errors)
        # powershell has its own quoting rules; the double-quote advice does not apply
        ps = cmd("& ${CLAUDE_PLUGIN_ROOT}/x.ps1", shell="powershell")
        self.assertEqual(hooktool.validate_config(config(ps)), ([], []))
        _, warnings = hooktool.validate_config(config(cmd("node", args=[], shell="bash")))
        self.assertTrue(has(warnings, "'shell' is ignored"), warnings)

    def test_on_failure(self):
        self.assertEqual(hooktool.validate_config(config(cmd(onFailure="block"))), ([], []))
        self.assertEqual(hooktool.validate_config(config(cmd(onFailure="continue"))), ([], []))
        errors, _ = hooktool.validate_config(config(cmd(onFailure="deny")))
        self.assertTrue(has(errors, "'onFailure' must be"), errors)
        for event in ("Stop", "SubagentStop", "TaskCompleted", "TeammateIdle"):
            matcher = any_matcher(event)
            _, warnings = hooktool.validate_config(config(cmd(onFailure="block"), event=event, matcher=matcher))
            self.assertTrue(has(warnings, f"'onFailure' has no effect on {event}"), event)
        _, warnings = hooktool.validate_config(config(cmd(onFailure="block", **{"async": True}), event="PostToolUse"))
        self.assertTrue(has(warnings, "no effect on a background"), warnings)
        _, warnings = hooktool.validate_config(config({"type": "prompt", "prompt": "p", "onFailure": "block"}))
        self.assertTrue(has(warnings, "'onFailure' has no effect on a 'prompt' handler"), warnings)

    def test_unknown_field_warns(self):
        errors, warnings = hooktool.validate_config(config(cmd(timeOut=5)))
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "'timeOut' has no effect"), warnings)
        self.assertTrue(has(warnings, "not a documented field"), warnings)

    def test_documented_fields_are_quiet(self):
        handlers = [
            cmd(statusMessage="Checking", timeout=5),
            {"type": "http", "url": "http://localhost:8080/h", "headers": {"Authorization": "Bearer $MY_TOKEN"},
             "allowedEnvVars": ["MY_TOKEN"], "onFailure": "block"},
            {"type": "mcp_tool", "server": "my_server", "tool": "scan", "input": {"file_path": "${tool_input.file_path}"}},
            {"type": "prompt", "prompt": "ok? $ARGUMENTS", "model": "haiku", "continueOnBlock": True},
            {"type": "agent", "prompt": "verify $ARGUMENTS", "model": "haiku"},
        ]
        for handler in handlers:
            self.assertEqual(hooktool.validate_config(config(handler)), ([], []), handler["type"])

    def test_http_header_variable_must_be_allowed(self):
        handler = {"type": "http", "url": "http://x", "headers": {"Authorization": "Bearer ${TOKEN}", "X": "$OTHER"},
                   "allowedEnvVars": ["OTHER"]}
        errors, warnings = hooktool.validate_config(config(handler))
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("$TOKEN", warnings[0])
        errors, _ = hooktool.validate_config(config({"type": "http", "url": "http://x", "headers": ["a"]}))
        self.assertTrue(has(errors, "'headers' must be an object"), errors)

    def test_mcp_input_must_be_an_object(self):
        errors, _ = hooktool.validate_config(config({"type": "mcp_tool", "server": "s", "tool": "t", "input": "x"}))
        self.assertTrue(has(errors, "'input' must be an object"), errors)

    def test_user_config_in_shell_form_plugin_hook_is_an_error(self):
        handler = cmd('curl "${user_config.webhook_url}"')
        errors, _ = hooktool.validate_config(config(handler), plugin=True)
        self.assertTrue(has(errors, "user_config"), errors)
        self.assertEqual(hooktool.validate_config(config(handler)), ([], []))          # settings: not substituted
        exec_form = cmd("curl", args=["${user_config.webhook_url}"])
        self.assertEqual(hooktool.validate_config(config(exec_form), plugin=True), ([], []))


class MatcherValues(unittest.TestCase):
    def test_exact_and_regex_paths(self):
        self.assertEqual(hooktool.matcher_tokens("PreToolUse", "Edit|Write"), ["Edit", "Write"])
        self.assertEqual(hooktool.matcher_tokens("PreToolUse", "Edit, Write"), ["Edit", "Write"])
        self.assertEqual(hooktool.matcher_tokens("SubagentStart", "code-reviewer"), ["code-reviewer"])
        for regex in ("mcp__.*", "^Edit$", "Edit.*", "^my-plugin:reviewer$"):
            self.assertIsNone(hooktool.matcher_tokens("PreToolUse", regex), regex)
        for match_all in ("", "*"):
            self.assertIsNone(hooktool.matcher_tokens("PreToolUse", match_all))
        # FileChanged and StopFailure: a hyphen, space or comma puts the matcher on the regex path
        self.assertIsNone(hooktool.matcher_tokens("StopFailure", "rate-limit"))
        self.assertEqual(hooktool.matcher_tokens("StopFailure", "rate_limit|overloaded"), ["rate_limit", "overloaded"])

    def test_value_outside_a_closed_set_warns(self):
        for event, matcher in (("SessionStart", "startup|restart"), ("PreCompact", "automatic"),
                               ("SessionEnd", "bypass_permissions_disabled"), ("Setup", "install"),
                               ("ConfigChange", "user"), ("InstructionsLoaded", "startup")):
            errors, warnings = hooktool.validate_config(config(cmd(), event=event, matcher=matcher))
            self.assertEqual(errors, [], event)
            self.assertTrue(has(warnings, "never matches"), (event, warnings))

    def test_values_inside_the_set_are_quiet(self):
        for event, meta in hooktool.EVENTS.items():
            if meta["values"]:
                data = config(cmd(), event=event, matcher="|".join(meta["values"]))
                self.assertEqual(hooktool.validate_config(data), ([], []), event)
        self.assertEqual(hooktool.validate_config(config(cmd(), event="SessionStart", matcher="^(startup|x)$")), ([], []))

    def test_open_sets_are_not_second_guessed(self):
        for event, matcher in (("Notification", "some_new_type"), ("SubagentStart", "my-agent"),
                               ("FileChanged", ".envrc|.env"), ("StopFailure", "rate_limit"),
                               ("PreModelSwitch", "claude-opus-5"), ("UserPromptExpansion", "deploy")):
            self.assertEqual(hooktool.validate_config(config(cmd(), event=event, matcher=matcher)), ([], []), event)

    def test_bare_mcp_server_matcher_warns(self):
        for matcher in ("mcp__memory", "mcp__brave-search", "Bash|mcp__memory"):
            _, warnings = hooktool.validate_config(config(cmd(), matcher=matcher))
            self.assertTrue(has(warnings, "matches no tool"), matcher)

    def test_multiedit_matcher_warns(self):
        _, warnings = hooktool.validate_config(config(cmd(), event="PostToolUse", matcher="Write|Edit|MultiEdit"))
        self.assertTrue(has(warnings, "'MultiEdit' is not a tool"), warnings)
        self.assertEqual(hooktool.validate_config(config(cmd(), event="PostToolUse", matcher="Write|Edit|NotebookEdit")),
                         ([], []))


class PluginOwnHooks(unittest.TestCase):
    """The plugin's own hooks/: config shape and script behaviour."""
    LINT = os.path.join(ROOT, "scripts", "claude-lint")
    SHIM = os.path.join(ROOT, "hooks", "lint-on-write.sh")

    def shim(self, payload, env=None):
        base = {"PATH": os.environ.get("PATH", ""), "CLAUDE_PLUGIN_ROOT": ROOT}
        return subprocess.run([shutil.which("sh") or "/bin/sh", self.SHIM], input=payload,
                              capture_output=True, text=True, env=env or base)

    def test_hooks_json_has_no_errors_or_warnings(self):
        _, out, err = run("validate", PLUGIN_HOOKS, "--json")
        self.assertEqual(json.loads(out), {"valid": True, "errors": [], "warnings": []}, err)

    def test_hooks_json_events_matcher_and_quoting(self):
        with open(PLUGIN_HOOKS, encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        self.assertEqual(set(hooks), {"SessionStart", "PreToolUse", "PostToolUse"})
        self.assertEqual([len(groups) for groups in hooks.values()], [1, 1, 1])
        # no hook runs in every session unasked: SessionStart only resets delivery, and not on resume or fork
        self.assertEqual(hooks["SessionStart"][0]["matcher"], "startup|clear|compact")
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "Bash")
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "Read|Write|Edit")
        for groups in hooks.values():
            for group in groups:
                for h in group["hooks"]:
                    self.assertRegex(h["command"], r'^sh "\$\{CLAUDE_PLUGIN_ROOT\}/hooks/[a-z-]+\.sh"$')
                    script = h["command"].split("/hooks/")[1].rstrip('"')
                    self.assertTrue(os.path.isfile(os.path.join(ROOT, "hooks", script)), script)

    def test_no_hook_injects_into_a_session_that_touched_no_artifact(self):
        # the litmus used to be a SessionStart hook paid by every session; it now leads the first rule delivery
        self.assertFalse(os.path.exists(os.path.join(ROOT, "hooks", "seam-punchline.sh")))
        reset = os.path.join(ROOT, "hooks", "reset-rule-delivery.sh")
        for source in ("startup", "resume", "clear", "compact", "fork"):
            payload = json.dumps({"session_id": "no-such-session", "hook_event_name": "SessionStart", "source": source})
            with tempfile.TemporaryDirectory() as tmp:
                p = subprocess.run(["sh", reset], input=payload, capture_output=True, text=True,
                                   env={"PATH": os.environ.get("PATH", ""), "CLAUDE_PLUGIN_ROOT": ROOT, "TMPDIR": tmp})
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""), source)

    def test_shim_is_silent_for_non_artifacts(self):
        for path in ("/tmp/src/app.py", "/tmp/notes.txt", "/tmp/README.md", "/tmp/package.json"):
            p = self.shim(json.dumps({"tool_name": "Write", "tool_input": {"file_path": path, "content": "x"}}))
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""), path)
        for junk in ("", "not json", "{}", '{"tool_input": {}}'):
            p = self.shim(junk)
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""), junk)

    def test_shim_reports_findings_as_additional_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".claude"))
            bad = os.path.join(tmp, ".claude", "settings.json")
            with open(bad, "w", encoding="utf-8") as f:
                json.dump({"hooks": {"PreToolUse": [{"hooks": [{"type": "command"}]}]}}, f)
            event = {"hook_event_name": "PostToolUse", "tool_name": "Write", "cwd": tmp,
                     "tool_input": {"file_path": bad, "content": "multi\nline $HOME `id` %s 'q' \\"}}
            for payload in (json.dumps(event), json.dumps(event, indent=2)):   # one line, or pretty-printed
                p = self.shim(payload)
                self.assertEqual((p.returncode, p.stderr), (0, ""))
                out = json.loads(p.stdout)["hookSpecificOutput"]
                self.assertEqual(out["hookEventName"], "PostToolUse")
                self.assertIn("[claude-lint]", out["additionalContext"])
                self.assertIn("requires 'command'", out["additionalContext"])

    def test_shim_without_python_or_linter_is_a_silent_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.dumps({"tool_input": {"file_path": "/x/.claude/rules/r.md"}})
            p = self.shim(payload, env={"PATH": tmp, "CLAUDE_PLUGIN_ROOT": ROOT})          # no python3
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))
            p = self.shim(payload, env={"PATH": tmp})                                      # no linter either
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))


class FieldsTable(unittest.TestCase):
    def test_json_rows_have_the_documented_keys(self):
        code, out, _ = run("fields", "--json")
        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertEqual([r["field"] for r in rows], [f.name for f in hooktool.FIELDS])
        for r in rows:
            self.assertEqual(set(r), {"field", "types", "required", "type", "default", "effect", "since"})
            self.assertTrue(set(r["required"]) <= set(r["types"]), r["field"])

    def test_one_type_filters_and_marks_required(self):
        rows = json.loads(run("fields", "mcp_tool", "--json")[1])
        names = {r["field"] for r in rows}
        self.assertEqual(names, hooktool.COMMON_FIELDS | hooktool.HANDLER_FIELDS["mcp_tool"])
        self.assertNotIn("command", names)
        _, text, _ = run("fields", "http")
        self.assertRegex(text, r"(?m)^  url +http\* ")
        self.assertNotRegex(text, r"(?m)^  shell ")

    def test_human_output_is_one_line_per_field(self):
        code, out, _ = run("fields")
        self.assertEqual(code, 0)
        for field in hooktool.FIELDS:
            self.assertEqual(len(re.findall(r"(?m)^  %s " % re.escape(field.name), out)), 1, field.name)

    def test_unknown_type_is_a_usage_error(self):
        code, out, _ = run("fields", "nope")
        self.assertEqual((code, out), (2, ""))

    def test_since_version_is_reported(self):
        rows = {r["field"]: r for r in json.loads(run("fields", "--json")[1])}
        self.assertEqual(rows["onFailure"]["since"], "2.1.295")
        self.assertIsNone(rows["timeout"]["since"])
        self.assertIn("(v2.1.295+)", run("fields", "command")[1])

    def test_reference_facts_are_in_the_table(self):
        by = {f.name: f for f in hooktool.FIELDS}
        self.assertEqual(set(by["onFailure"].types), {"command", "http"})
        self.assertEqual(set(by["async"].types), {"command"})
        self.assertEqual(set(by["prompt"].required), {"prompt", "agent"})
        self.assertEqual(set(by["continueOnBlock"].types), {"prompt"})
        self.assertEqual(by["continueOnBlock"].default, "false")       # a documented field, not a pointer
        self.assertIn("continues instead of ending the turn", by["continueOnBlock"].effect)
        for field in hooktool.FIELDS:
            self.assertNotIn("see the docs", field.effect.lower(), field.name)
        for token in ("600", "30", "60"):
            self.assertIn(token, by["timeout"].default)
        self.assertEqual(by["once"].default, "false")

    def test_validator_sets_come_from_the_table(self):
        self.assertEqual(hooktool.COMMON_FIELDS, {"type", "if", "timeout", "statusMessage", "once"})
        self.assertEqual(hooktool.HANDLER_FIELDS["command"], {"command", "args", "async", "asyncRewake", "shell", "onFailure"})
        self.assertEqual(hooktool.HANDLER_FIELDS["agent"], {"prompt", "model"})

    def test_every_field_validate_names_is_in_fields_json(self):
        table = {r["field"] for r in json.loads(run("fields", "--json")[1])}
        source = "".join(inspect.getsource(fn) for fn in (hooktool._check_handler, hooktool._check_command,
                                                         hooktool._check_http))
        named = set(re.findall(r"\bh(?:\.get\(|\[)\"(\w+)\"", source))
        named |= set(re.findall(r"\"(\w+)\" in h\b", source))
        named |= set(re.findall(r"\bkey == \"(\w+)\"", source))
        self.assertTrue({"timeout", "onFailure", "args", "shell", "input", "headers"} <= named, named)
        self.assertEqual(named - table, set())

    def test_every_table_field_is_accepted_without_a_no_effect_warning(self):
        samples = {"bool": True, "string": "x", "number": 5, "string[]": ["a"], "map<string>": {"A": "b"},
                   "object": {}, "bash|powershell": "bash", "continue|block": "continue", "rule": "Bash(git *)"}
        for field in hooktool.FIELDS:
            for htype in field.types:
                handler = {"type": htype}
                for req in hooktool.HANDLER_REQUIRED[htype]:
                    handler[req] = "x"
                if field.name != "type":
                    handler[field.name] = samples[field.type]
                errors, warnings = hooktool.validate_config(config(handler))
                self.assertFalse(has(warnings, "has no effect"), (field.name, htype, warnings))
                self.assertEqual(errors, [], (field.name, htype))

    def test_a_field_on_the_wrong_type_warns(self):
        for field in hooktool.FIELDS:
            for htype in set(hooktool.HANDLER_TYPES) - set(field.types):
                errors, warnings = hooktool.validate_config(config({"type": htype, field.name: "x"}))
                self.assertTrue(has(warnings, f"'{field.name}' has no effect"), (field.name, htype))


class EventValues(unittest.TestCase):
    def test_human_events_output_lists_every_closed_value_set(self):
        _, out, _ = run("events")
        for event, meta in hooktool.EVENTS.items():
            if meta["values"]:
                self.assertIn(f"  {event:<20} {meta['matcher']}: {', '.join(meta['values'])}", out)

    def test_events_without_values_have_no_values_line(self):
        lines = hooktool.matcher_value_lines(hooktool.EVENTS)
        self.assertEqual(len(lines), sum(1 for m in hooktool.EVENTS.values() if m["values"]))
        self.assertFalse(any(line.startswith("  Stop ") for line in lines))


class ClaudeMdCommands(unittest.TestCase):
    def test_every_command_is_runnable_by_absolute_path(self):
        _, out, _ = run("claudemd")
        spans = [ln.split("`")[1] for ln in out.splitlines() if ln.startswith("- `")]
        self.assertGreaterEqual(len(spans), 5)
        for span in spans:
            self.assertTrue(span.startswith('python3 "'), span)
        self.assertNotRegex(out, r"(?<![/\w])hooktool (events|fields|scaffold|validate|claudemd)")

    def test_path_is_this_script_absolute_and_quoted(self):
        _, out, _ = run("claudemd", cwd=tempfile.gettempdir())
        self.assertIn('python3 "%s" events' % os.path.abspath(HOOKTOOL), out)
        self.assertTrue(os.path.isabs(os.path.abspath(HOOKTOOL)))

    def test_mentions_fields(self):
        self.assertIn('" fields [TYPE] [--json]', run("claudemd")[1])

    def test_text_follows_the_path_it_is_given(self):
        text = hooktool.claudemd_text("/a b/hooktool.py")
        self.assertIn('python3 "/a b/hooktool.py" validate', text)


class RunsByPath(unittest.TestCase):
    """hooktool has no wrapper and is not on PATH: it is run as python3 <path>/hooktool.py."""

    def test_runs_from_any_directory_by_its_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([sys.executable, HOOKTOOL, "claudemd"], capture_output=True, text=True, cwd=tmp)
            self.assertEqual((p.returncode, p.stdout), (0, hooktool.claudemd_text(os.path.abspath(HOOKTOOL))), p.stderr)
            p = subprocess.run([sys.executable, HOOKTOOL, "validate", "-", "--plugin"], input="{}",
                               capture_output=True, text=True, cwd=tmp)
            self.assertEqual(p.returncode, 1)

    def test_no_wrapper_directory_came_back(self):
        self.assertFalse(os.path.lexists(os.path.join(ROOT, "bin")))


if __name__ == "__main__":
    unittest.main()
