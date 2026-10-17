"""Tests for scripts/claude-lint. Run from the plugin root:

    python3 -m unittest discover -s tests -v
"""

import importlib.machinery
import importlib.util
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "scripts", "claude-lint")
SHIM = os.path.join(ROOT, "hooks", "lint-on-write.sh")

_loader = importlib.machinery.SourceFileLoader("claude_lint", os.path.join(ROOT, "scripts", "claude_lint.py"))
_spec = importlib.util.spec_from_loader("claude_lint", _loader)
cl = importlib.util.module_from_spec(_spec)
_loader.exec_module(cl)

BT = "`"
FENCE = BT * 3


def write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content))
    return path


def run(*args, stdin=None, cwd=None, env=None):
    return subprocess.run([sys.executable, LINT, *args], input=stdin, capture_output=True,
                          text=True, cwd=cwd, env=env)


class TempCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = os.path.realpath(self._tmp.name)
        cl._INDEX_CACHE.clear()

    def plugin(self, name="demo"):
        write(self.tmp, ".claude-plugin/plugin.json", json.dumps({"name": name}))
        return self.tmp

    def ids(self, path):
        cl._INDEX_CACHE.clear()
        return [f.id for f in cl.lint_file(path)]

    def findings(self, path):
        cl._INDEX_CACHE.clear()
        return cl.lint_file(path)


# ---- frontmatter ------------------------------------------------------------

class FrontmatterTests(unittest.TestCase):
    def parse(self, text):
        return cl.parse_frontmatter(textwrap.dedent(text))

    def test_scalars_and_types(self):
        fm = self.parse("""\
            ---
            name: my-skill   # trailing comment
            description: "Quoted: with colon"
            background: true
            maxTurns: 12
            single: 'it''s'
            ---
            body line
            """)
        self.assertTrue(fm.present)
        self.assertEqual(fm.get("name"), "my-skill")
        self.assertEqual(fm.get("description"), "Quoted: with colon")
        self.assertIs(fm.get("background"), True)
        self.assertEqual(fm.get("maxTurns"), 12)
        self.assertEqual(fm.get("single"), "it's")
        self.assertEqual(fm.line("background"), 4)
        self.assertEqual(fm.body_line, 8)
        self.assertEqual(fm.body.strip(), "body line")

    def test_folded_and_literal_blocks(self):
        fm = self.parse("""\
            ---
            description: >-
              First line
              second line.

              New paragraph.
            literal: |
              a
              b
            name: x
            ---
            """)
        self.assertEqual(fm.get("description"), "First line second line.\nNew paragraph.")
        self.assertEqual(fm.get("literal"), "a\nb\n")
        self.assertEqual(fm.get("name"), "x")
        self.assertEqual(fm.line("name"), 10)

    def test_lists_inline_and_block(self):
        fm = self.parse("""\
            ---
            tools: [Read, "Bash(git *)", Grep]
            paths:
              - "**/*.md"
              - 'src/**'
            skills:
            - one
            - two
            ---
            """)
        self.assertEqual(fm.get("tools"), ["Read", "Bash(git *)", "Grep"])
        self.assertEqual(fm.get("paths"), ["**/*.md", "src/**"])
        self.assertEqual(fm.raw["paths"], ['"**/*.md"', "'src/**'"])
        self.assertEqual(fm.get("skills"), ["one", "two"])

    def test_nested_mapping_and_multiline_plain(self):
        fm = self.parse("""\
            ---
            hooks:
              PreToolUse:
                - matcher: Bash
            description: starts here
              and continues
            ---
            """)
        self.assertIsInstance(fm.get("hooks"), dict)
        self.assertEqual(fm.get("description"), "starts here and continues")

    def test_absent_and_unterminated(self):
        fm = self.parse("# Title\n\ntext\n")
        self.assertFalse(fm.present)
        self.assertEqual(fm.body_line, 1)
        fm = self.parse("---\nname: x\nno end\n")
        self.assertFalse(fm.present)
        self.assertTrue(fm.errors)


    def test_comment_stripping_is_quote_aware(self):
        fm = self.parse("""\
            ---
            paths: ["src/a #b/*.ts", 'c'] # trailing
            tools: Bash(git log *) # why
            note: it's # a comment
            ---
            """)
        self.assertEqual(fm.get("paths"), ["src/a #b/*.ts", "c"])
        self.assertEqual(fm.get("tools"), "Bash(git log *)")
        self.assertEqual(fm.get("note"), "it's")
        self.assertEqual(fm.errors, [])

    def test_flow_list_with_escaped_quotes_and_bom(self):
        fm = cl.parse_frontmatter('\ufeff---\nallowed-tools: [Read, "Bash(python3 \\"a, b\\" *)"]\n---\nbody\n')
        self.assertTrue(fm.present)
        self.assertEqual(fm.get("allowed-tools"), ["Read", 'Bash(python3 "a, b" *)'])


# ---- classify ---------------------------------------------------------------

class ClassifyTests(TempCase):
    def test_positive(self):
        self.plugin()
        cases = {
            "skills/a/SKILL.md": "skill",
            ".claude/commands/x.md": "skill",
            ".claude/commands/sub/x.md": "skill",
            ".claude/rules/deep/r.md": "rule",
            "rules/r.md": "rule",
            ".claude/agents/a.md": "agent",
            "agents/x.md": "agent",
            "CLAUDE.md": "memory",
            "pkg/CLAUDE.local.md": "memory",
            "AGENTS.md": "memory",
            ".claude/AGENTS.md": "memory",
            "commands/c.md": "skill",
            ".claude/settings.staging.json": "hooks",
            ".claude/settings.json": "hooks",
            ".claude/settings.local.json": "hooks",
            "hooks/hooks.json": "hooks",
            ".claude-plugin/plugin.json": "plugin",
        }
        for rel, kind in cases.items():
            with self.subTest(rel=rel):
                self.assertEqual(cl.classify(os.path.join(self.tmp, rel)), kind)
                self.assertTrue(rel.endswith(cl.ARTIFACT_SUFFIXES))     # what the hook prefilter relies on
        self.assertEqual({kind for kind in cases.values()}, set(cl.KINDS))

    def test_negative(self):
        self.plugin()
        for rel in (".claude/usersettings.json", "usersettings.json", "app/settings.json",
                    "docs/agents/x.md", "docs/rules/x.md", "NOTSKILL.md", "skills/a/README.md",
                    "README.md", "hooks/other.json", ".claude/sub/settings.json", "CLAUDE.md.bak",
                    "AGENTS.txt", "agents.md", ".claude/settings..json", ".claude/settingsx.json"):
            with self.subTest(rel=rel):
                self.assertIsNone(cl.classify(os.path.join(self.tmp, rel)))

    def test_plugin_dirs_need_claude_plugin_sibling(self):
        # no .claude-plugin here
        self.assertIsNone(cl.classify(os.path.join(self.tmp, "agents/x.md")))
        self.assertIsNone(cl.classify(os.path.join(self.tmp, "rules/x.md")))

    def test_cli(self):
        self.plugin()
        r = run("classify", os.path.join(self.tmp, "agents/x.md"))
        self.assertEqual((r.returncode, r.stdout), (0, "agent\n"))
        r = run("classify", os.path.join(self.tmp, "docs/agents/x.md"))
        self.assertEqual((r.returncode, r.stdout), (1, ""))


    def test_extensions_listing_is_what_classify_can_return(self):
        r = run("classify", "--extensions")
        self.assertEqual((r.returncode, r.stdout.split()), (0, list(cl.ARTIFACT_SUFFIXES)))
        self.assertEqual(run("classify").returncode, 2)
        # every path classify accepts ends in a listed suffix, and nothing else gets past its first test
        self.plugin()
        accepted = ["skills/a/SKILL.md", ".claude/commands/c.md", ".claude/rules/r.md", "agents/a.md", "CLAUDE.md",
                    "CLAUDE.local.md", "AGENTS.md", ".claude-plugin/plugin.json", "hooks/hooks.json",
                    ".claude/settings.json", ".claude/settings.local.json", "rules/r.md", "commands/c.md"]
        for rel in accepted:
            path = os.path.join(self.tmp, rel)
            self.assertIsNotNone(cl.classify(path), rel)
            self.assertTrue(path.endswith(cl.ARTIFACT_SUFFIXES), rel)
            for other in (".MD", ".JSON", ".markdown", ".yaml", ".md.bak", ".jsonc", ""):
                self.assertIsNone(cl.classify(os.path.splitext(path)[0] + other), rel + other)


# ---- skills -----------------------------------------------------------------

GOOD_SKILL = f"""\
---
name: good
description: Does a thing. Use when the thing needs doing.
allowed-tools: Bash(claude --version *)
---
# Good

Written for Claude Code v2.1.170. Version: !{BT}claude --version 2>/dev/null || echo unknown{BT}

Pass $ARGUMENTS straight to the script. See [the notes](references/notes.md) and
{BT}scripts/run.sh{BT}. Then invoke Skill(good) or Skill(demo:other).

{FENCE}bash
echo "$ARGUMENTS"
{FENCE}

An escaped literal is fine: \\!{BT}command{BT}
"""


class SkillTests(TempCase):
    def good(self):
        self.plugin()
        write(self.tmp, "skills/good/references/notes.md", "notes\n")
        write(self.tmp, "skills/good/scripts/run.sh", "true\n")
        write(self.tmp, "skills/other/SKILL.md", "---\ndescription: other\n---\nbody\n")
        return write(self.tmp, "skills/good/SKILL.md", GOOD_SKILL)

    def skill(self, body="body\n", front="description: d\n", name="s"):
        return write(self.tmp, f"skills/{name}/SKILL.md", f"---\n{front}---\n{body}")

    def test_clean_skill(self):
        self.assertEqual(self.ids(self.good()), [])

    def test_sk001_sk002(self):
        self.assertIn("SK001", self.ids(self.skill(front="name: Bad_Name\n")))
        self.assertEqual(self.ids(self.skill(front="name: other\ndescription: d\n")), ["SK002"])
        f = self.findings(self.skill(front="description: d\nname: other\n"))[0]
        self.assertEqual(f.line, 3)

    def test_sk003_cap_boundary(self):
        ok = self.skill(front=f"description: >-\n  {'a' * 1000}\nwhen_to_use: {'b' * 536}\n")
        self.assertNotIn("SK003", self.ids(ok))
        over = self.skill(front=f"description: >-\n  {'a' * 1000}\nwhen_to_use: {'b' * 537}\n")
        self.assertIn("SK003", self.ids(over))

    def test_sk004(self):
        bad = self.skill(front="description: d\ndisable-model-invocation: true\nuser-invocable: false\n")
        self.assertIn("SK004", self.ids(bad))
        ok = self.skill(front="description: d\ndisable-model-invocation: true\n")
        self.assertNotIn("SK004", self.ids(ok))

    def test_sk005_inline_and_fenced(self):
        p = self.skill(body=f"Status: !{BT}git status --short{BT}\n")
        found = self.findings(p)
        self.assertIn("SK005", [f.id for f in found])
        self.assertEqual([f.line for f in found if f.id == "SK005"], [4])
        p = self.skill(body=f"{FENCE}!\ngit status --short\n{FENCE}\n")
        self.assertIn("SK005", self.ids(p))
        p = self.skill(body=f"{FENCE}!\ngit status --short 2>/dev/null || echo none\n{FENCE}\n")
        self.assertNotIn("SK005", self.ids(p))

    def test_sk005_silencing_stderr_is_not_a_fallback(self):
        # Observed on 2.1.295: `ls nonexistent 2>/dev/null` still aborts the
        # load (non-zero exit); `|| true`, `; true` and a pipe tail do not.
        fallback = cl.has_failure_fallback
        for command in ("ls nope 2>/dev/null", "ls nope", "ls nope 2>&1", "test -f nope && echo yes",
                        "command", "", "echo \"a || echo b\" && false"):
            with self.subTest(command=command):
                self.assertFalse(fallback(command))
        for command in ("ls nope 2>/dev/null || echo none", "ls nope || true", "ls nope 2>/dev/null; true",
                        "ls nope 2>/dev/null | head -1", "ls nope 2>/dev/null\necho after",
                        "(git diff --stat 2>/dev/null || echo \"no data\") | head -40",
                        "a 2>/dev/null || b 2>/dev/null || printf none"):
            with self.subTest(command=command):
                self.assertTrue(fallback(command))
        p = self.skill(body=f"Status: !{BT}git status --short 2>/dev/null{BT}\n")
        found = [f for f in self.findings(p) if f.id == "SK005"]
        self.assertEqual(len(found), 1)
        self.assertIn("2>/dev/null", found[0].message)

    def test_escaped_or_glued_directive_is_not_a_directive(self):
        p = self.skill(body=f"Write \\!{BT}date{BT} or x!{BT}date{BT} here.\n")
        self.assertEqual(self.ids(p), [])

    def test_sk006(self):
        p = self.skill(body=f"!{BT}cat big.log 2>/dev/null || echo none{BT}\n")
        self.assertIn("SK006", self.ids(p))
        p = self.skill(body=f"!{BT}cat big.log 2>/dev/null | head -20 || echo none{BT}\n")
        self.assertNotIn("SK006", self.ids(p))

    def test_sk007(self):
        p = self.skill(body=f"API_KEY=sk-live-123\n!{BT}curl -s x 2>/dev/null || echo none{BT}\n")
        self.assertIn("SK007", self.ids(p))
        p = self.skill(body=f"!{BT}API_KEY=$API_KEY tool 2>/dev/null || echo none{BT}\n")
        self.assertNotIn("SK007", self.ids(p))

    def test_sk008(self):
        self.assertIn("SK008", self.ids(self.skill(body="x\n" * 501)))
        self.assertNotIn("SK008", self.ids(self.skill(body="x\n" * 500)))

    def test_sk009(self):
        p = self.skill(body="See [a](references/missing.md) and `scripts/gone.py` and @./nope.md\n"
                            "Ignored: [w](https://example.com) [m](mailto:a@b.c) [h](#anchor)\n"
                            f"{FENCE}\n[x](in/fence.md)\n{FENCE}\n")
        found = [f for f in self.findings(p) if f.id == "SK009"]
        self.assertEqual(len(found), 3)
        self.assertTrue(all(f.line == 4 for f in found))

    def test_sk009_link_target_with_a_space(self):
        # not a link to a markdown renderer either, so a mechanical rename that
        # wrote a space into a path must still be caught
        p = self.skill(body="See [r](../the old dir/references/r.md) and [t](a.md \"title\")\n")
        found = [f for f in self.findings(p) if f.id == "SK009"]
        self.assertEqual([f.message.split("'")[1] for f in found], ["../the old dir/references/r.md", "a.md"])
        write(self.tmp, "skills/s/a.md", "")
        p2 = self.skill(body="See [w](https://x.org/a b.html) and [t](a.md \"title\")\n")
        self.assertNotIn("SK009", self.ids(p2))

    def test_sk009_skill_dir_variable(self):
        p = self.skill(body=f"{FENCE}bash\npython3 ${{CLAUDE_SKILL_DIR}}/scripts/tool.py\n{FENCE}\n")
        self.assertIn("SK009", self.ids(p))
        write(self.tmp, "skills/s/scripts/tool.py", "")
        self.assertNotIn("SK009", self.ids(p))

    def test_sk009_sibling_skill_reference_in_prose(self):
        self.plugin()
        write(self.tmp, "skills/other/SKILL.md", "---\ndescription: o\n---\n")
        write(self.tmp, "skills/other/references/deep.md", "")
        p = self.skill(body="Read other's `references/deep.md` first.\n")
        self.assertNotIn("SK009", self.ids(p))

    def test_sk010(self):
        self.plugin()
        p = self.skill(body="Invoke Skill(missing) and Skill(demo:gone) and Skill(elsewhere:x) and Skill(s).\n")
        msgs = [f.message for f in self.findings(p) if f.id == "SK010"]
        self.assertEqual(len(msgs), 2)
        self.assertTrue(any("Skill(missing)" in m for m in msgs))
        self.assertTrue(any("Skill(demo:gone)" in m for m in msgs))

    def test_sk010_silent_without_a_skills_root(self):
        p = write(self.tmp, "loose/SKILL.md", "---\ndescription: d\n---\nSkill(missing)\n")
        self.assertNotIn("SK010", self.ids(p))

    def test_sk010_project_skills_root(self):
        write(self.tmp, ".claude/skills/a/SKILL.md", "---\ndescription: d\n---\nSkill(b) Skill(zzz)\n")
        write(self.tmp, ".claude/skills/b/SKILL.md", "---\ndescription: d\n---\n")
        found = [f.message for f in self.findings(os.path.join(self.tmp, ".claude/skills/a/SKILL.md"))]
        self.assertEqual(len(found), 1)
        self.assertIn("Skill(zzz)", found[0])

    def test_version_stamps_are_gone(self):
        # SK011 and SK014 went with the `stamp` subcommand: `claude-lint drift` checks staleness now
        self.assertEqual(self.ids(self.skill(body="Written for Claude Code v2.1.170.\n")), [])
        self.assertFalse({"SK011", "SK014"} & {r[0] for r in cl.RULES})
        self.assertNotIn("stamp", cl.COMMANDS)
        r = run("stamp", "2.1.170")
        self.assertEqual(r.returncode, 2)                    # read as a path that does not exist

    def test_sk012_placeholder_directive(self):
        p = self.skill(body=f"- {BT}{BT} !{BT}command{BT} {BT}{BT} inline injection\n")
        ids = self.ids(p)
        self.assertIn("SK012", ids)
        msg = [f.message for f in self.findings(p) if f.id == "SK012"][0]
        self.assertIn("executed or substituted at load, code span or not", msg)
        self.assertIn("references/ file, which is not preprocessed", msg)

    def test_sk012_documented_tokens(self):
        p = self.skill(body=f"- **{BT}$ARGUMENTS{BT}** - all arguments\n"
                            f"- **{BT}${{CLAUDE_SESSION_ID}}{BT}** - the session\n"
                            f"**{BT}${{CLAUDE_EFFORT}}{BT}** is the effort\n")
        found = [f for f in self.findings(p) if f.id == "SK012"]
        self.assertEqual([f.line for f in found], [4, 5, 6])
        self.assertTrue(all(f.severity == "warn" for f in found))

    def test_sk012_legitimate_use_is_quiet(self):
        p = self.skill(body=f"Fix issue $ARGUMENTS now. Log to {BT}${{CLAUDE_SESSION_ID}}.log{BT}.\n"
                            f"Run {BT}gh issue view $ARGUMENTS{BT} first. The issue: {BT}$ARGUMENTS{BT}\n"
                            f"{FENCE}\n- **{BT}$ARGUMENTS{BT}** in a fence\n{FENCE}\n")
        self.assertEqual(self.ids(p), [])

    def test_sk012_placeholder_alone_in_a_plain_code_span(self):
        # Observed on 2.1.295: "Use `$ARGUMENTS` to pass" loaded, with no arguments, as "Use `` to pass".
        for body in (f"Use {BT}$ARGUMENTS{BT} to receive everything the user typed.\n",
                     f"The first word is {BT}$ARGUMENTS[0]{BT} (zero-based).\n",
                     f"A skill sees {BT}$ARGUMENTS{BT} replaced before the model reads it.\n",
                     f"**Important:** use {BT}$ARGUMENTS{BT} verbatim.\n",
                     f"{BT}${{CLAUDE_EFFORT}}{BT} is the active effort level.\n"):
            with self.subTest(body=body):
                found = self.findings(self.skill(body=body))
                self.assertEqual([(f.id, f.severity, f.line) for f in found], [("SK012", "warn", 4)])
                self.assertIn("is described here but will be replaced", found[0].message)
        # the span holds more than the token, or the token is in a value position, or it is not in a span
        for body in (f"Run {BT}gh issue view $ARGUMENTS{BT} and read it.\n", "Fix issue $ARGUMENTS now.\n",
                     f"Issue: {BT}$ARGUMENTS{BT}\n", f"Review the pull request named in {BT}$ARGUMENTS{BT}.\n",
                     f"Print {BT}$1{BT} with awk, or {BT}$0{BT} for the whole line.\n",
                     f"{BT}{BT}$ARGUMENTS{BT}{BT} in a double-backtick span is another matter.\n",
                     f"This skill lives at {BT}${{CLAUDE_SKILL_DIR}}{BT}.\n"):
            with self.subTest(body=body):
                self.assertEqual(self.ids(self.skill(body=body)), [])

    def test_sk012_index_placeholder_alone_in_a_code_span(self):
        # `$0`/`$1` alone in a span: documentation when the line is about arguments
        for body in (f"The placeholder {BT}$1{BT} expands to the second argument.\n",
                     f"Positional arguments arrive as {BT}$0{BT}, {BT}$1{BT} and so on.\n",
                     f"{BT}$0{BT} is replaced by the first word the user typed.\n",
                     f"Like $ARGUMENTS, {BT}$2{BT} is substituted before the model reads the body.\n"):
            with self.subTest(body=body):
                found = self.findings(self.skill(body=body))
                self.assertEqual([(f.id, f.severity, f.line) for f in found], [("SK012", "warn", 4)])
                self.assertIn("is described here but will be replaced", found[0].message)
        # shell and awk, a value position, a longer span, and no span at all are uses
        for body in (f"Print {BT}$1{BT} with awk, or {BT}$0{BT} for the whole line.\n",
                     f"The first argument is {BT}$0{BT}.\n", f"Run {BT}gh pr view $0{BT} with the argument.\n",
                     "Review pull request $0 and then argument $1.\n",
                     f"In sed, {BT}$1{BT} is not a thing; use {BT}\\1{BT}.\n"):
            with self.subTest(body=body):
                self.assertEqual(self.ids(self.skill(body=body)), [])

    def test_sk012_is_not_a_second_sk005(self):
        # a real command with no fallback: SK005 alone
        p = self.skill(body=f"Status: !{BT}git status --short{BT}\n{FENCE}!\ngit log -3 --oneline\n{FENCE}\n")
        self.assertEqual(self.ids(p), ["SK005", "SK005"])
        # a placeholder: SK012 says what it is (SK005 still notes the missing fallback)
        for body in (f"Write !{BT}command{BT} to inject.\n", f"Write !{BT}<your-command> --flag{BT} to inject.\n",
                     f"Write {BT}{BT} !{BT}git status{BT} {BT}{BT} to inject.\n", f"{FENCE}!\n{FENCE}\n"):
            with self.subTest(body=body):
                found = [f for f in self.findings(self.skill(body=body)) if f.id == "SK012"]
                self.assertEqual(len(found), 1)
                self.assertIn("placeholder injection", found[0].message)
        # a placeholder with a fallback is still a placeholder, and now the only finding
        p = self.skill(body=f"Write !{BT}cmd 2>/dev/null || echo none{BT} to inject.\n")
        self.assertEqual(self.ids(p), ["SK012"])
        self.assertIn("SK005 alone", {r[0]: r[3] for r in cl.RULES}["SK012"])

    def test_disable_comment(self):
        p = self.skill(body=f"<!-- claude-lint-disable SK012, SK005 -->\n!{BT}command{BT}\n")
        self.assertEqual(self.ids(p), [])


# ---- SK015: at-sign file references ----------------------------------------
#
# OBSERVED on Claude Code 2.1.295, 2026-10-09: three probe skills in a throwaway
# plugin, loaded headless (`claude -p ... --plugin-dir <probe> --model haiku
# --allowedTools Skill`) from a working directory holding one marker file per
# row, each with its own random token; a row is "attached" when the model could
# quote that token after the skill loaded. Every row was run twice and agreed.
# Each row: (what it shows, the line(s) in the SKILL.md body, the marker file
# relative to the session's working directory - or None, attached?).
# "{CWD}" stands for that directory's absolute path, "{SKILL}" for the skill's.

AT_OBSERVED = [
    ("bare, mid-sentence", "See @a1.txt for details", "a1.txt", True),
    ("start of line", "@a2.txt", "a2.txt", True),
    ("trailing full stop", "Read @a3.txt.", "a3.txt", True),
    ("in parentheses", "Look (@a4.txt) here", "a4.txt", False),
    ("in double quotes", 'Look "@a5.txt" here', "a5.txt", False),
    ("glued after a colon", "see:@a6.txt here", "a6.txt", False),
    ("e-mail shape", "mail user@a7.txt here", "a7.txt", False),
    ("list item", "- @a8.txt", "a8.txt", True),
    ("blockquote", "> @a9.txt", "a9.txt", True),
    ("heading", "## @a10.txt", "a10.txt", True),
    ("bold", "Now **@a11.txt** here", "a11.txt", False),
    ("markdown link target", "A [link](@a12.txt) here", "a12.txt", False),
    ("HTML comment", "<!-- @a13.txt -->", "a13.txt", True),
    ("trailing comma", "Read @a14.txt, then stop", "a14.txt", True),
    ("quoted form with a space", 'Read @"a15 file.txt" now', "a15 file.txt", True),
    ("fenced block, alone on its line", f"{FENCE}\n@b1.txt\n{FENCE}", "b1.txt", True),
    ("fenced block, after a command", f"{FENCE}bash\ncat @b2.txt\n{FENCE}", "b2.txt", True),
    ("code span, directly after the backtick", "Inline `@b3.txt` here", "b3.txt", False),
    ("code span, after a word", "Inline `cat @b4.txt` here", "b4.txt", True),
    ("double-backtick span", "Inline ``@b5.txt`` here", "b5.txt", False),
    ("code span, after a space", "Inline ` @b6.txt` here", "b6.txt", True),
    ("decorator in a python fence, file of that name", f"{FENCE}python\n@dataclass\nclass A:\n    x: int\n{FENCE}",
     "dataclass", True),
    ("indented code block", "Para.\n\n    @b8.txt\n\nPara.", "b8.txt", True),
    ("tilde fence", "~~~\n@b9.txt\n~~~", "b9.txt", True),
    ("decorator with a call, file `app.route`", f"{FENCE}python\n@app.route('/x')\ndef f(): pass\n{FENCE}",
     "app.route", False),
    ("no extension", "See @README here", "README", True),
    ("dot-slash", "See @./c2.txt here", "c2.txt", True),
    ("subdirectory", "See @sub/c3.txt here", "sub/c3.txt", True),
    ("npm scope shape, file exists", "Install @scope/pkg here", "scope/pkg", True),
    ("npm scope shape, directory exists (its listing)", "Install @types/node here", "types/node/x.txt", True),
    ("absolute path", "See @{CWD}/c7.txt here", "c7.txt", True),
    ("exists only in the skill's directory", "See @references/c8.md here", None, False),
    ("${CLAUDE_SKILL_DIR} is substituted first", "See @{SKILL}/references/c11.md here", None, True),
    ("handle shape, file exists", "Thanks @octocat for this", "octocat", True),
    ("after a tab", "x\t@c13.txt", "c13.txt", True),
    ("glued after an open bracket", "See [@c14.txt] here", "c14.txt", False),
    # re-probed the same day, twice each, asking for every token visible after the skill loaded
    ("no extension, only README.md exists (the name is taken exactly)", "See @README here", "README.md", False),
    ("a name nothing has", "See @nonexistent-file.md here", "other-file.md", False),
    ("line range (lines 1-2 of 3 attached)", "See @d1.md#L1-2 here", "d1.md", True),
    ("single line (line 2 of 3 attached)", "See @d2.md#L2 here", "d2.md", True),
    ("line range, trailing full stop (lines 2-3 attached)", "See @d3.md#L2-3. Then stop", "d3.md", True),
    ("GitHub-style range (attached; lines 2-3 in two runs, the whole file in two)", "See @d4.md#L2-L3 here",
     "d4.md", True),
    ("another fragment (the whole file attached)", "See @d5.md#heading here", "d5.md", True),
    ("line range in a fenced block (line 1 attached)", f"{FENCE}\n@d6.md#L1\n{FENCE}", "d6.md", True),
    ("line range opening a code span", "Type `@d7.md#L1` to attach", "d7.md", False),
    ("directory name (its listing, file names only)", "See @docs here", "docs/x.txt", True),
    ("directory name, trailing slash (its listing)", "See @docs/ here", "docs/x.txt", True),
]
# Also observed, not a row because the file exists and still nothing is added:
# `@d.md#L9` on a three-line file attached nothing.
# One more observation that is not a row: a file present in both the working
# directory and the skill's directory under the same relative path attached the
# working directory's copy, never the skill's.


class AtReferenceTests(TempCase):
    def skill(self, body, rel="skills/s/SKILL.md"):
        return write(self.tmp, rel, f"---\ndescription: d\n---\n{body}")

    def sk015(self, path):
        return [f for f in self.findings(path) if f.id == "SK015"]

    def test_model_reproduces_every_observed_row(self):
        for what, body, marker, attached in AT_OBSERVED:
            with self.subTest(what=what), tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryDirectory() as sk:
                cwd, sk = os.path.realpath(cwd), os.path.realpath(sk)
                if marker:
                    write(cwd, marker, "x\n")
                write(sk, "references/c8.md", "x\n")
                write(sk, "references/c11.md", "x\n")
                text = body.replace("{CWD}", cwd).replace("{SKILL}", sk)
                tokens = [t for _, t, _ in cl.at_file_refs(text)]
                predicted = any(os.path.exists(os.path.join(cwd, t)) for t in tokens)
                self.assertEqual(predicted, attached, tokens)

    def test_contexts_and_lines(self):
        body = f"x\n{FENCE}\ncat @a.md\n{FENCE}\n`see @b.md` and @c.md and `@d.md`\n"
        self.assertEqual(cl.at_file_refs(body, 10), [(12, "a.md", "fence"), (14, "b.md", "span"), (14, "c.md", "prose")])
        self.assertEqual(cl.at_file_refs(f"!{BT}cat @x.md || echo none{BT}\n"), [])     # a directive is a command

    def test_plugin_skill_goes_by_the_shape_of_the_name(self):
        self.plugin()
        live = ["See @README.md here", f"{FENCE}\n@docs/guide.md\n{FENCE}", "- @./notes",
                "Run `cat @src/app.py` now", "<!-- @CLAUDE.md -->", 'Read @"my notes.txt" now', "@../x/y.json",
                "See @README.md#L1-2 here", "See @docs/guide.md#L40 here", "See @nonexistent-file.md here",
                f"{FENCE}\n@src/app.py#L10-20\n{FENCE}", "See @README.md#install here"]
        # nothing of these names exists where the linter can look, and it cannot see the
        # working directory of a plugin skill: a note that the reference is live, not a warning
        for body in live:
            with self.subTest(body=body):
                found = self.sk015(self.skill(body + "\n"))
                self.assertEqual([f.severity for f in found], ["info"])
                self.assertIn("attached if a file of this name exists in the session's working directory",
                              found[0].message)
        quiet = ["Mail user@example.com or me@host.md", "Install @scope/pkg and @types/node", "Thanks @octocat",
                 f"{FENCE}python\n@dataclass\n@functools.cache\n@pytest.mark.skip\n@app.route('/x.md')\n{FENCE}",
                 "Write `@README.md` to attach it", "Use ``@a.md`` or (@b.md) or \"@c.md\" or **@d.md**",
                 f'{FENCE}ts\nimport x from "@/lib/utils.ts"\n{FENCE}', "@media print and @import rules",
                 "Attach @$1 or @$ARGUMENTS or @${CLAUDE_SKILL_DIR}/references/a.md", "a @ b", "@", "@@x.md",
                 "See [@a.md] and x:@b.md", f"{FENCE}java\n@Override\n@Test\n{FENCE}", "@example.com @v1.2.3",
                 "See @README here", "Build with @Makefile or @Dockerfile", "See @LICENSE and @CHANGELOG",
                 "Type `@README.md#L1-2` to attach two lines", "Issue @octocat#L1 or @user#123"]
        for body in quiet:
            with self.subTest(body=body):
                self.assertEqual(self.sk015(self.skill(body + "\n")), [])

    def test_a_warning_needs_a_target_that_resolves(self):
        # Observed: `@nonexistent-file.md` attaches nothing, and `@README.md#L1-2` attaches README.md.
        self.plugin()
        p = self.skill("See @nonexistent-file.md here\nSee @README.md#L1-2 here\n")
        self.assertEqual([(f.severity, f.line) for f in self.sk015(p)], [("info", 4), ("info", 5)])
        write(self.tmp, "README.md", "a\nb\nc\n")           # at the plugin root: a plausible working directory
        found = self.sk015(p)
        self.assertEqual([(f.severity, f.line) for f in found], [("info", 4), ("warn", 5)])
        self.assertIn("`@README.md`", found[1].message)      # the range is not part of the name
        # a project skill's working directory is known: what does not exist there is not reported at all
        rel = ".claude/skills/s/SKILL.md"
        fenced = f"{FENCE}\n@nonexistent-file.md\n@README\n@README.md#L1-2\n{FENCE}\n"
        self.assertEqual([f.line for f in self.sk015(self.skill(fenced, rel))], [7])
        # and with no project or plugin above the skill there is nowhere to look
        with tempfile.TemporaryDirectory() as bare:
            lone = write(os.path.realpath(bare), "s/SKILL.md", "---\ndescription: d\n---\nSee @notes.md here\n")
            self.assertEqual([f.severity for f in self.sk015(lone)], ["info"])

    def test_an_unlikely_name_is_flagged_when_the_file_exists(self):
        self.plugin()
        p = self.skill("Thanks @octocat and @scope/pkg\n")
        self.assertEqual(self.sk015(p), [])
        write(self.tmp, "skills/s/octocat", "x\n")           # beside the skill
        write(self.tmp, "scope/pkg", "x\n")                  # at the plugin root
        self.assertEqual(len(self.sk015(p)), 2)

    def test_a_bare_well_known_name_needs_a_file_of_exactly_that_name(self):
        # Observed: `@README` attaches a file named README, and nothing when only README.md exists.
        self.plugin()
        p = self.skill("See @README here and @Makefile there, and @docs too\n")
        self.assertEqual(self.sk015(p), [])
        write(self.tmp, "README.md", "x\n")                  # not the same name
        self.assertEqual(self.sk015(p), [])
        write(self.tmp, "README", "x\n")                     # at the plugin root
        self.assertEqual([f.message.split("`")[1] for f in self.sk015(p)], ["@README"])
        write(self.tmp, "skills/s/Makefile", "x\n")          # beside the skill
        os.makedirs(os.path.join(self.tmp, "docs"))          # a directory: its listing is attached
        self.assertEqual(sorted(f.message.split("`")[1] for f in self.sk015(p)), ["@Makefile", "@README", "@docs"])
        # a personal skill has no root to look in: only beside the skill
        personal = os.path.join(self.tmp, "home", ".claude", "skills", "k", "SKILL.md")
        with mock.patch.dict(os.environ, {"HOME": os.path.join(self.tmp, "home")}):
            write(self.tmp, "home/.claude/skills/k/SKILL.md", "---\ndescription: d\n---\nSee @README and @LICENSE\n")
            self.assertEqual(self.sk015(personal), [])
            write(self.tmp, "home/.claude/skills/k/LICENSE", "x\n")
            self.assertEqual(len(self.sk015(personal)), 1)

    def test_a_line_range_suffix_is_part_of_the_reference(self):
        self.assertEqual(cl.at_file_refs("See @a.md#L1-2 and @b.md#L7. Then @c.md#top and @d#L2-L3\n"),
                         [(1, "a.md", "prose"), (1, "b.md", "prose"), (1, "c.md", "prose"), (1, "d", "prose")])
        self.assertEqual(cl.at_file_refs("@#L1 and @# and `@a.md#L1`\n"), [(1, "#L1", "prose")])
        rel = ".claude/skills/s/SKILL.md"
        write(self.tmp, "docs/style.md", "x\n")
        # a project skill: the file is there, so a range in a fenced example is attached like any other
        self.assertEqual(len(self.sk015(self.skill(f"{FENCE}\n@docs/style.md#L1-2\n{FENCE}\n", rel))), 1)
        self.assertEqual(self.sk015(self.skill("Follow @docs/style.md#L1-2 here\n", rel)), [])     # prose: the feature

    def test_message(self):
        self.plugin()
        write(self.tmp, "skills/s/references/a.md", "x\n")
        found = self.sk015(self.skill(f"x\n{FENCE}\n@references/a.md\n{FENCE}\n"))
        self.assertEqual([f.line for f in found], [6])
        m = found[0].message
        self.assertIn("is attached if a file of that name exists in the session's working directory when the "
                      "skill loads", m)
        self.assertNotIn("it is read from", m)               # nothing is read when nothing by that name is there
        for part in ("`@references/a.md`", "session's working directory", "when the skill loads", "fenced block",
                     "directory's listing", "`#L<n>-<m>` suffix",
                     "directly inside an inline code span", "`` `@references/a.md` ``", "${CLAUDE_SKILL_DIR}",
                     "explicit Read instruction", "where this file is"):
            self.assertIn(part, m)
        write(self.tmp, "x.md", "x\n")
        found = self.sk015(self.skill("Run `cat @x.md` now\n@x.md again\n"))
        self.assertEqual([f.line for f in found], [4, 5])           # the same token on two lines: both
        self.assertIn("directly after the backtick", found[0].message)
        self.assertNotIn("backtick", found[1].message.split("Put it")[0])

    def test_project_skill_knows_its_working_directory(self):
        rel = ".claude/skills/s/SKILL.md"
        write(self.tmp, "docs/style.md", "x\n")
        # prose that resolves from the project root is the documented feature, working
        self.assertEqual(self.sk015(self.skill("Follow @docs/style.md here\n", rel)), [])
        # the same reference where it reads as an example is attached all the same
        self.assertEqual(len(self.sk015(self.skill(f"{FENCE}\n@docs/style.md\n{FENCE}\n", rel))), 1)
        self.assertEqual(len(self.sk015(self.skill("Type `review @docs/style.md` to see\n", rel))), 1)
        # nothing by that name: nothing is attached, nothing is said
        self.assertEqual(self.sk015(self.skill(f"See @README.md\n{FENCE}\n@nope.md\n{FENCE}\n", rel)), [])
        # a bundled file: the reference looks in the project root, not beside the skill
        write(self.tmp, ".claude/skills/s/references/a.md", "x\n")
        found = self.sk015(self.skill("Read @references/a.md first\n", rel))
        self.assertEqual(len(found), 1)
        self.assertIn("where this file is", found[0].message)
        # commands are skills too
        cmd = write(self.tmp, ".claude/commands/c.md", f"Review @docs/style.md\n{FENCE}\n@docs/style.md\n{FENCE}\n")
        self.assertEqual([f.line for f in self.sk015(cmd)], [3])

    def test_disable_comment_and_severity(self):
        self.plugin()
        p = self.skill("See @README.md here\n<!-- claude-lint-disable SK015 -->\n")
        self.assertEqual(self.sk015(p), [])
        self.assertEqual(cl.RULE_SEVERITY["SK015"], "warn")

    def test_this_plugins_own_skills_have_no_live_references(self):
        for base, _, files in os.walk(os.path.join(ROOT, "skills")):
            if "SKILL.md" in files:
                self.assertEqual(self.sk015(os.path.join(base, "SKILL.md")), [])


# ---- rules ------------------------------------------------------------------

GOOD_RULE = f"""\
---
paths:
  - "**/*.py"
---
# Python rule

Applies when editing Python. Procedure: Skill(py).

- No skill grammar ({BT}{BT} !{BT}cmd{BT} {BT}{BT}, {BT}$ARGUMENTS{BT}, {BT}${{VAR}}{BT}) - it is literal here.
"""


class RuleTests(TempCase):
    def rule(self, content, rel=".claude/rules/r.md"):
        return write(self.tmp, rel, content)

    def test_clean_rule(self):
        write(self.tmp, ".claude/skills/py/SKILL.md", "---\ndescription: d\n---\n")
        self.assertEqual(self.ids(self.rule(GOOD_RULE)), [])

    def test_plugin_rule_is_linted(self):
        self.plugin()
        p = self.rule("# T\n\nNo opener.\n", rel="rules/r.md")
        self.assertEqual(sorted(self.ids(p)), ["RU004", "RU005"])

    def test_ru001(self):
        p = self.rule(GOOD_RULE.replace("Skill(py)", "x") + "- line\n" * 200)
        self.assertIn("RU001", self.ids(p))

    def test_ru002(self):
        p = self.rule(GOOD_RULE.replace("Skill(py)", "x")
                      + f"Run !{BT}date{BT} with $ARGUMENTS in ${{CLAUDE_SKILL_DIR}}.\n\n{FENCE}!\ndate\n{FENCE}\n")
        found = [f for f in self.findings(p) if f.id == "RU002"]
        self.assertEqual(len(found), 4)
        self.assertEqual(found[0].severity, "error")
        self.assertEqual(sorted({f.line for f in found}), [10, 12])

    def test_ru003(self):
        p = self.rule(GOOD_RULE.replace("Skill(py)", "x") + "1. do this\n2. then that\n")
        self.assertEqual(self.ids(p), ["RU003"])

    def test_ru004(self):
        p = self.rule('---\npaths: ["**/*"]\n---\n# T\n\nSome intro.\n')
        found = self.findings(p)
        self.assertEqual([(f.id, f.line) for f in found], [("RU004", 6)])

    def test_ru005_and_opt_out(self):
        self.assertEqual(self.ids(self.rule("# T\n\nApplies to everything.\n")), ["RU005"])
        p = self.rule("# T\n\nApplies to everything.\n<!-- claude-lint-disable RU005 -->\n")
        self.assertEqual(self.ids(p), [])

    def test_ru006(self):
        body = "# T\n\nApplies when x.\n"
        for front in ("paths:\n  - **/*.md\n", "paths: [*.md]\n", "paths:\n", "paths: true\n",
                      'paths:\n  - "src/{a,b"\n', "paths:\n  glob: x\n"):
            with self.subTest(front=front):
                self.assertIn("RU006", self.ids(self.rule(f"---\n{front}---\n{body}")))
        for front in ('paths:\n  - "**/*.md"\n', "paths: [src/a.py, 'b/*.py']\n", 'paths: "src/**"\n',
                      "paths: src/api/**/*.ts\n", "paths: src/**, lib/**\n", "paths:\n  - src/**/*.py\n",
                      "paths: [\n  src/a.py,\n  lib/b.py\n]\n", 'paths: "{src,lib}/**"\n', "paths: [abc]\n"):
            with self.subTest(front=front):
                self.assertEqual(self.ids(self.rule(f"---\n{front}---\n{body}")), [])

    def test_ru006_says_to_quote_what_yaml_cannot_read_plain(self):
        body = "# T\n\nApplies when x.\n"
        for front, char in (("paths: *.md\n", "*"), ("paths: **/*.ts\n", "*"), ("paths: [ab]*.ts\n", "["),
                            ("paths: {src,lib}/**\n", "{"), ("paths: !negated/**\n", "!"),
                            ("paths: &anchor/**\n", "&"), ("paths:\n  - [a-z]*.md\n", "["),
                            ("paths:\n  - {a,b}/**\n", "{"), ("paths: [src/**, *.md]\n", "*")):
            with self.subTest(front=front):
                found = self.findings(self.rule(f"---\n{front}---\n{body}"))
                self.assertEqual([(f.id, f.severity, f.line) for f in found], [("RU006", "error", 2)])
                self.assertIn("must be quoted", found[0].message)
                self.assertIn(f"'{char}'", found[0].message)

    def test_ru006_listing_text_matches_behaviour(self):
        check = {r[0]: r[3] for r in cl.RULES}["RU006"]
        self.assertIn("quoted or plain", check)
        for char in "*[{!&":
            self.assertIn(f"`{char}`", check)

    def test_sk010_applies_to_rules(self):
        write(self.tmp, ".claude/skills/py/SKILL.md", "---\ndescription: d\n---\n")
        p = self.rule(GOOD_RULE.replace("Skill(py)", "Skill(nope)"))
        self.assertEqual(self.ids(p), ["SK010"])


# ---- agents -----------------------------------------------------------------

class AgentTests(TempCase):
    def agent(self, front, body="You review code.\n", rel=".claude/agents/a.md"):
        return write(self.tmp, rel, f"---\n{front}---\n{body}")

    def test_clean_agent(self):
        write(self.tmp, ".claude/skills/k/SKILL.md", "---\ndescription: d\n---\n")
        p = self.agent("name: rev\ndescription: Reviews.\nbackground: true\nmaxTurns: 20\nskills:\n  - k\n",
                       f"Use {BT}$ARGUMENTS{BT} never.\n\n{FENCE}bash\necho ${{HOME}}\n{FENCE}\n")
        self.assertEqual(self.ids(p), [])

    def test_ag001(self):
        self.assertEqual(self.ids(self.agent("description: d\n")), ["AG001"])
        self.assertEqual(self.ids(self.agent("name: rev\n")), ["AG001"])
        self.assertEqual(self.ids(self.agent("name: Rev_1\ndescription: d\n")), ["AG001"])
        self.assertEqual(self.ids(write(self.tmp, ".claude/agents/n.md", "no frontmatter\n")), ["AG001", "AG001"])

    def test_ag002(self):
        p = self.agent("name: a\ndescription: d\n", f"Now: !{BT}date{BT}\nArgs: $ARGUMENTS\n")
        found = [f for f in self.findings(p) if f.id == "AG002"]
        self.assertEqual([f.line for f in found], [5, 6])

    def test_ag003(self):
        self.assertEqual(self.ids(self.agent("name: a\ndescription: d\nbackground: true\n")), ["AG003"])
        self.assertEqual(self.ids(self.agent("name: a\ndescription: d\nbackground: false\n")), [])
        self.assertEqual(self.ids(self.agent("name: a\ndescription: d\n")), [])

    def test_ag004(self):
        self.plugin()
        write(self.tmp, "skills/ok/SKILL.md", "---\ndescription: d\n---\n")
        write(self.tmp, "skills/manual/SKILL.md", "---\ndescription: d\ndisable-model-invocation: true\n---\n")
        p = self.agent("name: a\ndescription: d\nskills: [ok, demo:ok, gone, manual, other:x]\n", rel="agents/a.md")
        found = [f for f in self.findings(p) if f.id == "AG004"]
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0].line, 4)
        self.assertTrue(any("'gone'" in f.message for f in found))
        self.assertTrue(any("'manual'" in f.message for f in found))

    def test_ag002_plugin_agent_bodies_expand_three_variables(self):
        # Documented (plugin reference, "Skill, command, and agent content"); a probe showed real paths in a
        # plugin agent's body and the literals in a project agent's.
        body = ('Run python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" --all . and keep state in\n'
                "${CLAUDE_PLUGIN_DATA}/x under ${CLAUDE_PROJECT_DIR}.\n")
        project = self.agent("name: a\ndescription: d\n", body)
        found = [f for f in self.findings(project) if f.id == "AG002"]
        self.assertEqual([f.line for f in found], [5, 6, 6])
        self.assertTrue(all("only in a plugin-distributed agent" in f.message for f in found))
        self.plugin()
        plugin = self.agent("name: a\ndescription: d\n", body, rel="agents/a.md")
        self.assertEqual(self.ids(plugin), [])
        # everything else is still literal text there
        other = self.agent("name: a\ndescription: d\n",
                           f"${{CLAUDE_SKILL_DIR}} $ARGUMENTS ${{HOME}} !{BT}date{BT} ${{CLAUDE_SESSION_ID}}\n",
                           rel="agents/b.md")
        found = [f for f in self.findings(other) if f.id == "AG002"]
        self.assertEqual(len(found), 5)
        self.assertTrue(all("${CLAUDE_PLUGIN_ROOT}" in f.message for f in found))    # says what is expanded

    def test_ag005_only_for_plugin_agents(self):
        front = ("name: a\ndescription: d\npermissionMode: plan\nhooks:\n  Stop:\n    - hooks: []\n"
                 "mcpServers:\n  x:\n    command: y\ninitialPrompt: go\n")
        self.assertEqual(self.ids(self.agent(front)), [])
        self.plugin()
        found = self.findings(self.agent(front, rel="agents/a.md"))
        self.assertEqual([f.id for f in found], ["AG005"] * 4)
        self.assertEqual(sorted(f.message.split("`")[1] for f in found),
                         ["hooks", "initialPrompt", "mcpServers", "permissionMode"])
        for field in ("hooks", "mcpServers", "permissionMode", "initialPrompt"):
            self.assertIn(field, {r[0]: r[3] for r in cl.RULES}["AG005"])

    def test_ag006_permission_specifier_in_tools(self):
        # Observed on 2.1.295: a specifier in an agent's `tools` grants the whole tool and pre-approves nothing.
        def found(tools):
            return [f for f in self.findings(self.agent(f"name: a\ndescription: d\ntools: {tools}\n")) if f.id == "AG006"]
        one = found("Read, Grep, Bash(claude-lint *)")
        self.assertEqual([(f.severity, f.line) for f in one], [("warn", 4)])
        for part in ("`Bash(claude-lint *)`", "does not restrict Bash", "PreToolUse", "pre-approves nothing"):
            self.assertIn(part, one[0].message)
        self.assertEqual(len(found("Bash(git log *), Read(src/**), mcp__srv__tool")), 2)
        self.assertEqual(len(found('["Read", "Bash(npm run *)"]')), 1)
        self.assertEqual(len(found("\n  - Read\n  - Edit(docs/**)\n  - Bash")), 1)
        self.assertEqual(len(found('Bash(python3 "x y.py" *)')), 1)
        for fine in ("Read, Grep, Glob, Bash", "Agent(worker, researcher), Read", "Task(worker)", "Agent", "",
                     "mcp__github__get_issue, Bash", "[Read, Agent(worker)]"):
            self.assertEqual(found(fine), [], fine)
        # the body is not this rule's business
        p = self.agent("name: a\ndescription: d\ntools: Bash\n", "Never Bash(rm *).\n")
        self.assertEqual(self.ids(p), [])

    def test_ag006_permission_specifier_in_disallowed_tools(self):
        # Documented (sub-agents, "Available tools"): "A `disallowedTools` entry with a specifier, such as
        # `Bash(git push *)`, still removes the whole tool from the subagent, not only the matching commands."
        def found(value):
            p = self.agent(f"name: a\ndescription: d\ntools: Read, Bash\ndisallowedTools: {value}\n")
            return [f for f in self.findings(p) if f.id == "AG006"]
        one = found("Bash(git push *)")
        self.assertEqual([(f.severity, f.line) for f in one], [("warn", 5)])
        for part in ("`Bash(git push *)` in `disallowedTools`", "removes ALL of Bash", "not only the calls that match",
                     "still removes the whole tool from the subagent, not only the matching commands",
                     "PreToolUse", "write `Bash` alone"):
            self.assertIn(part, one[0].message)
        self.assertNotIn("grants the whole tool", one[0].message)       # that is the `tools` wording
        self.assertEqual(len(found("Write, Edit(docs/**), Bash(rm *)")), 2)
        self.assertEqual(len(found("\n  - Write\n  - Bash(git push *)")), 1)
        self.assertEqual(len(found('["Bash(git push *)"]')), 1)
        for fine in ("Write, Edit", "Bash", "mcp__github, mcp__*", "Agent(worker)", ""):
            self.assertEqual(found(fine), [], fine)
        both = self.agent("name: a\ndescription: d\ntools: Bash(git log *)\ndisallowedTools: Bash(git push *)\n")
        self.assertEqual([(f.id, f.line) for f in self.findings(both)], [("AG006", 4), ("AG006", 5)])
        self.assertIn("disallowedTools", {r[0]: r[3] for r in cl.RULES}["AG006"])


# ---- memory -----------------------------------------------------------------

class MemoryTests(TempCase):
    def test_clean(self):
        write(self.tmp, "docs/a.md", "plain\n")
        p = write(self.tmp, "CLAUDE.md", "# Project\n\n- Use 2-space indentation.\n- See @docs/a.md\n"
                                         "- Install `@scope/pkg` and ping @someone or @anthropic-ai/sdk.\n"
                                         "- Personal: @~/.claude/mine.md\n")
        self.assertEqual(self.ids(p), [])

    def test_cm001(self):
        self.assertEqual(self.ids(write(self.tmp, "CLAUDE.md", "- x\n" * 201)), ["CM001"])
        self.assertEqual(self.ids(write(self.tmp, "CLAUDE.md", "- x\n" * 200)), [])

    def test_cm002_missing(self):
        p = write(self.tmp, "CLAUDE.local.md", "intro\n\nSee @docs/missing.md and @./also-missing\n")
        found = self.findings(p)
        self.assertEqual([(f.id, f.line, f.severity) for f in found], [("CM002", 3, "error")] * 2)

    def chain(self, n):
        for i in range(1, n + 1):
            nxt = f"@c{i + 1}.md\n" if i < n else "end\n"
            write(self.tmp, f"c{i}.md", nxt)
        return write(self.tmp, "CLAUDE.md", "@c1.md\n")

    def test_cm002_depth(self):
        self.assertEqual(self.ids(self.chain(cl.IMPORT_MAX_HOPS)), [])
        found = self.findings(self.chain(cl.IMPORT_MAX_HOPS + 1))
        self.assertEqual([f.id for f in found], ["CM002"])
        self.assertIn("deeper than 4 hops", found[0].message)

    def test_cm002_cycle_terminates(self):
        write(self.tmp, "a.md", "@CLAUDE.md\n")
        self.assertEqual(self.ids(write(self.tmp, "CLAUDE.md", "@a.md\n")), [])

    def test_cm003(self):
        self.assertEqual(self.ids(write(self.tmp, "CLAUDE.md", "1. build\n2. test\n")), ["CM003"])
        self.assertEqual(self.ids(write(self.tmp, "CLAUDE.md", f"{FENCE}\n1. in a fence\n{FENCE}\n")), [])


    def test_agents_md_is_memory_without_cm003(self):
        steps = "1. build\n2. test\n"
        self.assertEqual(self.ids(write(self.tmp, "AGENTS.md", steps)), [])
        self.assertEqual(self.ids(write(self.tmp, ".claude/AGENTS.md", steps)), [])
        self.assertEqual(self.ids(write(self.tmp, "AGENTS.md", "- x\n" * 201)), ["CM001"])
        self.assertEqual(self.ids(write(self.tmp, "sub/CLAUDE.md", steps)), ["CM003"])
        found = self.findings(write(self.tmp, "AGENTS.md", "See @docs/missing.md\n"))
        self.assertEqual([(f.id, f.severity) for f in found], [("CM002", "error")])
        write(self.tmp, "docs/a.md", "plain\n")
        self.assertEqual(self.ids(write(self.tmp, "AGENTS.md", "See @docs/a.md\n")), [])
        self.assertIn("AGENTS.md", {r[0]: r[3] for r in cl.RULES}["CM003"])

    def test_claude_md_importing_agents_md(self):
        write(self.tmp, "AGENTS.md", "1. a step other tools want\n@missing-from-agents.md\n")
        found = self.findings(write(self.tmp, "CLAUDE.md", "@AGENTS.md\n"))
        self.assertEqual([f.id for f in found], ["CM002"])
        self.assertIn("imported via", found[0].message)


# What reading a project's AGENTS.md was OBSERVED to depend on - Claude Code
# 2.1.295, 2026-10-09. Each probe was a throwaway project whose AGENTS.md held
# a random passphrase, started headless (`claude -p "what is the project
# passphrase" --model haiku`) from the project directory; the AGENTS.md was
# "read" when the reply gave the passphrase. Two or three runs per row, every
# run of a row agreeing. Each row: (what it shows, the CLAUDE.md - or None for
# no CLAUDE.md, other files, was the AGENTS.md read?).
PRE = "# Project\n\nUse tabs.\n\n"
RULE_PRE = "# R\n\n"

IMPORT_OBSERVED = [
    ("no CLAUDE.md at all", None, {}, True),
    ("a CLAUDE.md with no import", PRE, {}, False),
    ("line start", PRE + "@AGENTS.md\n", {}, True),
    ("mid-sentence, no punctuation after", PRE + "See @AGENTS.md for the rest\n", {}, True),
    ("trailing full stop (3 runs)", PRE + "See @AGENTS.md.\n", {}, False),
    ("HTML comment (3 runs)", PRE + "<!-- @AGENTS.md -->\n", {}, False),
    ("list item", PRE + "- @AGENTS.md\n", {}, True),
    ("code span", PRE + "Use `@AGENTS.md` here\n", {}, False),
    ("trailing comma", PRE + "See @AGENTS.md, then stop\n", {}, False),
    ("in parentheses", PRE + "(see @AGENTS.md)\n", {}, False),
    ("fenced block", PRE + f"{FENCE}\n@AGENTS.md\n{FENCE}\n", {}, False),
    ("blockquote", PRE + "> @AGENTS.md\n", {}, True),
    ("heading", PRE + "## @AGENTS.md\n", {}, True),
    ("dot-slash, trailing full stop", PRE + "See @./AGENTS.md.\n", {}, False),
    ("multi-line HTML comment", PRE + "<!--\n@AGENTS.md\n-->\n", {}, False),
    ("HTML comment inside a sentence", PRE + "Text <!-- @AGENTS.md --> text\n", {}, False),
    ("trailing colon", PRE + "See @AGENTS.md: it has more\n", {}, False),
    ("indented code block", PRE + "Para.\n\n    @AGENTS.md\n\nPara.\n", {}, False),
    ("trailing semicolon", PRE + "See @AGENTS.md; more\n", {}, False),
    ("bold", PRE + "**@AGENTS.md**\n", {}, True),
    ("italic", PRE + "See *@AGENTS.md* here\n", {}, True),
    ("#fragment", PRE + "@AGENTS.md#intro\n", {}, True),
    ("link text", PRE + "See [@AGENTS.md](https://example.test/x) here\n", {}, True),
    ("double quotes", PRE + 'See "@AGENTS.md" here\n', {}, False),
    ("table cell", PRE + "| file |\n| --- |\n| @AGENTS.md |\n", {}, True),
    ("nested list item", PRE + "- outer\n  - @AGENTS.md\n", {}, True),
    ("numbered list item", PRE + "1. @AGENTS.md\n", {}, True),
    ("after a tab", PRE + "x\t@AGENTS.md\n", {}, True),
    ("end of line, sentence continues on the next", PRE + "Read @AGENTS.md\nthen stop.\n", {}, True),
    # a CLAUDE.md with nothing in it is no CLAUDE.md
    ("CLAUDE.md empty, 0 bytes (4 runs)", "", {}, True),
    ("CLAUDE.md whitespace only (3 runs)", "\n  \n\n", {}, True),
    ("CLAUDE.md that is only an HTML comment", "<!-- nothing here -->\n", {}, True),
    ("empty CLAUDE.md and empty CLAUDE.local.md", "", {"CLAUDE.local.md": ""}, True),
    ("only an empty CLAUDE.local.md (3 runs)", None, {"CLAUDE.local.md": ""}, True),
    ("only an empty .claude/CLAUDE.md (3 runs)", None, {".claude/CLAUDE.md": ""}, True),
    ("only a non-empty CLAUDE.local.md, no import", None, {"CLAUDE.local.md": PRE}, False),
    ("only a non-empty .claude/CLAUDE.md, no import", None, {".claude/CLAUDE.md": PRE}, False),
    # rules expand imports, relative to the rule file
    ("rule imports @../../AGENTS.md", PRE, {".claude/rules/r.md": RULE_PRE + "@../../AGENTS.md\n"}, True),
    ("rule imports @AGENTS.md (looked for beside the rule)", PRE, {".claude/rules/r.md": RULE_PRE + "@AGENTS.md\n"},
     False),
    ("rule in a subdirectory imports @../../../AGENTS.md", PRE,
     {".claude/rules/sub/r.md": RULE_PRE + "@../../../AGENTS.md\n"}, True),
    ("path-scoped rule imports @../../AGENTS.md", PRE,
     {".claude/rules/r.md": '---\npaths: "src/**/*.ts"\n---\n' + RULE_PRE + "@../../AGENTS.md\n"}, True),
    ("no CLAUDE.md, a rule that does not import (3 runs)", None, {".claude/rules/r.md": RULE_PRE + "Use tabs.\n"},
     True),
]


class AgentsMdIsReadTests(TempCase):
    """CM004. Documented: "By default, Claude reads AGENTS.md only when you have
    no CLAUDE.md in your working directory or above it"."""

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.tmp, ".git"))          # the repo root: nothing above it is looked at

    def cm004(self, rel="AGENTS.md"):
        return [f for f in self.findings(os.path.join(self.tmp, rel)) if f.id == "CM004"]

    def test_alone_is_read(self):
        write(self.tmp, "AGENTS.md", "- x\n")
        self.assertEqual(self.cm004(), [])

    def test_model_reproduces_every_observed_row(self):
        for what, claude_md, extra, read in IMPORT_OBSERVED:
            with self.subTest(what=what), tempfile.TemporaryDirectory() as proj:
                proj = os.path.realpath(proj)
                os.makedirs(os.path.join(proj, ".git"))
                agents = os.path.join(proj, "AGENTS.md")
                files = dict(extra, **({} if claude_md is None else {"CLAUDE.md": claude_md}))
                for rel, text in dict(files, **{"AGENTS.md": "# Agents\n\nThe passphrase is x.\n"}).items():
                    path = os.path.join(proj, rel)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(text)                        # as probed: no dedent
                flagged = any(f.id == "CM004" for f in self.findings(agents))
                self.assertEqual(not flagged, read)

    def test_an_import_from_a_rule_file_counts(self):
        write(self.tmp, "AGENTS.md", "- x\n")
        write(self.tmp, "CLAUDE.md", "# no import\n")
        rule = write(self.tmp, ".claude/rules/shared.md", "# Shared\n\nApplies to everything.\n\n@AGENTS.md\n")
        self.assertEqual(len(self.cm004()), 1)               # resolves beside the rule, where there is none
        with open(rule, "w", encoding="utf-8") as f:
            f.write("# Shared\n\nApplies to everything.\n\n@../../AGENTS.md\n")
        self.assertEqual(self.cm004(), [])
        self.assertIn(".claude/rules/", {r[0]: r[3] for r in cl.RULES}["CM004"])

    def test_an_empty_claude_md_does_not_shadow_it(self):
        write(self.tmp, "AGENTS.md", "- x\n")
        path = os.path.join(self.tmp, "CLAUDE.md")
        for text, shadows in (("", False), ("  \n\t\n", False), ("<!-- later -->\n", False), ("x\n", True)):
            with self.subTest(text=text):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.assertEqual(len(self.cm004()), int(shadows))

    def test_a_comment_or_trailing_punctuation_is_not_an_import(self):
        # Observed on 2.1.295 in a CLAUDE.md, 3 runs of 3 each: neither imported the file.
        write(self.tmp, "AGENTS.md", "- x\n")
        for text in ("# P\n\n<!-- @AGENTS.md -->\n", "# P\n\nSee @AGENTS.md.\n", "# P\n\n<!--\n@AGENTS.md\n-->\n"):
            with self.subTest(text=text):
                claude_md = write(self.tmp, "CLAUDE.md", text)
                self.assertEqual(len(self.cm004()), 1)
        found = [f for f in self.findings(claude_md) if f.id == "CM002"]
        self.assertEqual(found, [])                          # inside a comment nothing was attempted
        found = [f for f in self.findings(write(self.tmp, "CLAUDE.md", "# P\n\nSee @AGENTS.md.\n")) if f.id == "CM002"]
        self.assertEqual(len(found), 1)                      # the silent miss is said out loud
        self.assertIn("straight after the path", found[0].message)

    def test_claude_md_that_imports_it_is_quiet(self):
        write(self.tmp, "AGENTS.md", "- x\n")
        for text in ("@AGENTS.md\n", "@./AGENTS.md\n", "# Project\n\nSee @AGENTS.md for the rest.\n",
                     "@docs/../AGENTS.md\n", f"@{self.tmp}/AGENTS.md\n"):
            with self.subTest(text=text):
                write(self.tmp, "docs/x.md", "")
                write(self.tmp, "CLAUDE.md", text)
                self.assertEqual(self.cm004(), [])

    def test_claude_md_without_the_import(self):
        write(self.tmp, "AGENTS.md", "- x\n")
        for text in ("# Project\n", "Mentions `@AGENTS.md` in a span only.\n", f"{FENCE}\n@AGENTS.md\n{FENCE}\n",
                     "@OTHER.md\n", "See AGENTS.md.\n"):
            with self.subTest(text=text):
                write(self.tmp, "OTHER.md", "")
                write(self.tmp, "CLAUDE.md", text)
                found = self.cm004()
                self.assertEqual([(f.severity, f.line) for f in found], [("warn", 1)])
                for part in ("is not read", "CLAUDE.md", "`@AGENTS.md`",
                             "unless the instruction-files setting is `claude-md-and-agents-md`"):
                    self.assertIn(part, found[0].message)

    def test_each_place_a_claude_md_can_sit(self):
        write(self.tmp, "AGENTS.md", "- x\n")
        for place in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"):
            with self.subTest(place=place):
                path = write(self.tmp, place, "# no import\n")
                self.assertEqual(len(self.cm004()), 1)
                write(self.tmp, place, "@AGENTS.md\n" if "/" not in place else "@../AGENTS.md\n")
                self.assertEqual(self.cm004(), [])
                os.remove(path)

    def test_any_one_importer_is_enough(self):
        write(self.tmp, "AGENTS.md", "- x\n")
        write(self.tmp, "CLAUDE.md", "# no import\n")
        write(self.tmp, "CLAUDE.local.md", "@AGENTS.md\n")
        self.assertEqual(self.cm004(), [])

    def test_import_through_a_chain(self):
        write(self.tmp, "AGENTS.md", "- x\n")
        write(self.tmp, "CLAUDE.md", "@docs/shared.md\n")
        write(self.tmp, "docs/shared.md", "@../AGENTS.md\n")
        self.assertEqual(self.cm004(), [])
        write(self.tmp, "docs/shared.md", "@loop.md\n")
        write(self.tmp, "docs/loop.md", "@shared.md\n")           # a cycle that never reaches it
        self.assertEqual(len(self.cm004()), 1)

    def test_symlink_is_quiet(self):
        write(self.tmp, "AGENTS.md", "- x\n")
        os.symlink("AGENTS.md", os.path.join(self.tmp, "CLAUDE.md"))
        self.assertEqual(self.cm004(), [])

    def test_nested_agents_md_looks_upward_to_the_repo_root(self):
        write(self.tmp, "pkg/api/AGENTS.md", "- x\n")
        self.assertEqual(self.cm004("pkg/api/AGENTS.md"), [])
        write(self.tmp, "CLAUDE.md", "# root, no import\n")
        found = self.cm004("pkg/api/AGENTS.md")
        self.assertEqual(len(found), 1)
        self.assertIn("`@pkg/api/AGENTS.md`", found[0].message)
        write(self.tmp, "CLAUDE.md", "@pkg/api/AGENTS.md\n")
        self.assertEqual(self.cm004("pkg/api/AGENTS.md"), [])
        write(self.tmp, "CLAUDE.md", "@AGENTS.md\n")               # imports a different (missing) AGENTS.md
        self.assertEqual(len(self.cm004("pkg/api/AGENTS.md")), 1)

    def test_nothing_above_the_repo_root_counts(self):
        write(self.tmp, "CLAUDE.md", "# outside the repo\n")
        os.makedirs(os.path.join(self.tmp, "repo", ".git"))
        write(self.tmp, "repo/AGENTS.md", "- x\n")
        self.assertEqual(self.cm004("repo/AGENTS.md"), [])
        os.rmdir(os.path.join(self.tmp, "repo", ".git"))
        self.assertEqual(len(self.cm004("repo/AGENTS.md")), 1)

    def test_only_agents_md_is_checked_and_it_can_be_disabled(self):
        write(self.tmp, "AGENTS.md", "- x\n<!-- claude-lint-disable CM004 -->\n")
        p = write(self.tmp, "CLAUDE.md", "# no import\n")
        self.assertEqual(self.cm004(), [])
        self.assertEqual(self.ids(p), [])


# ---- hook configs -----------------------------------------------------------

GOOD_HOOKS = {"hooks": {"PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "true"}]}]}}
BAD_HOOKS = {"hooks": {"PostToolUse": [{"matcher": "Write", "hooks": []}],
                       "Stop": [{"matcher": "x", "hooks": [{"type": "command", "command": "true"}]}]}}


class HookConfigTests(TempCase):
    def test_clean(self):
        p = write(self.tmp, ".claude/settings.json", json.dumps(GOOD_HOOKS))
        self.assertEqual(self.ids(p), [])

    def test_errors_and_warnings_map_to_hk001(self):
        p = write(self.tmp, ".claude/settings.local.json", json.dumps(BAD_HOOKS))
        found = self.findings(p)
        self.assertTrue(found)
        self.assertEqual({f.id for f in found}, {"HK001"})
        self.assertIn("error", {f.severity for f in found})
        self.assertIn("warn", {f.severity for f in found})

    def test_settings_without_hooks_key_is_skipped(self):
        p = write(self.tmp, ".claude/settings.json", json.dumps({"permissions": {"allow": []}}))
        self.assertEqual(self.ids(p), [])

    def test_plugin_hooks_json(self):
        self.plugin()
        p = write(self.tmp, "hooks/hooks.json", json.dumps(dict(GOOD_HOOKS, description="d")))
        self.assertNotIn("error", {f.severity for f in self.findings(p)})
        p = write(self.tmp, "hooks/hooks.json", "{not json")
        self.assertIn(("HK001", "error"), {(f.id, f.severity) for f in self.findings(p)})

    def test_plugin_flag_retry_when_hooktool_rejects_it(self):
        self.plugin()
        old = write(self.tmp, "old/hooktool.py", """\
            import argparse, json, sys
            p = argparse.ArgumentParser()
            p.add_argument("cmd"); p.add_argument("path"); p.add_argument("--json", action="store_true")
            p.parse_args()
            print(json.dumps({"valid": False, "errors": ["from old hooktool"], "warnings": []}))
            sys.exit(1)
            """)
        p = write(self.tmp, "hooks/hooks.json", json.dumps(GOOD_HOOKS))
        with mock.patch.object(cl, "find_hooktool", return_value=old):
            found = self.findings(p)
        self.assertEqual([(f.severity, f.message) for f in found], [("error", "from old hooktool")])

    def test_missing_hooktool_is_one_info(self):
        p = write(self.tmp, ".claude/settings.json", json.dumps(BAD_HOOKS))
        with mock.patch.object(cl, "find_hooktool", return_value=None):
            found = self.findings(p)
        self.assertEqual([(f.id, f.severity) for f in found], [("HK001", "info")])

    def test_real_hooktool_is_found(self):
        self.assertTrue(os.path.isfile(cl.find_hooktool() or ""))


# ---- plugin -----------------------------------------------------------------

class PluginTests(TempCase):
    def test_clean(self):
        self.plugin()
        write(self.tmp, "skills/a/SKILL.md", "---\ndescription: d\n---\n")
        write(self.tmp, "docs/guide.md", "g\n")
        write(self.tmp, "README.md", "[g](docs/guide.md#part) [w](https://x.y) [a](#here)\n")
        self.assertEqual(self.ids(os.path.join(self.tmp, ".claude-plugin/plugin.json")), [])

    def test_pl001(self):
        p = write(self.tmp, ".claude-plugin/plugin.json", "{oops")
        self.assertEqual(self.ids(p), ["PL001"])
        p = write(self.tmp, ".claude-plugin/plugin.json", json.dumps({"version": "1"}))
        self.assertEqual(self.ids(p), ["PL001"])

    def test_pl002(self):
        p = self.plugin()
        os.makedirs(os.path.join(p, "skills", "empty"))
        found = self.findings(os.path.join(p, ".claude-plugin/plugin.json"))
        self.assertEqual([(f.id, f.severity) for f in found], [("PL002", "warn")])

    def test_pl003(self):
        self.plugin()
        write(self.tmp, "docs/x.md", f"line\n[dead](nope.md)\n{FENCE}\n[fenced](gone.md)\n{FENCE}\n"
                                     "`[code](span.md)` [ok](x.md)\n")
        write(self.tmp, "node_modules/pkg/README.md", "[dead](nope.md)\n")
        found = self.findings(os.path.join(self.tmp, ".claude-plugin/plugin.json"))
        self.assertEqual([(f.id, f.line) for f in found], [("PL003", 2)])
        self.assertTrue(found[0].path.endswith(os.path.join("docs", "x.md")))


    def manifest(self, **fields):
        return write(self.tmp, ".claude-plugin/plugin.json", json.dumps(fields))

    def test_pl004_reserved_names(self):
        # Each verdict below is what `claude plugin validate` said on 2.1.295.
        reserved = ["claude-authoring", "anthropic-x", "anthropics-x", "cc-plugin-x", "claude", "anthropic",
                    "anthropics", "claude-code", "claude-mods", "official-claude-tools", "my-anthropic-official",
                    "official-claude", "OFFICIAL-ANTHROPIC-x", "unofficial-claude-x", "Claude-X", "claude_x",
                    "anthropic_x", "claude.x", "anthropic--x", "cc_plugin_x", "CC-PLUGIN-X", "claude-",
                    "official-claudette", "myclaude-official"]
        reads_as = ["my-claude-tools", "my-anthropic-tools", "tools-for-claude", "x-anthropics",
                    "x-official-y-claude", "x_claude_y"]
        fine = ["good-name", "authoring-kit", "official-tools", "claudette", "cc-plugin", "claudecode-x",
                "my-cc-plugin-x", "claudes-x", "official", "9lives"]
        for names, verdict in ((reserved, "reserved"), (reads_as, "reads-as"), (fine, None)):
            for name in names:
                with self.subTest(name=name):
                    self.assertEqual(cl.reserved_plugin_name(name), verdict)
        found = [f for f in self.findings(self.manifest(name="claude-authoring")) if f.id == "PL004"]
        self.assertEqual([(f.severity, f.line) for f in found], [("error", 1)])     # the validator exits 1
        self.assertIn("claude plugin validate", found[0].message)
        self.assertEqual(run(self.manifest(name="claude-authoring")).returncode, 1)
        found = [f for f in self.findings(self.manifest(name="my-claude-tools")) if f.id == "PL004"]
        self.assertEqual([f.severity for f in found], ["warn"])                    # the validator warns, exit 0
        self.assertIn("whole word", found[0].message)
        self.assertEqual(run(self.manifest(name="my-claude-tools")).returncode, 0)
        self.assertEqual(self.ids(self.manifest(name="authoring-kit")), [])

    def test_pl004_ignores_case_and_runs_of_separators(self):
        # A second pass against `claude plugin validate` 2.1.295 for the documented wording: the check
        # "ignores case and treats any run of separators as one". (exit code, said "reserved", said "reads as")
        observed = {
            "claude-x": "reserved", "Claude-X": "reserved", "claude--x": "reserved", "claude_x": "reserved",
            "claude.x": "reserved", "claude__--x": "reserved", "claude": "reserved", "anthropic": "reserved",
            "claude-code": "reserved", "Claude_Code": "reserved", "claude--code": "reserved",
            "claude.mods": "reserved", "cc-plugin-x": "reserved", "cc--plugin-x": "reserved",
            "cc_plugin__x": "reserved", "official-claude": "reserved", "x-official-claude-y": "reserved",
            "x-official--claude": "reserved", "claude-official-x": "reserved", "official_claude": "reserved",
            "officialclaude": "reserved", "x-anthropic-official": "reserved", "claude.official": "reserved",
            "mcp-for-claude": "reads-as", "mcp-for-Claude": "reads-as", "mcp_for_claude": "reads-as",
            "mcp--for--claude": "reads-as", "x-claude-y": "reads-as", "x.anthropic.y": "reads-as",
            "x-anthropics": "reads-as", "my-claude-code": "reads-as", "official-x-claude": "reads-as",
            "x-claude-code-y": "reads-as", "x/claude": "reads-as",
            "x-claudes": None, "myclaude": None, "claudex": None, "my-cc-plugin-x": None, "good-name": None,
            "anthropicx": None,
        }
        for name, verdict in observed.items():
            with self.subTest(name=name):
                self.assertEqual(cl.reserved_plugin_name(name), verdict)

    def test_pl007_top_level_bin_directory(self):
        self.plugin()
        manifest = os.path.join(self.tmp, ".claude-plugin/plugin.json")
        write(self.tmp, "scripts/tool", "")
        write(self.tmp, "skills/a/bin/tool", "")                  # only the plugin root's own bin/ counts
        write(self.tmp, "skills/a/SKILL.md", "---\ndescription: d\n---\n")
        self.assertEqual(self.ids(manifest), [])
        write(self.tmp, "bin", "a file called bin is not the directory\n")
        self.assertEqual(self.ids(manifest), [])
        os.remove(os.path.join(self.tmp, "bin"))
        write(self.tmp, "bin/tool", "")
        found = self.findings(manifest)
        self.assertEqual([(f.id, f.severity) for f in found], [("PL007", "warn")])
        for part in ("claude.ai and Cowork don't install a plugin that has this directory", "`scripts/`",
                     "${CLAUDE_PLUGIN_ROOT}"):
            self.assertIn(part, found[0].message)
        self.assertFalse(os.path.lexists(os.path.join(ROOT, "bin")))      # and this plugin has none

    def test_pl004_reports_the_line_of_the_name(self):
        p = write(self.tmp, ".claude-plugin/plugin.json", '{\n  "version": "1.0.0",\n  "name": "claude-x"\n}\n')
        self.assertEqual([(f.id, f.line, f.severity) for f in self.findings(p)], [("PL004", 3, "error")])

    def test_pl005_kebab_case(self):
        for name in ("My_Plugin", "my.plugin", "-lead", "a--b", "trail-", "a\u00e9"):
            with self.subTest(name=name):
                found = self.findings(self.manifest(name=name))
                self.assertEqual([(f.id, f.severity) for f in found], [("PL005", "warn")])
        found = self.findings(self.manifest(name="my plugin"))
        self.assertEqual([(f.id, f.severity) for f in found], [("PL005", "error")])
        for name in ("good-name", "9lives", "a1-b2"):
            self.assertEqual(self.ids(self.manifest(name=name)), [])

    def test_pl006_field_types(self):
        found = self.findings(self.manifest(name="ok", version=1, author="a string", keywords="x"))
        self.assertEqual([(f.id, f.severity) for f in found], [("PL006", "error")] * 3)
        clean = self.manifest(name="ok", version="1.0", author={"name": "a"}, keywords=["x"], description="d")
        self.assertEqual(self.ids(clean), [])
        self.assertEqual(self.ids(self.manifest(name="ok", version="v1.0.0-beta.1+b5")), [])  # semver is not enforced


# ---- CLI --------------------------------------------------------------------

class CliTests(TempCase):
    def test_exit_codes_and_output_shapes(self):
        self.plugin()
        write(self.tmp, "skills/ok/SKILL.md", "---\ndescription: d\n---\nbody\n")
        r = run("--all", self.tmp)
        self.assertEqual((r.returncode, r.stdout), (0, ""))      # findings only on stdout
        self.assertIn("2 artifacts checked: 0 error, 0 warn, 0 info", r.stderr)   # plugin.json + the skill

        write(self.tmp, "skills/warned/SKILL.md", "---\nname: other\ndescription: d\n---\nbody\n")
        r = run("--all", cwd=self.tmp)
        self.assertEqual(r.returncode, 0)
        self.assertRegex(r.stdout, r"^skills/warned/SKILL\.md:2: warn SK002 ")

        write(self.tmp, "skills/bad/SKILL.md", "---\nname: BAD\n---\nbody\n")
        r = run(".", "--json", cwd=self.tmp)
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual(data["summary"], {"error": 1, "warn": 1, "info": 0, "artifacts": 4})
        self.assertEqual(set(data["findings"][0]), {"path", "line", "id", "severity", "message"})

        r = run("skills/ok/SKILL.md", "--json", cwd=self.tmp)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout),
                         {"findings": [], "summary": {"error": 0, "warn": 0, "info": 0, "artifacts": 1}})

    def test_non_artifacts_and_skipped_dirs(self):
        write(self.tmp, "README.md", "!`command` $ARGUMENTS\n")
        write(self.tmp, "node_modules/x/SKILL.md", "---\nname: BAD\n---\n")
        write(self.tmp, ".git/x/SKILL.md", "---\nname: BAD\n---\n")
        r = run("--all", self.tmp)
        # nothing matched is not "clean": it exits 2 and says so, so a wrong path cannot pass silently
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("no Claude Code artifacts", r.stderr)

    def test_usage_errors(self):
        self.assertEqual(run().returncode, 2)
        self.assertEqual(run("--bogus").returncode, 2)
        r = run(os.path.join(self.tmp, "nope.md"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("no such file", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_help_mentions_every_subcommand(self):
        r = run("--help")
        self.assertEqual(r.returncode, 0)
        for word in ("rules", "fields", "check-injection", "drift", "classify", "hook", "install-rules", "--all", "--json",
                     "--target", "--dry-run", "--check", "AGENTS.md", "claude-lint-disable"):
            self.assertIn(word, r.stdout)
        self.assertNotIn("--copy", r.stdout)   # still accepted, no longer advertised here
        sub = run("install-rules", "--help").stdout
        for word in ("--target", "--copy", "--dry-run", "--check", "Copying is the only mode"):
            self.assertIn(word, sub)
        self.assertNotIn("--link", r.stdout + sub)   # removed: a symlinked rule is never loaded
        self.assertNotIn("stamp", r.stdout)
        for sub_command in cl.COMMANDS:
            self.assertEqual(run(sub_command, "--help").returncode, 0, sub_command)
        self.assertIn("--extensions", run("classify", "--help").stdout)
        # the program keeps its name; the help says how to run it now that nothing puts it on PATH
        self.assertTrue(r.stdout.startswith("usage: claude-lint "))
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint"', r.stdout)
        self.assertIn("not on PATH", r.stdout)

    def test_messages_that_say_what_to_run_are_runnable(self):
        # nothing is on PATH, so a bare `claude-lint ...` in a message could not be pasted and run
        with open(LINT, encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("run install-rules", source)
        self.assertEqual(cl.self_command("install-rules"), f'python3 "{os.path.realpath(LINT)}" install-rules')
        p = write(self.tmp, "skills/s/SKILL.md", "---\ndescription: d\nalowed-tools: Read\n---\nbody\n")
        message = [f.message for f in self.findings(p) if f.id == "SK017"][0]
        self.assertIn(cl.self_command("fields", "skill"), message)

    def test_rules_listing(self):
        r = run("rules", "--json")
        data = json.loads(r.stdout)
        ids = [x["id"] for x in data["rules"]]
        expected = ([f"SK{n:03d}" for n in range(1, 19) if n not in (11, 14)]      # ids are never renumbered
                    + [f"RU{n:03d}" for n in range(1, 8)]
                    + [f"AG{n:03d}" for n in range(1, 11)] + [f"CM{n:03d}" for n in range(1, 5)]
                    + ["HK001"] + [f"PL{n:03d}" for n in range(1, 8)])
        self.assertEqual(ids, expected)
        self.assertEqual(set(data["rules"][0]), {"id", "severity", "kind", "check", "why"})
        for key, value in {"DESC_CAP": 1536, "SKILL_BODY_MAX_LINES": 500, "RULE_MAX_LINES": 200,
                           "MEMORY_MAX_LINES": 200, "IMPORT_MAX_HOPS": 4}.items():
            self.assertEqual(data["limits"][key], value)
        sev = {x["id"]: x["severity"] for x in data["rules"]}
        self.assertEqual((sev["SK016"], sev["SK012"], sev["SK010"]), ("info", "warn", "error"))
        self.assertEqual((sev["SK013"], sev["AG007"], sev["PL004"]), ("warn", "info", "error"))
        self.assertEqual((sev["SK015"], sev["AG006"], sev["CM004"], sev["PL007"]), ("warn",) * 4)
        self.assertEqual((sev["SK017"], sev["SK018"], sev["AG008"], sev["AG009"], sev["AG010"], sev["RU007"]),
                         ("warn",) * 6)
        self.assertEqual(set(data), {"rules", "limits", "kinds"})
        self.assertNotIn("STALE_PATCH_GAP", data["limits"])
        for key, value in {"AGENT_NAME_MAX": 256, "AGENT_SKILLS_MAX": 32, "PATHS_EXPANSION_MAX": 1000}.items():
            self.assertEqual(data["limits"][key], value)
        self.assertEqual(len(set(ids)), len(ids))
        text = run("rules").stdout
        for rule_id in expected:
            self.assertIn(rule_id, text)


# ---- hook mode --------------------------------------------------------------

class HookModeTests(TempCase):
    def payload(self, path):
        return json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Write",
                           "tool_input": {"file_path": path}})

    def test_non_artifact_is_silent(self):
        p = write(self.tmp, "notes.md", "!`command`\n")
        r = run("hook", stdin=self.payload(p))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_missing_file_is_silent(self):
        r = run("hook", stdin=self.payload(os.path.join(self.tmp, "skills/x/SKILL.md")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_clean_artifact_is_silent(self):
        p = write(self.tmp, "skills/x/SKILL.md", "---\ndescription: d\n---\nbody\n")
        r = run("hook", stdin=self.payload(p))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_finding_is_additional_context_json(self):
        p = write(self.tmp, "skills/x/SKILL.md", "---\nname: BAD\n---\nbody\n")
        r = run("hook", stdin=self.payload(p))
        self.assertEqual(r.returncode, 0)  # even with an error finding
        out = json.loads(r.stdout)
        self.assertEqual(list(out), ["hookSpecificOutput"])
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertEqual(set(out["hookSpecificOutput"]), {"hookEventName", "additionalContext"})
        ctx = out["hookSpecificOutput"]["additionalContext"]
        lines = ctx.split("\n")
        self.assertEqual(lines[0], f"[claude-lint] {p}")
        self.assertRegex(lines[1], r"^2: error SK001 ")
        self.assertEqual(ctx.count(p), 1)      # the path once, in the header

    def test_relative_path_resolves_against_event_cwd(self):
        write(self.tmp, "skills/x/SKILL.md", "---\nname: BAD\n---\nbody\n")
        payload = json.dumps({"cwd": self.tmp, "tool_input": {"file_path": "skills/x/SKILL.md"}})
        ctx = json.loads(run("hook", stdin=payload, cwd="/").stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx.split("\n")[0], "[claude-lint] skills/x/SKILL.md")
        self.assertRegex(ctx.split("\n")[1], r"^2: error SK001 ")

    def test_finding_about_another_file_keeps_its_path(self):
        self.plugin()
        write(self.tmp, "docs/x.md", "[dead](nope.md)\n")
        p = os.path.join(self.tmp, ".claude-plugin/plugin.json")
        ctx = json.loads(run("hook", stdin=self.payload(p)).stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx.split("\n")[0], f"[claude-lint] {p}")
        self.assertRegex(ctx.split("\n")[1], r"docs/x\.md:1: warn PL003 ")

    def test_non_artifact_exits_before_the_heavy_imports(self):
        p = write(self.tmp, "src/app.py", "print(1)\n")
        r = subprocess.run([sys.executable, "-X", "importtime", LINT, "hook"], input=self.payload(p),
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        imported = {ln.rsplit("|", 1)[-1].strip() for ln in r.stderr.splitlines()}
        for module in ("json", "re", "argparse", "subprocess", "hashlib", "shutil", "urllib.parse"):
            self.assertNotIn(module, imported)      # a .py payload is not even parsed
        p = write(self.tmp, "docs/notes.md", "x\n")
        compact = json.dumps(json.loads(self.payload(p)), separators=(",", ":"))      # as Claude Code writes it
        for payload in (self.payload(p), compact):
            r = subprocess.run([sys.executable, "-X", "importtime", LINT, "hook"], input=payload,
                               capture_output=True, text=True)
            self.assertEqual((r.returncode, r.stdout), (0, ""))
            imported = {ln.rsplit("|", 1)[-1].strip() for ln in r.stderr.splitlines()}
            # a .md that is not an artifact: the path is read off the front of the payload and classified
            for module in ("claude_lint", "json", "re", "dataclasses", "argparse", "subprocess", "hashlib", "shutil"):
                self.assertNotIn(module, imported)      # the linter itself is never imported for it
        relative = json.dumps({"cwd": self.tmp, "tool_input": {"file_path": "docs/notes.md"}})
        r = subprocess.run([sys.executable, "-X", "importtime", LINT, "hook"], input=relative,
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        imported = {ln.rsplit("|", 1)[-1].strip() for ln in r.stderr.splitlines()}
        self.assertIn("json", imported)             # a relative path needs the event's cwd: parsed, then classified
        for module in ("dataclasses", "argparse", "subprocess", "hashlib", "shutil", "urllib.parse"):
            self.assertNotIn(module, imported)

    def _launcher(self):
        import importlib.machinery, importlib.util
        loader = importlib.machinery.SourceFileLoader("claude_lint_launcher", LINT)
        spec = importlib.util.spec_from_loader("claude_lint_launcher", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)     # not __main__: defines _private_cache, runs nothing
        return mod

    def test_read_only_cache_is_private_to_the_user(self):
        cache = os.path.join(self.tmp, "cache")
        old = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = cache
        try:
            launcher = self._launcher()
            path = launcher._private_cache()
            self.assertEqual(path, os.path.join(cache, "claude-lint-pycache"))
            self.assertEqual(os.stat(path).st_mode & 0o077, 0)
            os.chmod(path, 0o777)                    # writable by others: refused, nothing cached
            self.assertIsNone(launcher._private_cache())
            os.chmod(path, 0o700)
            os.rmdir(path)
            os.symlink(self.tmp, path)               # a link planted in its place: refused
            self.assertIsNone(launcher._private_cache())
        finally:
            if old is None:
                os.environ.pop("XDG_CACHE_HOME", None)
            else:
                os.environ["XDG_CACHE_HOME"] = old
            sys.pycache_prefix = None

    def test_the_launcher_never_caches_in_the_temp_directory(self):
        with open(LINT, encoding="utf-8") as f:
            self.assertNotIn("gettempdir", f.read())

    def test_the_gate_module_imports_only_os(self):
        import ast
        with open(os.path.join(ROOT, "scripts", "claude_lint_gate.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        top = {a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names}
        top |= {n.module for n in tree.body if isinstance(n, ast.ImportFrom)}
        self.assertEqual(top, {"os"})       # json is imported lazily, only when a payload must be parsed

    def test_payload_prefilter_never_hides_an_artifact(self):
        self.plugin()
        p = write(self.tmp, "skills/caf\u00e9 x/SKILL.md", "---\nname: BAD\n---\nbody\n")
        escaped = json.dumps({"tool_input": {"file_path": p}}).replace("/", "\\/")     # \/ and \u00e9 escapes
        self.assertIn("\\u00e9", escaped)
        pretty = json.dumps({"tool_input": {"content": "x", "file_path": p}, "z": 1}, indent=4, ensure_ascii=False)
        for payload in (escaped, pretty, self.payload(p)):
            self.assertEqual(cl.hook_target(payload), (p, p))
            self.assertEqual(cl.hook_target(payload.encode()), (p, p))
            self.assertIn("SK001", run("hook", stdin=payload).stdout)
        # the prefilter is exactly the suffix test classify() starts with
        for suffix in cl.ARTIFACT_SUFFIXES:
            self.assertIsNone(cl.classify(os.path.join(self.tmp, "skills/a/SKILL" + suffix + ".bak")))
        self.assertIsNone(cl.hook_target('{"tool_input": {"file_path": "/x/app.py", "content": "open(\\"a.md\\")"}}'))

    def test_agents_md_is_linted_in_hook_mode(self):
        p = write(self.tmp, "AGENTS.md", "See @docs/missing.md\n")
        self.assertIn("CM002", run("hook", stdin=self.payload(p)).stdout)

    def test_hook_help_and_in_process_stdin(self):
        self.assertIn("usage: claude-lint hook", run("hook", "--help").stdout)
        p = write(self.tmp, "skills/x/SKILL.md", "---\nname: BAD\n---\nbody\n")
        buf = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(self.payload(p))), redirect_stdout(buf):
            self.assertEqual(cl.cmd_hook([]), 0)
        self.assertIn("SK001", buf.getvalue())

    def test_output_is_bounded(self):
        body = "".join(f"!{BT}tool{i} run{BT}\n" for i in range(30))
        p = write(self.tmp, "skills/x/SKILL.md", f"---\ndescription: d\n---\n{body}")
        ctx = json.loads(run("hook", stdin=self.payload(p)).stdout)["hookSpecificOutput"]["additionalContext"]
        lines = ctx.split("\n")
        self.assertEqual(len(lines), 1 + 20 + 1)
        self.assertEqual(lines[-1], "(+40 more)")  # SK005 + SK013 per line
        self.assertTrue(all(ln[0].isdigit() for ln in lines[1:-1]))

    def test_a_file_over_the_size_limit_is_not_linted(self):
        # the write-time hook has a 30 second timeout: over 1 MiB, one info line and nothing else
        self.assertEqual(cl.HOOK_MAX_BYTES, 1024 * 1024)
        head = "---\nname: BAD\n---\n"
        p = write(self.tmp, "skills/x/SKILL.md", head + "x" * (cl.HOOK_MAX_BYTES - len(head)))
        self.assertEqual(os.path.getsize(p), cl.HOOK_MAX_BYTES)
        self.assertIn("SK001", run("hook", stdin=self.payload(p)).stdout)       # at the limit: linted
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n")
        started = time.monotonic()
        r = run("hook", stdin=self.payload(p))
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PostToolUse")
        lines = out["additionalContext"].split("\n")
        self.assertEqual(lines[0], f"[claude-lint] {p}")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith("info: file too large to lint at write time"), lines[1])
        self.assertIn(cl.self_command(), lines[1])
        self.assertNotIn("SK001", r.stdout)
        self.assertEqual(run(p).returncode, 1)               # linted on demand all the same

    def test_malformed_stdin(self):
        for stdin in ("", "not json", "[]", "{}", '{"tool_input": {}}', '{"tool_input": {"file_path": 7}}'):
            with self.subTest(stdin=stdin):
                r = run("hook", stdin=stdin)
                self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_shim(self):
        p = write(self.tmp, "skills/x/SKILL.md", "---\nname: BAD\n---\nbody\n")
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        with_root = subprocess.run(["sh", SHIM], input=self.payload(p), capture_output=True, text=True,
                                   env=dict(env, CLAUDE_PLUGIN_ROOT=ROOT))
        self.assertEqual(with_root.returncode, 0)
        self.assertIn("additionalContext", json.loads(with_root.stdout)["hookSpecificOutput"])
        # no plugin root and no claude-lint on PATH - the normal case outside a plugin: a silent no-op
        bare = dict(env, PATH=os.path.dirname(sys.executable) + os.pathsep + "/usr/bin:/bin")
        if not any(os.path.exists(os.path.join(d, "claude-lint")) for d in bare["PATH"].split(os.pathsep)):
            without = subprocess.run(["sh", SHIM], input=self.payload(p), capture_output=True, text=True, env=bare)
            self.assertEqual((without.returncode, without.stdout, without.stderr), (0, "", ""))
        # second choice: a claude-lint somebody put on PATH themselves (the plugin itself puts nothing there)
        mine = os.path.join(self.tmp, "mybin")
        os.makedirs(mine)
        wrapper = os.path.join(mine, "claude-lint")       # not a symlink to LINT: it may have no exec bit
        with open(wrapper, "w", encoding="utf-8") as f:
            f.write(f"import runpy\nrunpy.run_path({LINT!r}, run_name='__main__')\n")      # the shim runs it with python3
        os.chmod(wrapper, 0o755)
        on_path = subprocess.run(["sh", SHIM], input=self.payload(p), capture_output=True, text=True,
                                 env=dict(env, PATH=mine + os.pathsep + bare["PATH"]))
        self.assertIn("SK001", on_path.stdout)
        # and the plugin root wins over PATH when both are there
        decoy = os.path.join(self.tmp, "decoy")
        os.makedirs(decoy)
        with open(os.path.join(decoy, "claude-lint"), "w") as f:
            f.write("print('DECOY')\n")
        os.chmod(os.path.join(decoy, "claude-lint"), 0o755)      # `command -v` only finds an executable
        both = subprocess.run(["sh", SHIM], input=self.payload(p), capture_output=True, text=True,
                              env=dict(env, PATH=decoy + os.pathsep + bare["PATH"], CLAUDE_PLUGIN_ROOT=ROOT))
        self.assertNotIn("DECOY", both.stdout)
        self.assertIn("SK001", both.stdout)
        with open(SHIM, encoding="utf-8") as f:
            self.assertIn('"$CLAUDE_PLUGIN_ROOT/scripts/claude-lint"', f.read())

    def test_shim_without_python_is_a_silent_noop(self):
        sh = subprocess.run(["sh", "-c", "command -v sh"], capture_output=True, text=True).stdout.strip()
        os.symlink(sh, os.path.join(self.tmp, "sh"))
        proc = subprocess.run([sh, SHIM], input="{}", capture_output=True, text=True,
                              env={"PATH": self.tmp, "CLAUDE_PLUGIN_ROOT": ROOT})
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))

    def shim_code(self):
        with open(SHIM, encoding="utf-8") as f:
            return "\n".join(ln for ln in f.read().split("\n") if not ln.lstrip().startswith("#"))

    def shim_gate(self):
        """The suffixes the shim's one `case` lets through, read out of its patterns (`*'.md"'*`)."""
        import re
        code = self.shim_code()
        block = code[code.index("case $payload in"):code.index("esac")]
        return re.findall(r"\*'(\.[A-Za-z0-9]+)\"'\*", block), block

    def test_shim_has_no_path_list_other_than_the_extension_gate(self):
        code = self.shim_code()
        for needle in ("SKILL", "CLAUDE.md", "AGENTS", "settings", "plugin.json", "hooks.json", "rules", "agents",
                       "commands", "file_path", "jq", "grep", "sed", "awk"):
            self.assertNotIn(needle, code)
        self.assertEqual(code.count("case "), 1)                 # the gate, and nothing else that matches text
        suffixes, block = self.shim_gate()
        # every pattern in the gate is a bare suffix followed by a closing quote: no directory, no file name
        patterns = [x.strip() for arm in block.split("\n")[1:] if ")" in arm
                    for x in arm.split(")")[0].split("|")]
        self.assertEqual(sorted(patterns), sorted(["*'" + x + "\"'*" for x in suffixes] + ["*"]))

    def test_shim_gate_is_exactly_the_extensions_classify_can_return(self):
        suffixes, _ = self.shim_gate()
        listed = run("classify", "--extensions").stdout.split()
        self.assertEqual(sorted(suffixes), sorted(listed))
        self.assertEqual(sorted(listed), sorted(cl.ARTIFACT_SUFFIXES))

    def run_shim(self, payload, **env):
        base = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        if isinstance(payload, str):
            payload = payload.encode()
        return subprocess.run(["sh", SHIM], input=payload, capture_output=True,
                              env=dict(base, CLAUDE_PLUGIN_ROOT=ROOT, **env))

    def test_shim_gate_agrees_with_the_linter_on_adversarial_payloads(self):
        """The shim must print exactly what `claude-lint hook` prints for the same payload: the gate may only
        ever skip a payload the linter would have been silent about."""
        self.plugin()
        bad = write(self.tmp, "skills/x/SKILL.md", "---\nname: BAD\n---\nbody\n")
        spaced = write(self.tmp, "skills/my skill/SKILL.md", "---\nname: BAD\n---\nbody\n")
        quoted = write(self.tmp, 'skills/q"uote/SKILL.md', "---\nname: BAD\n---\nbody\n")
        rule = write(self.tmp, ".claude/rules/r.md", "no applies line\n")
        manifest = os.path.join(self.tmp, ".claude-plugin/plugin.json")
        write(self.tmp, "docs/x.md", "[dead](nope.md)\n")
        upper = write(self.tmp, "skills/up/SKILL.MD", "---\nname: BAD\n---\nbody\n")
        py = write(self.tmp, "src/app.py", "x = 1\n")
        big = "x = 1  # filler\n" * 13000                         # about 200 KB
        decoy = '{"tool_input": {"file_path": "x.py"}} "file_path":"x.py" open("a.md") \\ `id` $HOME %s \'q\''

        def event(path, content="x", first=True, **extra):
            ti = {"file_path": path, "content": content} if first else {"content": content, "file_path": path}
            return dict({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": ti}, **extra)

        cases = {
            "file_path first": (event(bad), True),
            "file_path last": (event(bad, first=False), True),
            "path with a space": (event(spaced), True),
            "path with an escaped quote": (event(quoted), True),
            "rule file": (event(rule), True),
            "plugin manifest (.json)": (event(manifest), True),
            "content names another file_path": (event(bad, decoy, first=False), True),
            "content names another file_path, path first": (event(bad, decoy), True),
            "200 KB content, artifact": (event(bad, big, first=False), True),
            "200 KB content, not an artifact": (event(py, big), False),
            "tool_response repeats the content": (event(bad, big, tool_response={"filePath": bad, "content": big}), True),
            "not an artifact (.py)": (event(py), False),
            ".py whose content mentions artifacts": (event(py, decoy + ' "SKILL.md" .json'), False),
            ".py whose content ends a string in .md": (event(py, "see notes.md"), False),
            "uppercase .MD is not an artifact": (event(upper), False),
            "non-artifact .md": (event(os.path.join(self.tmp, "docs/x.md")), False),
            "missing file": (event(os.path.join(self.tmp, "skills/gone/SKILL.md")), False),
        }
        for name, (data, expect_findings) in cases.items():
            for style, payload in (("compact", json.dumps(data)), ("spaced", json.dumps(data, indent=2)),
                                   ("ascii-escaped slashes", json.dumps(data).replace("/", "\\/")),
                                   ("no trailing newline", json.dumps(data, separators=(",", ":"))),
                                   ("trailing newlines", json.dumps(data) + "\n\n")):
                with self.subTest(case=name, style=style):
                    direct = subprocess.run([sys.executable, LINT, "hook"], input=payload.encode(),
                                            capture_output=True)
                    shim = self.run_shim(payload)
                    self.assertEqual((shim.returncode, shim.stderr), (0, b""))
                    self.assertEqual(shim.stdout, direct.stdout)
                    self.assertEqual(bool(shim.stdout), expect_findings)
        for junk in ("", "\n", "not json", "{}", '{"tool_input": {}}', '.md"', '{"a": ".json"}', "\\", "'", "$(id)"):
            with self.subTest(junk=junk):
                shim = self.run_shim(junk)
                self.assertEqual((shim.returncode, shim.stdout, shim.stderr), (0, b"", b""))

    def test_shim_gate_skips_python_only_when_no_artifact_suffix_is_present(self):
        """Put a python3 on PATH that leaves a mark: the gate must not start it for a payload with no artifact
        suffix in it, and must start it whenever one is there - whatever else the payload holds."""
        fake = os.path.join(self.tmp, "fakebin")
        os.makedirs(fake)
        mark = os.path.join(self.tmp, "python-started")
        with open(os.path.join(fake, "python3"), "w") as f:
            f.write(f"#!/bin/sh\n: > '{mark}'\ncat > /dev/null\n")
        os.chmod(os.path.join(fake, "python3"), 0o755)

        def started(payload):
            if os.path.exists(mark):
                os.remove(mark)
            self.run_shim(payload, PATH=fake + os.pathsep + "/usr/bin:/bin")
            return os.path.exists(mark)

        def event(path, content="x"):
            return json.dumps({"tool_input": {"content": content, "file_path": path}})

        self.assertFalse(started(event("/r/src/app.py")))
        self.assertFalse(started(event("/r/src/app.py", "x = 1\n" * 30000)))
        self.assertFalse(started(event("/r/SKILL.MD")))                              # classify is case-sensitive
        self.assertFalse(started(event("/r/a.py", 'open("notes.md") and "file_path":"x.md"')))   # \" is not "
        self.assertFalse(started(event("/r/notes.markdown")))
        self.assertFalse(started(""))
        self.assertTrue(started(event("/r/skills/x/SKILL.md")))
        self.assertTrue(started(event("/r/docs/notes.md")))                           # Python decides, not the shim
        self.assertTrue(started(event("/r/.claude/settings.json", "y" * 200000)))
        self.assertTrue(started(event('/r/a "b/SKILL.md')))
        self.assertTrue(started(json.dumps({"tool_input": {"file_path": "/r/SKILL.md", "content": "x"}})))
        self.assertTrue(started(json.dumps({"tool_input": {"file_path": "/r/a.py"}, "note": "x.json"})))  # unsure: fall through


# ---- install-rules ----------------------------------------------------------

class InstallRulesTests(TempCase):
    def setUp(self):
        super().setUp()
        self.src = os.path.join(self.tmp, "plugin")
        self.proj = os.path.join(self.tmp, "proj")
        os.makedirs(self.proj)
        write(self.src, ".claude-plugin/plugin.json", json.dumps({"name": "demo-kit"}))
        write(self.src, "rules/alpha.md", "alpha\n")
        write(self.src, "rules/beta.md", "beta\n")
        write(self.src, "rules/notes.txt", "ignored\n")
        self.dest = os.path.join(self.proj, ".claude", "rules")
        self.alpha = os.path.join(self.dest, "demo-kit-alpha.md")
        self.beta = os.path.join(self.dest, "demo-kit-beta.md")

    def install(self, **kw):
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.object(cl, "eprint", lambda *a: buf.write(" ".join(a) + "\n")):
            skipped = cl.install_rules(self.proj, plugin_root=self.src, **kw)
        return skipped, buf.getvalue()

    def md(self):
        return sorted(n for n in os.listdir(self.dest) if n.endswith(".md"))

    def content(self, path):
        with open(path) as f:
            return f.read()

    def test_copy_is_the_default_and_idempotent(self):
        skipped, out = self.install()
        self.assertEqual((skipped, out.count("copy ")), (0, 2))
        self.assertEqual(self.md(), ["demo-kit-alpha.md", "demo-kit-beta.md"])
        self.assertFalse(os.path.islink(self.alpha))
        self.assertEqual(self.content(self.alpha), "alpha\n")
        self.assertEqual(cl.classify(self.alpha), "rule")
        self.assertTrue(os.path.isfile(os.path.join(self.dest, ".demo-kit-rules.json")))
        before = sorted(os.listdir(self.dest))
        skipped, out = self.install()
        self.assertEqual((skipped, out.count("already up to date")), (0, 2))
        self.assertEqual(sorted(os.listdir(self.dest)), before)

    def test_prefix_comes_from_the_plugins_own_manifest(self):
        self.assertEqual(cl.own_plugin_name(self.src), "demo-kit")
        write(self.src, ".claude-plugin/plugin.json", json.dumps({"name": "renamed"}))
        self.install()
        self.assertEqual(self.md(), ["renamed-alpha.md", "renamed-beta.md"])

    def test_fallback_name_without_a_usable_manifest(self):
        for manifest in ("{not json", json.dumps({"name": "../evil"}), json.dumps({"name": 7}), json.dumps([])):
            write(self.src, ".claude-plugin/plugin.json", manifest)
            self.assertEqual(cl.own_plugin_name(self.src), cl.FALLBACK_PLUGIN_NAME)
        os.remove(os.path.join(self.src, ".claude-plugin", "plugin.json"))
        self.assertEqual(cl.own_plugin_name(self.src), "claude-lint")
        self.install()
        self.assertEqual(self.md(), ["claude-lint-alpha.md", "claude-lint-beta.md"])

    def test_no_plugin_name_literal_in_the_linter(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            name = json.load(f)["name"]
        self.assertEqual(cl.own_plugin_name(), name)
        for script in ("claude-lint", "claude_lint.py", "claude_lint_gate.py"):
            with open(os.path.join(ROOT, "scripts", script), encoding="utf-8") as f:
                self.assertNotIn(name, f.read(), script)

    def test_dry_run_changes_nothing(self):
        skipped, out = self.install(dry_run=True)
        self.assertFalse(os.path.exists(self.dest))
        self.assertEqual(out.count("would copy"), 2)

    def test_never_overwrites_a_foreign_file(self):
        mine = write(self.proj, ".claude/rules/demo-kit-alpha.md", "hand written\n")
        skipped, out = self.install()
        self.assertEqual(skipped, 1)
        self.assertIn("skip", out)
        self.assertEqual(self.content(mine), "hand written\n")
        self.assertFalse(os.path.islink(mine))

    def test_refreshes_only_its_own_unedited_copies(self):
        self.install()
        write(self.src, "rules/alpha.md", "alpha v2\n")     # upstream change: refreshed
        write(self.src, "rules/beta.md", "beta v2\n")
        with open(self.beta, "w") as f:                      # local edit: left alone
            f.write("edited locally\n")
        skipped, out = self.install()
        self.assertEqual(skipped, 1)
        self.assertIn(f"skip     {self.beta}", out)
        self.assertEqual(self.content(self.alpha), "alpha v2\n")
        self.assertEqual(self.content(self.beta), "edited locally\n")

    def links_from_an_earlier_version(self):
        """What `install-rules --link` used to leave: a symlink per rule, no manifest."""
        os.makedirs(self.dest, exist_ok=True)
        for name, dest in (("alpha.md", self.alpha), ("beta.md", self.beta)):
            os.symlink(os.path.join(self.src, "rules", name), dest)

    def test_there_is_no_link_mode(self):
        # A symlinked rule whose target is outside the project is not loaded, so the mode is gone.
        with self.assertRaises(TypeError):
            cl.install_rules(self.proj, link=True, plugin_root=self.src)
        r = run("install-rules", "--target", self.proj, "--link")
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        for part in ("--link has been removed", "never loaded", "Copying is the only mode"):
            self.assertIn(part, r.stderr)
        self.assertFalse(os.path.exists(self.dest))                      # and nothing was installed
        self.assertEqual(run("install-rules", "--target", self.proj, "--link", "--dry-run").returncode, 2)
        self.assertEqual(run("install-rules", "--link=yes").returncode, 2)
        with open(LINT, encoding="utf-8") as f:
            self.assertNotIn("os.symlink", f.read())

    def test_links_from_an_earlier_version_become_copies(self):
        self.links_from_an_earlier_version()
        skipped, out = self.install(dry_run=True)
        self.assertEqual(out.count("would copy"), 2)
        self.assertTrue(os.path.islink(self.alpha))
        skipped, out = self.install()
        self.assertEqual((skipped, out.count("replacing a symlink")), (0, 2))
        self.assertFalse(os.path.islink(self.alpha) or os.path.islink(self.beta))
        self.assertEqual(self.content(self.alpha), "alpha\n")
        self.assertEqual(self.content(os.path.join(self.src, "rules", "alpha.md")), "alpha\n")   # source untouched
        self.assertTrue(os.path.isfile(os.path.join(self.dest, ".demo-kit-rules.json")))
        self.assertEqual(self.install()[1].count("already up to date"), 2)

    def test_a_dangling_link_is_replaced_by_a_copy(self):
        os.makedirs(self.dest)
        os.symlink("/gone/plugin-cache/v1/rules/alpha.md", self.alpha)
        skipped, out = self.install()
        self.assertEqual(skipped, 0)
        self.assertFalse(os.path.islink(self.alpha))
        self.assertEqual(self.content(self.alpha), "alpha\n")

    def check(self):
        return self.install(check=True)

    def test_check(self):
        problems, out = self.check()
        self.assertEqual(problems, 2)
        self.assertEqual(out.count("missing  "), 2)
        self.assertFalse(os.path.exists(self.dest))          # check never writes
        self.install()
        self.assertEqual(self.check(), (0, ""))
        write(self.src, "rules/alpha.md", "alpha v2\n")
        with open(self.beta, "w") as f:
            f.write("edited locally\n")
        snapshot = {n: self.content(os.path.join(self.dest, n)) for n in os.listdir(self.dest)}
        problems, out = self.check()
        self.assertEqual(problems, 2)
        self.assertIn(f"outdated {self.alpha}", out)
        self.assertIn(f"modified {self.beta}", out)
        self.assertEqual({n: self.content(os.path.join(self.dest, n)) for n in os.listdir(self.dest)}, snapshot)

    def test_check_reports_links(self):
        self.links_from_an_earlier_version()
        problems, out = self.check()                         # a link that works is still a rule that never loads
        self.assertEqual((problems, out.count("linked   ")), (2, 2))
        self.assertIn("a symlinked rule is not loaded", out)
        self.assertIn(cl.self_command("install-rules"), out)
        os.remove(self.alpha)
        os.symlink("/gone/rules/alpha.md", self.alpha)
        os.remove(self.beta)
        os.symlink(os.path.join(self.src, "rules", "alpha.md"), self.beta)
        problems, out = self.check()
        self.assertEqual(problems, 2)
        self.assertIn(f"dangling {self.alpha}", out)
        self.assertIn(f"foreign  {self.beta}", out)
        self.assertTrue(os.path.islink(self.alpha))          # check never writes

    def earlier_install(self):
        """What a run under the plugin's previous name left behind: one copy
        with its manifest, and one symlink into a cache that has since gone."""
        old_copy = write(self.proj, ".claude/rules/old-name-alpha.md", "alpha\n")
        write(self.proj, ".claude/rules/.old-name-rules.json", json.dumps({"old-name-alpha.md": cl._sha(old_copy)}))
        old_link = os.path.join(self.dest, "old-name-beta.md")
        os.symlink("/gone/cache/old-name/1.0/rules/beta.md", old_link)
        return old_copy, old_link

    def test_recognises_files_installed_under_an_earlier_name(self):
        old_copy, old_link = self.earlier_install()
        unrelated = write(self.proj, ".claude/rules/team-style.md", "ours\n")
        other_link = os.path.join(self.dest, "notes-beta.md")
        os.symlink(os.path.join(self.proj, "docs", "beta.md"), other_link)   # not a rules/ link: not ours
        problems, out = self.check()
        self.assertEqual(out.count("stale    "), 2)
        skipped, out = self.install()
        self.assertEqual(skipped, 0)
        self.assertEqual(out.count("remove   "), 2)
        self.assertFalse(os.path.lexists(old_copy))
        self.assertFalse(os.path.lexists(old_link))
        self.assertFalse(os.path.exists(os.path.join(self.dest, ".old-name-rules.json")))
        self.assertTrue(os.path.lexists(other_link))
        self.assertEqual(self.content(unrelated), "ours\n")
        self.assertEqual(self.md(), ["demo-kit-alpha.md", "demo-kit-beta.md", "notes-beta.md", "team-style.md"])
        self.assertEqual(self.check(), (0, ""))

    def test_an_edited_file_from_an_earlier_name_is_left_alone(self):
        old_copy, _ = self.earlier_install()
        with open(old_copy, "w") as f:
            f.write("edited\n")
        skipped, out = self.install()
        self.assertEqual(skipped, 1)
        self.assertIn(f"skip     {old_copy}", out)
        self.assertEqual(self.content(old_copy), "edited\n")
        self.assertTrue(os.path.exists(os.path.join(self.dest, ".old-name-rules.json")))

    def test_cli_against_the_real_plugin(self):
        shipped = len([n for n in os.listdir(os.path.join(ROOT, "rules")) if n.endswith(".md")])
        self.assertEqual(run("install-rules", "--target", self.proj, "--check").returncode, 1)
        self.assertEqual(run("install-rules", "--target", self.proj, "--dry-run").returncode, 0)
        self.assertFalse(os.path.exists(self.dest))
        r = run("install-rules", "--target", self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.count("copy     "), shipped)
        self.assertEqual(len(self.md()), shipped)
        self.assertFalse(any(os.path.islink(os.path.join(self.dest, n)) for n in self.md()))
        r = run("install-rules", "--target", self.proj, "--check")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = run("install-rules", "--target", self.proj, "--copy")       # the old flag: a no-op alias
        self.assertEqual((r.returncode, r.stdout.count("already up to date")), (0, shipped))
        r = run("install-rules", "--target", self.proj, "--link")
        self.assertEqual(r.returncode, 2)
        self.assertFalse(any(os.path.islink(os.path.join(self.dest, n)) for n in self.md()))
        self.assertEqual(run("install-rules", "--target", self.proj, "--link", "--copy").returncode, 2)
        self.assertEqual(run("install-rules", "--target", os.path.join(self.tmp, "nope")).returncode, 2)


# ---- SK012 on the bodies that were actually corrupted -------------------------

# Lines copied from the plugin's own SKILL.md files as they shipped before the
# preprocessing bug was understood (v0.1, when the plugin was still called
# claude-authoring). True marks a line the skill preprocessor corrupted at load:
# a directive that ran, or a token that was replaced. False marks its
# neighbours, which loaded intact. Blocks are separated by a blank line.
ORIGINAL_BODY_LINES = [
    # authoring-skills/SKILL.md - "Arguments"
    ("- **`arguments`** - Names positional args for `$name` substitution", False),
    ("  (`arguments: [issue, branch]` → `$issue`, `$branch`). Prefer named over", False),
    ("  `$0`/`$1` past one argument.", True),
    ("", False),
    # authoring-skills/SKILL.md - "Dynamic context injection"
    ("- **`` !`command` ``** inline; **```` ```! ````** fenced for multi-line.", True),
    ("- **Prefer injection over instructing Claude to run the same command** -", False),
    ("  one deterministic preprocessing step replaces a probabilistic tool call.", False),
    ("- **Always include a fallback**: on failure stderr lands in the prompt;", False),
    ("  use `` !`cmd 2>/dev/null || echo \"no data: <reason>\"`` so the skill", True),
    ("  degrades into something actionable.", False),
    ("- **Standard `$VAR` is not expanded** - read env vars via", False),
    ("  `` !`echo $VAR` ``; never inline secrets, the output enters the prompt.", True),
    ("- **Bound the output** - injected output is prompt content; pipe large", False),
    ("  things through `head`, `--stat`, or a summarizing tool.", False),
    ("", False),
    # authoring-skills/SKILL.md - "Argument substitutions" and "Built-in variables"
    ("- **`$ARGUMENTS`** - all arguments; if the placeholder is absent,", True),
    ("  arguments are appended as `ARGUMENTS: <value>`, so place it", False),
    ("  deliberately.", False),
    ("- **`$ARGUMENTS[N]` / `$N`** - 0-based positional access.", True),
    ("- **`$name`** - named positionals declared in `arguments` frontmatter.", False),
    ("", False),
    ("- **`${CLAUDE_SESSION_ID}`** - logging, session-scoped files.", True),
    ("- **`${CLAUDE_EFFORT}`** - active effort level; adapt instructions to it.", True),
    ("- **`${CLAUDE_SKILL_DIR}`** - the skill's own directory (secondary-sourced;", True),
    ("  verify on your version). If available, the portable way to call bundled", False),
    ("  tools: `` \\!`${CLAUDE_SKILL_DIR}/tools/check.sh` ``.", True),
    ("- Not available in skill bodies: `${CLAUDE_PROJECT_DIR}` (hooks),", True),
    ("  `${CLAUDE_PLUGIN_ROOT}` (plugin components). They silently fail to", True),
    ("  expand.", False),
    ("", False),
    # authoring-skills/SKILL.md - "Security review"
    ("1. Review every `` !` `` and ```` ```! ```` directive in third-party or", True),
    ("   repo-borne skills before first use - arbitrary code execution at skill", False),
    ("", False),
    # authoring-rules/SKILL.md - "Body conventions"
    ("Bodies are plain markdown facts. None of the skill-body grammar applies:", False),
    ("no `` !`command` `` injection, no `$ARGUMENTS`, no `${...}` variables -", True),
    ("these arrive as literal text without warning. Whether `@path` imports", False),
    ("", False),
    # authoring-hooks/SKILL.md - "Hooks in a plugin"
    ("outer `{\"hooks\": {...}}` wrapper**; without it the hooks silently fail to", False),
    ("register. Reference bundled scripts via `${CLAUDE_PLUGIN_ROOT}` (never a", True),
    ("hard-coded path); `${CLAUDE_PLUGIN_DATA}` gives update-surviving state. Plugin", True),
    ("hooks merge with user and project hooks, register when the plugin is enabled,", False),
    ("", False),
    # authoring-hooks/SKILL.md - intentional uses, which worked as written
    ("   python3 ${CLAUDE_SKILL_DIR}/scripts/hooktool.py events", False),
    ("   python3 ${CLAUDE_SKILL_DIR}/scripts/hooktool.py validate .claude/settings.json", False),
    ("!`python3 ${CLAUDE_SKILL_DIR}/scripts/hooktool.py claudemd 2>/dev/null || echo \"(hooktool docs unavailable — run: python3 scripts/hooktool.py claudemd)\"`", False),
    ("", False),
    # every stamped skill - the injection is intended (SK013 is what it failed)
    ("> https://code.claude.com/docs/en/skills). Running version: !`claude --version 2>/dev/null || echo \"unknown\"`", False),
]

# Intentional uses in the tree as it is now, plus the shapes the heuristic must
# leave alone: a path built from a variable, a variable handed over as a value.
INTENTIONAL_LINES = [
    "directly): `${CLAUDE_SKILL_DIR}/references/minimizing-model-work.md` and",
    "`${CLAUDE_SKILL_DIR}/references/composition.md`.",
    "The bundled tool is run by its full path: `python3 \"${CLAUDE_SKILL_DIR}/scripts/hooktool.py\" events`.",
    "> Version check: !`python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint\" stamp 2.1.295 2>/dev/null || echo \"version check unavailable - written for 2.1.295\"`",
    "This skill lives at `${CLAUDE_SKILL_DIR}`.",
    "Skill directory: `${CLAUDE_SKILL_DIR}`",
    "Write the transcript to `${CLAUDE_PLUGIN_DATA}/runs/${CLAUDE_SESSION_ID}.jsonl`.",
    "The plugin root is",
    "`${CLAUDE_PLUGIN_ROOT}`; resolve every path against it.",
    "Fix issue $ARGUMENTS on the branch named `$1`, then compare `$0` and `$1`.",
    "**Important:** pass $ARGUMENTS through verbatim.",
    "The arguments, verbatim: `$ARGUMENTS`",
    "Run `gh issue view $ARGUMENTS --json title` and summarise it.",
    "An escaped literal is fine: \\!`command`",
    "Costs about $5 per run, or $ARGUMENTS if the caller says otherwise.",
]


class Sk012OriginalBodiesTests(TempCase):
    def sk012_lines(self, lines):
        body = "\n".join(lines) + "\n"
        p = write(self.tmp, "skills/s/SKILL.md", "---\ndescription: d\n---\n" + body)
        first = 4
        return sorted({f.line - first for f in self.findings(p) if f.id == "SK012"}), self.findings(p)

    def test_every_corrupted_line_is_flagged_and_no_other(self):
        self.plugin()
        lines = [text for text, _ in ORIGINAL_BODY_LINES]
        expected = [i for i, (_, corrupted) in enumerate(ORIGINAL_BODY_LINES) if corrupted]
        self.assertEqual(len(expected), 16)
        flagged, _ = self.sk012_lines(lines)
        self.assertEqual(flagged, expected,
                         "\nmissed: %s\nextra: %s" % ([lines[i] for i in expected if i not in flagged],
                                                      [lines[i] for i in flagged if i not in expected]))

    def test_the_original_version_injection_is_an_sk013_positive(self):
        self.plugin()
        line = ORIGINAL_BODY_LINES[-1][0]
        _, found = self.sk012_lines([line])
        messages = [f.message for f in found if f.id == "SK013"]
        self.assertEqual(len(messages), 1)
        self.assertIn("`Bash(claude --version)`", messages[0])

    def test_intentional_uses_stay_quiet(self):
        self.plugin()
        flagged, _ = self.sk012_lines(INTENTIONAL_LINES)
        self.assertEqual([INTENTIONAL_LINES[i] for i in flagged], [])

    def test_described_tokens_edges(self):
        hits = lambda text: [t for _, t in cl.described_tokens(text)]   # noqa: E731
        self.assertEqual(hits("- **`${CLAUDE_PROJECT_DIR}`** - the project root"), ["${CLAUDE_PROJECT_DIR}"])
        self.assertEqual(hits("`${CLAUDE_EFFORT}` is the active effort level"), ["${CLAUDE_EFFORT}"])
        self.assertEqual(hits("Effort: `${CLAUDE_EFFORT}` (adapt to it)"), ["${CLAUDE_EFFORT}"])
        self.assertEqual(hits("Effort: `${CLAUDE_EFFORT}`."), [])
        self.assertEqual(hits("Run it from `${CLAUDE_PROJECT_DIR}`, not from here."), [])
        self.assertEqual(hits("**`$0`** is the first argument"), ["$0"])
        self.assertEqual(hits("There is no `$ARGUMENTS` in a rule."), ["$ARGUMENTS"])
        self.assertEqual(hits("`$0` / `$1` are positional"), ["$0"])
        self.assertEqual(hits("`$HOME` and `${HOME}` and `$name` are not substituted"), [])
        self.assertEqual(hits("two on one line: **`$0`** and **`$1`**"), ["$0"])       # one hit per line

    def test_sk012_covers_every_substituted_variable(self):
        for var in cl.SUBSTITUTED_VARS:
            with self.subTest(var=var):
                p = write(self.tmp, "skills/s/SKILL.md", "---\ndescription: d\n---\n- **`${%s}`** - what it is.\n" % var)
                self.assertEqual(self.ids(p), ["SK012"])
        self.assertEqual(set(cl.SUBSTITUTED_VARS), {"CLAUDE_SKILL_DIR", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA",
                                                    "CLAUDE_PROJECT_DIR", "CLAUDE_SESSION_ID", "CLAUDE_EFFORT"})


# ---- SK013: the injection permission check -----------------------------------

# Every row is one headless probe on Claude Code 2.1.295, 2026-10-09: a skill
# whose body holds one injection (the command) and whose frontmatter holds the
# given allowed-tools line(s) or none, loaded in a throwaway plugin with
#   claude -p "Invoke the skill probe:<name> ..." --plugin-dir <dir> --model haiku --allowedTools Skill
# in the default permission mode. True: the permission check passed (the skill
# loaded, or the command ran and merely exited non-zero). False: the load was
# aborted with "Shell command permission check failed". In the probe plugin
# notes.txt sat in the working directory and ${CLAUDE_SKILL_DIR} and
# ${CLAUDE_PLUGIN_ROOT} pointed outside it, as they do for an installed plugin.
OBSERVED = [
    (None, 'echo hi', True),
    (None, "printf 'x\\n'", True),
    (None, 'true', True),
    (None, ':', False),
    (None, 'false || echo fb', True),
    (None, 'cat /etc/hostname', False),
    (None, 'head -1 /etc/hostname', False),
    (None, 'tail -1 /etc/hostname', False),
    (None, 'date', True),
    (None, 'git status', True),
    (None, 'git status --short | head -5', True),
    (None, 'cat /etc/hostname | head -1', False),
    (None, 'ls', True),
    (None, 'pwd', True),
    (None, 'whoami', True),
    (None, 'python3 --version', True),
    (None, "python3 -c 'print(1)'", False),
    (None, 'claude --version', False),
    (None, 'touch probe-touched.txt', False),
    (None, 'node --version', True),
    (None, 'wc -l /etc/hostname', False),
    (None, 'git log --oneline -3', True),
    (None, 'git branch --show-current', True),
    (None, 'git diff --stat', True),
    (None, 'gh --version', False),
    (None, 'env', False),
    (None, 'which python3', True),
    (None, 'test -f x', True),
    (None, 'sleep 0', True),
    (None, 'find . -maxdepth 1', True),
    (None, 'grep -c x /etc/hostname', False),
    (None, 'sed -n 1p /etc/hostname', False),
    (None, 'jq --version', False),
    (None, 'npm --version', False),
    (None, 'cd /tmp && ls', False),
    (None, 'FOO=1 echo hi', False),
    (None, '(echo hi)', False),
    (None, 'echo $(date)', False),
    (None, 'echo hi > /dev/null', True),
    (None, 'echo hi > probe-redirect.txt', False),
    (None, 'date 2>&1', True),
    (None, 'date 2>/dev/null', True),
    (None, 'echo "a || python3 -c 1"', True),
    (None, 'echo $HOME', True),
    (None, 'basename /a/b', True),
    (None, 'sort /etc/hostname', False),
    (None, 'git rev-parse --show-toplevel', True),
    (None, 'hostname', True),
    (None, 'tr a b < /etc/hostname', False),
    (None, 'stat /etc/hostname', False),
    (None, 'cat notes.txt', True),
    (None, 'head -1 notes.txt', True),
    (None, 'cat notes.txt | head -1', True),
    (None, 'wc -l notes.txt', True),
    (None, 'grep -c x notes.txt', True),
    (None, 'sed -n 1p notes.txt', True),
    (None, 'cat "${CLAUDE_SKILL_DIR}/SKILL.md" | head -2', False),
    (None, 'cat ${CLAUDE_PLUGIN_ROOT}/bin/tool.py', False),
    (None, 'ls ${CLAUDE_SKILL_DIR}', False),
    (None, 'cat missing.txt 2>/dev/null || echo fb', True),
    (None, 'git diff', True),
    (None, 'git log', True),
    (None, 'git show --stat HEAD', True),
    (None, 'git remote -v', True),
    (None, 'git config user.name', False),
    (None, 'git branch -a', True),
    (None, 'git tag', True),
    (None, 'git stash list', True),
    (None, 'git ls-files', True),
    (None, 'git describe --tags 2>/dev/null || echo none', True),
    (None, 'git -C . status', False),
    (None, 'uname -a', True),
    (None, 'id', True),
    (None, 'df -h', True),
    (None, 'du -sh .', True),
    (None, 'tree', True),
    (None, 'rg x', True),
    (None, "awk '{print 1}' notes.txt", False),
    (None, 'cut -c1-3 notes.txt', True),
    (None, 'uniq notes.txt', False),
    (None, 'diff notes.txt notes.txt', True),
    (None, 'file notes.txt', True),
    (None, 'realpath .', True),
    (None, 'dirname /a/b', True),
    (None, 'printenv HOME', False),
    (None, 'echo hi | tr a b', True),
    (None, 'seq 3', True),
    (None, 'expr 1 + 1', True),
    (None, '[ -f x ]', True),
    (None, 'ls -la | head -3', True),
    (None, 'date +%F', True),
    (None, 'ls; pwd', True),
    (None, 'echo a && echo b', True),
    (None, "true; python3 -c 'print(1)'", False),
    (None, 'docker --version', False),
    (None, 'cargo --version', False),
    (None, 'go version', False),
    (None, 'ruby --version', False),
    (None, 'pip --version', False),
    (None, 'uv --version', False),
    (None, 'python --version', True),
    (None, 'npx --version', False),
    (None, 'node -v', True),
    (None, 'python3 -V', False),
    (None, 'git --version', False),
    (None, 'make --version', False),
    (None, 'curl --version', False),
    (None, 'curl -s https://example.com', False),
    (None, 'jq . notes.txt', True),
    (None, 'echo hi | xargs echo', True),
    (None, 'ls | wc -l', True),
    (None, 'cat notes.txt | wc -l', True),
    (None, 'command -v python3', False),
    (None, 'type python3', True),
    (None, 'export FOO=1', False),
    (None, '(git status --short 2>/dev/null || echo "no data") | head -30', False),
    (None, '{ git status --short 2>/dev/null || echo no; } | head -30', False),
    (None, 'timeout 5 date', False),
    (None, 'git status --short 2>/dev/null || echo "no data: not a git repository"', True),
    (None, 'git diff --stat 2>/dev/null | head -40', True),
    (None, 'gh pr view --json title 2>/dev/null || echo none', False),
    (None, 'git log --oneline -5 2>/dev/null || echo none', True),
    (None, 'ls -R', True),
    (None, "find . -name '*.md' | head", True),
    (None, 'find . -exec echo {} \\;', False),
    (None, 'sed -i s/a/b/ notes.txt', False),
    (None, 'git add .', False),
    (None, 'git fetch', False),
    (None, 'git stash', False),
    (None, 'sort notes.txt | uniq -c', True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3:*)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 -c *)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3)', "python3 -c 'print(1)'", False),
    ('allowed-tools: Bash', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python *)', "python3 -c 'print(1)'", False),
    ('allowed-tools: Bash(pyth*)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(pyth *)', "python3 -c 'print(1)'", False),
    ("allowed-tools: Bash(python3 -c 'print(1)')", "python3 -c 'print(1)'", True),
    ("allowed-tools: Bash(python3 -c 'print(1)' *)", "python3 -c 'print(1)'", False),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' | head -1", True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' | node -e 'process.stdin.pipe(process.stdout)'", False),
    ('allowed-tools: Bash(python3 *), Bash(node *)', "python3 -c 'print(1)' | node -e 'process.stdin.pipe(process.stdout)'", True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' 2>/dev/null || echo fb", True),
    ('allowed-tools: Bash(python3 *)', "FOO=1 python3 -c 'print(1)'", False),
    ('allowed-tools: Bash(FOO=1 python3 *)', "FOO=1 python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', "(python3 -c 'print(1)' 2>/dev/null || echo fb) | head -5", False),
    ('allowed-tools: Bash', "(python3 -c 'print(1)' 2>/dev/null || echo fb) | head -5", True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' 2>&1", True),
    ('allowed-tools: [Read, "Bash(python3 *)"]', "python3 -c 'print(1)'", True),
    ('allowed-tools:\n  - Read\n  - Bash(python3 *)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Read, Bash(python3 *)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Read Bash(python3 *)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" stamp *)', 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" stamp 1 2>/dev/null || echo fb', True),
    ('allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/bin/tool.py stamp *)', 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" stamp 1 2>/dev/null || echo fb', False),
    ('allowed-tools: Bash(python3 * stamp *)', 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" stamp 1 2>/dev/null || echo fb', True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' > probe-out.txt", False),
    ('allowed-tools: Bash(python3 *)', "echo $(python3 -c 'print(1)')", False),
    ('allowed-tools: Bash(python3 *)', "echo 'a; b' ; python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', "date\npython3 -c 'print(1)'", True),
    (None, "date\npython3 -c 'print(1)'", False),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' && node -e 'console.log(2)'", False),
    ('allowed-tools: Bash(claude --version *)', 'claude --version 2>/dev/null || echo unknown', True),
    ('allowed-tools: Bash(claude --version)', 'claude --version 2>/dev/null || echo unknown', True),
    ('allowed-tools: Bash(claude *)', 'claude --version 2>/dev/null || echo unknown', True),
    ('allowed-tools: "Bash(python3 *)"', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(* -c *)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(*)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(echo *)', "python3 -c 'print(1)'", False),
    ('allowed-tools: Bash(git *)', 'git -C . status', True),
    ('allowed-tools: Bash(python3 *)', "{ python3 -c 'print(1)'; }", False),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' | tee probe-tee.txt", False),
    ('allowed-tools: Bash(python3 -c:*)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', "timeout 5 python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(timeout 5 python3 *)', "timeout 5 python3 -c 'print(1)'", True),
    ('allowed-tools:\n  - "Bash(python3 \\"${CLAUDE_PLUGIN_ROOT}/bin/tool.py\\" stamp *)"', 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" stamp 1 2>/dev/null || echo fb', True),
    ('allowed-tools: Bash(python3 *)', 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" stamp 1 2>/dev/null || echo fb', True),
    (None, 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" stamp 1 2>/dev/null || echo fb', False),
    ('allowed-tools: Read', "python3 -c 'print(1)'", False),
    ("allowed-tools: Bash(python3 -c 'print(1)' 2>/dev/null *)", "python3 -c 'print(1)' 2>/dev/null || echo fb", False),
    ('allowed-tools: Bash(*)', "(python3 -c 'print(1)' 2>/dev/null || echo fb) | head -5", True),
    ('allowed-tools: Bash(FOO=1 *)', "FOO=1 python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(echo *)', 'FOO=1 echo hi', False),
    ('allowed-tools: Bash(python3 *)', 'cd "${CLAUDE_PLUGIN_ROOT}" && python3 bin/tool.py x', False),
    ('allowed-tools: Bash(cat *)', 'cat "${CLAUDE_SKILL_DIR}/SKILL.md" | head -2', False),
    ('allowed-tools: Read', 'cat "${CLAUDE_SKILL_DIR}/SKILL.md" | head -2', False),
    ('allowed-tools: Bash(claude --version *)', 'claude --version', True),
    ('allowed-tools: Bash(claude --version *)', 'claude --version || echo x', True),
    ("allowed-tools: Bash(python3 -c 'print(1)' *)", "python3 -c 'print(1)' 2>/dev/null", False),
    ('allowed-tools: Bash(npm --version *)', 'npm --version', True),
    ('allowed-tools: Bash(gh *)', 'gh', True),
    ('allowed-tools: Bash(claude --version:*)', 'claude --version', True),
    ('allowed-tools: Bash', "echo $(python3 -c 'print(1)')", True),
    ('allowed-tools: Bash', 'cat "${CLAUDE_SKILL_DIR}/SKILL.md" | head -2', True),
    ('allowed-tools: Bash', "python3 -c 'print(1)' > probe-out.txt", True),
    ('allowed-tools: Bash', 'cd "${CLAUDE_PLUGIN_ROOT}" && python3 bin/tool.py x', True),
    ('allowed-tools: Bash(python3 *)', "time python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', "nice python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', "nohup python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', "command python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', "env python3 -c 'print(1)'", False),
    ('allowed-tools: Bash', "FOO=1 python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(cat:*)', 'cat ${CLAUDE_PLUGIN_ROOT}/bin/tool.py', False),
    ('allowed-tools: Bash(cat *)', 'cat ${CLAUDE_PLUGIN_ROOT}/bin/tool.py', False),
    ('allowed-tools: Bash(python3 -c "print(1)")', "python3 -c 'print(1)'", False),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)'; python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', 'python3', True),
    ('allowed-tools: Bash(python3:*)', "python3 -c 'print(1)' && echo ok", True),
    ('allowed-tools: Read(${CLAUDE_SKILL_DIR}/**)', 'cat "${CLAUDE_SKILL_DIR}/SKILL.md" | head -2', False),
    ('allowed-tools: Bash(*)', 'cat "${CLAUDE_SKILL_DIR}/SKILL.md" | head -2', True),
    ('allowed-tools: Bash(python3 *)', "PYTHONPATH=. python3 -c 'print(1)'", False),
    ('allowed-tools: Bash(npm --version)', 'npm --version 2>&1', True),
    ('allowed-tools: Bash(npm *)', 'NODE_ENV=test npm --version', True),
    ('allowed-tools: Bash(python3 -c *)', 'python3 -cprint(1)', False),
    ('allowed-tools: Bash(python3  *)', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 * )', "python3 -c 'print(1)'", True),
    ('allowed-tools: bash(python3 *)', "python3 -c 'print(1)'", False),
    ('allowed-tools: Bash(python3 *) Read', "python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' &", False),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' <<< hi", True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' < notes.txt", True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' >> probe-out.txt", False),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' 2> probe-err.txt", False),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' &> /dev/null", True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' > /dev/null 2>&1", True),
    ('allowed-tools: Bash(python3 *)', "python3 -c 'print(1)' |& head -1", True),
    (None, 'cat ./notes.txt', True),
    (None, 'cat ~/.bashrc 2>/dev/null || echo none', False),
    (None, 'head -5 README.md 2>/dev/null || echo none', True),
    (None, 'ls ~', False),
    (None, 'ls ..', False),
    (None, 'ls /tmp | head -2', False),
    (None, 'test -f "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" && echo yes', True),
    (None, '[ -d .git ] && echo yes || echo no', True),
    (None, 'ls *.txt 2>/dev/null | head -5', True),
    (None, 'cat package.json 2>/dev/null | head -20 || echo none', True),
    (None, 'pwd && git branch --show-current 2>/dev/null', True),
    (None, 'head -c 100 notes.txt', True),
    (None, 'tail -n 5 notes.txt', True),
    (None, 'nl notes.txt', True),
    (None, 'tac notes.txt', True),
    (None, 'jq -r .name package.json 2>/dev/null || echo none', True),
    (None, 'stat notes.txt', True),
    (None, 'md5sum notes.txt', True),
    (None, 'sha256sum notes.txt', True),
    (None, 'nproc', True),
    (None, 'free -m', True),
    (None, 'ps', True),
    (None, 'uptime', True),
    (None, 'cal', True),
    (None, 'locale', True),
    (None, 'groups', True),
    (None, 'arch', True),
    (None, 'printenv', False),
    (None, 'git blame notes.txt 2>/dev/null || echo none', True),
    (None, 'git shortlog -sn', True),
    (None, 'git reflog', True),
    (None, 'git worktree list', True),
    (None, 'git status -sb', True),
    (None, 'git diff HEAD --name-only', True),
    (None, 'git merge-base HEAD HEAD', True),
    (None, 'git rev-list --count HEAD', True),
    (None, 'git cat-file -p HEAD', True),
    (None, 'git grep x', True),
    (None, 'git for-each-ref', True),
    (None, 'git config --get remote.origin.url 2>/dev/null || echo none', True),
    (None, 'git ls-remote 2>/dev/null || echo none', True),
    (None, 'npm ls 2>/dev/null || echo none', False),
    (None, 'pip list 2>/dev/null | head -3', False),
    (None, 'gh pr list 2>/dev/null || echo none', False),
    (None, 'docker ps 2>/dev/null || echo none', True),
    (None, 'kubectl get pods 2>/dev/null || echo none', False),
    (None, "node -e 'console.log(1)'", False),
    (None, 'python3 -m json.tool notes.txt 2>/dev/null || echo none', False),
    (None, 'echo "${CLAUDE_PLUGIN_ROOT}"', True),
    (None, 'git rev-parse --abbrev-ref HEAD', True),
    (None, 'git rev-parse HEAD', True),
    (None, 'git status --porcelain', True),
    (None, 'git diff --cached --stat', True),
    (None, 'git diff main...HEAD --stat 2>/dev/null || echo none', True),
    (None, 'git log -1 --format=%s', True),
    (None, 'git branch', True),
    (None, 'git remote get-url origin 2>/dev/null || echo none', False),
    (None, 'git show HEAD --name-only', True),
    (None, 'git diff --name-only', True),
    (None, 'ls -1 src 2>/dev/null || echo none', True),
    (None, "find . -type f -name '*.py' -maxdepth 2 | head -20", True),
    (None, 'grep -rn TODO . 2>/dev/null | head -5', True),
    (None, 'wc -l < notes.txt', True),
    (None, 'date -u +%Y-%m-%dT%H:%M:%SZ', True),
    (None, 'uname', True),
    (None, 'false', True),
    (None, 'exit 0', False),
    (None, 'cat notes.txt | grep alpha | head -1', True),
    (None, 'echo hi | sed s/h/j/', True),
    (None, "echo hi | awk '{print $1}'", False),
    (None, 'echo hi | cut -c1', True),
    (None, "echo hi | python3 -c 'import sys'", False),
    (None, 'basename "$PWD"', False),
    (None, 'basename $(pwd)', False),
    (None, 'printf \'%s\\n\' "$USER"', False),
    (None, 'read x', False),
    (None, 'cat', True),
    (None, 'yes | head -1', False),
    (None, 'tree -L 2 2>/dev/null || echo none', True),
    (None, "bash -c 'echo hi'", False),
    (None, "sh -c 'echo hi'", False),
    (None, 'eval echo hi', False),
    (None, 'source x 2>/dev/null || echo none', False),
    (None, 'xargs --version', False),
    (None, 'node --version 2>/dev/null || echo none', True),
    (None, 'python3 --version 2>&1 | head -1', True),
    (None, 'npm -v', False),
    (None, 'ruby -v', False),
    (None, 'java -version 2>&1 | head -1', False),
    ('allowed-tools: Bash(basename *)', 'basename "$PWD"', False),
    ('allowed-tools: Bash', 'basename "$PWD"', True),
    (None, 'echo "$HOME"', True),
    (None, 'echo "hi $USER"', True),
    ('allowed-tools: Bash', "python3 -c 'print(1)' &", True),
    ("allowed-tools: Bash(python3 -c 'print(1)' *)", "python3 -c 'print(1)' extra", False),
    ("allowed-tools: Bash(python3 -c 'print(1)'*)", "python3 -c 'print(1)'", True),
    ("allowed-tools: Bash(python3 -c 'print(*)", "python3 -c 'print(1)'", True),
    ("allowed-tools: Bash(python3 -c 'print*)", "python3 -c 'print(1)'", True),
    ("allowed-tools: Bash(node -e 'console.log(1)' *)", "node -e 'console.log(1)' 2>/dev/null || echo fb", False),
    ("allowed-tools: Bash(python3 -c 'print(1)':*)", "python3 -c 'print(1)'", True),
    (None, 'NODE_ENV=test echo hi', True),
    ('allowed-tools: Bash(npm *)', 'LC_ALL=C npm --version', True),
    ('allowed-tools: Bash(npm *)', 'TZ=UTC npm --version', True),
    ('allowed-tools: Bash(npm *)', 'NO_COLOR=1 npm --version', True),
    ('allowed-tools: Bash(npm *)', 'LANG=C npm --version', True),
    ('allowed-tools: Bash(npm *)', 'PYTHONUNBUFFERED=1 npm --version', True),
    ('allowed-tools: Bash(npm *)', 'CI=1 npm --version', True),
    (None, 'TZ=UTC date', True),
    (None, 'LC_ALL=C sort notes.txt', True),
    (None, 'git -c core.pager=cat log -1', False),
    (None, 'git --no-pager log -1', False),
    (None, 'git show', True),
    (None, 'git status --short | wc -l', True),
    (None, 'git log --oneline | head', True),
    (None, 'git config --list', False),
    (None, 'git stash show 2>/dev/null || echo none', True),
    (None, 'git branch -r', True),
    (None, 'git tag -l', True),
    (None, 'git rev-parse --short HEAD', True),
    (None, 'git symbolic-ref --short HEAD', False),
    (None, 'git ls-tree HEAD', False),
    (None, 'git check-ignore x || echo no', False),
    (None, 'git diff | head -100', True),
    (None, 'git describe --always', True),
    (None, 'ls -la .claude 2>/dev/null || echo none', True),
    (None, 'cat .claude/settings.json 2>/dev/null || echo none', True),
    (None, 'cat CLAUDE.md 2>/dev/null | head -50', True),
    (None, 'find . -name SKILL.md | wc -l', True),
    (None, 'rg --files | head', False),
    (None, 'wc -c notes.txt', True),
    (None, 'ls -t | head -1', True),
    (None, 'cat notes.txt | sort | uniq', True),
    (None, 'cat notes.txt | tr a-z A-Z', True),
    (None, 'cat notes.txt | xargs echo', True),
    (None, 'column -t notes.txt', True),
    (None, 'paste notes.txt', True),
    (None, 'rev notes.txt', True),
    (None, 'cmp notes.txt notes.txt', True),
    (None, 'test -n "$CI" && echo ci || echo no', False),
    (None, 'echo ${CI:-none}', False),
    (None, 'echo $((1+1))', True),
    (None, 'id -un', True),
    (None, 'hostname -s', True),
    (None, 'which git node', True),
    (None, 'uname -m', True),
    (None, 'cat /proc/version', False),
    (None, 'df .', True),
    (None, "sed -n '1,5p' notes.txt", True),
    (None, "grep -E 'a|b' notes.txt", True),
    (None, 'jq . package.json 2>/dev/null || echo none', True),
    (None, 'echo \'{"a":1}\' | jq .a', True),
    (None, 'cat notes.txt | tee /dev/null', False),
    (None, 'ls -la', True),
    (None, 'ls skills 2>/dev/null | head -20 || echo none', True),
    (None, 'fold -w 3 notes.txt', True),
    (None, 'comm notes.txt notes.txt', True),
    (None, 'od -c notes.txt | head -2', True),
    (None, 'strings notes.txt', True),
    (None, 'xxd notes.txt | head -1', False),
    (None, 'true && echo ok', True),
    (None, 'echo a; echo b; echo c', True),
    (None, 'test -e notes.txt && cat notes.txt || echo none', True),
    (None, 'grep -q alpha notes.txt && echo found', True),
    (None, 'ls | grep -v x | sort | head -3', True),
    (None, 'echo hi 1>&2', True),
    (None, 'echo hi >&2', True),
    (None, 'echo ~', True),
    (None, 'cat *.txt', True),
    (None, 'mkdir -p probe-d', False),
    (None, 'rm -f probe-none', False),
    (None, 'cp notes.txt probe-c.txt', False),
    (None, 'mv probe-none x 2>/dev/null || echo none', False),
    (None, 'chmod +x notes.txt', False),
    (None, 'ln -s a b', False),
    (None, 'cd .git && ls', True),
    (None, 'basename $PWD', False),
    ('allowed-tools: Bash(test *)', 'test -n "$CI" && echo ci || echo no', False),
    (None, 'find /etc -maxdepth 1 | head -2', False),
    (None, 'find "${CLAUDE_SKILL_DIR}" -name \'*.md\'', False),
    (None, 'git tag --sort=-creatordate', True),
    (None, 'git branch --list', True),
    (None, 'git log --oneline -5 --no-merges', True),
    (None, 'cat "${CLAUDE_PROJECT_DIR}/notes.txt"', True),
    (None, 'git diff HEAD~1 2>/dev/null || echo none', True),
    (None, 'echo hi>/dev/null', True),
    ('allowed-tools: Bash(pyth:*)', "python3 -c 'print(1)'", False),
    (None, 'diff "${CLAUDE_SKILL_DIR}/SKILL.md" notes.txt || echo differs', False),
    (None, 'md5sum "${CLAUDE_SKILL_DIR}/SKILL.md"', False),
    (None, 'jq . "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json"', False),
    (None, 'grep -c name "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json"', False),
    (None, 'git branch -d nope 2>/dev/null || echo none', False),
    (None, 'git tag v-probe', False),
    (None, 'git remote show origin 2>/dev/null || echo none', False),
    (None, 'uniq -c notes.txt', False),
    (None, 'sort -u notes.txt', True),
    (None, 'ls -la "${CLAUDE_PROJECT_DIR}"', True),
    (None, 'printf "%s\\n" hi', True),
    (None, 'echo "a b" | wc -w', True),
    (None, 'ls "my dir" 2>/dev/null || echo none', True),
    ('allowed-tools: Bash(python3 *)', 'python3 -c "print(1)"', True),
    ('allowed-tools: Bash(git status *)', 'timeout 5 git status', True),
    (None, 'time date', False),
    ('allowed-tools: Bash(basename *)', 'basename $PWD', False),
    (None, 'echo $PWD | wc -c', False),
    (None, 'cat notes.txt # a comment', True),
    ('allowed-tools: Bash(python3 *)', 'python3 x.py 2>/dev/null || echo "no data: x || y; z"', True),
    ('allowed-tools: Bash(cat *)', 'cat ~/.bashrc 2>/dev/null || echo none', False),
    (None, 'head -20 "${CLAUDE_SKILL_DIR}/SKILL.md" 2>/dev/null || echo none', False),
    ('allowed-tools: Bash(head *)', 'head -3 "${CLAUDE_SKILL_DIR}/SKILL.md" 2>/dev/null || echo none', False),
    ('allowed-tools: Bash(head -3 "${CLAUDE_SKILL_DIR}/SKILL.md")', 'head -3 "${CLAUDE_SKILL_DIR}/SKILL.md" 2>/dev/null || echo none', False),
    (None, 'ls nonexistent-zz 2>/dev/null', True),
    (None, 'ls nonexistent-zz 2>/dev/null | head -1', True),
    (None, 'ls nonexistent-zz 2>/dev/null; true', True),
    (None, 'ls nonexistent-zz 2>/dev/null || true', True),
    (None, 'ls nonexistent-zz', True),
    (None, 'ls nonexistent-zz 2>&1', True),
    (None, 'ls nonexistent-zz || echo fb', True),
    (None, 'git status --short 2>/dev/null', True),
    (None, 'ls nonexistent-zz 2>/dev/null\necho after', True),
    (None, 'grep -c zzz notes.txt', True),
    ('allowed-tools: Bash(python3 -c *)', "python3 -c 'import sys; sys.exit(3)' 2>/dev/null", True),
    (None, 'test -f nope && echo yes', True),
    (None, 'git status --short | head -5 || echo none', True),
    (None, 'git log --oneline -10 2>/dev/null | head -5', True),
    (None, 'ls -la src 2>/dev/null | head -10 || echo "no src"', True),
    (None, 'cat package.json 2>/dev/null | jq -r .version || echo unknown', True),
    (None, 'git diff --stat HEAD~3 2>/dev/null | tail -1 || echo none', True),
    ('allowed-tools: Bash(gh pr view *)', 'gh pr view --json title 2>/dev/null || echo none', True),
    ('allowed-tools: Bash(gh *)', 'gh pr diff 2>/dev/null | head -100 || echo none', True),
    ('allowed-tools: Bash(gh pr *)', 'gh issue list 2>/dev/null || echo none', False),
    ('allowed-tools: Bash(npm run *)', 'npm run lint --silent 2>&1 | tail -5', True),
    ('allowed-tools: Bash(npm:*)', 'npm ls --depth=0 2>/dev/null | head -20', True),
    ('allowed-tools:\n  - Bash(git add *)\n  - Bash(git commit *)', 'git add -n . 2>/dev/null || echo none', True),
    ('allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/x.py" *)', 'python3 "${CLAUDE_SKILL_DIR}/x.py" --flag 2>/dev/null || echo fb', True),
    ('allowed-tools: Bash(python3 "${CLAUDE_SKILL_DIR}/x.py")', 'python3 "${CLAUDE_SKILL_DIR}/x.py" --flag 2>/dev/null || echo fb', False),
    ('allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/x.py *)', 'python3 ${CLAUDE_SKILL_DIR}/x.py a 2>/dev/null || echo fb', True),
    (None, 'wc -l "${CLAUDE_SKILL_DIR}/SKILL.md"', False),
    (None, 'test -d "${CLAUDE_SKILL_DIR}/references" && echo yes || echo no', True),
    (None, 'ls ~/.claude 2>/dev/null | head -3 || echo none', False),
    (None, 'head -3 /etc/os-release', False),
    (None, 'grep -c "/api" notes.txt || echo 0', True),
    (None, "sed -n '/alpha/p' notes.txt", False),
    (None, "tr '/' '-' < notes.txt", True),
    (None, 'git branch --show-current 2>/dev/null || echo "(detached)"', True),
    (None, 'echo "Today: $(date +%F)"', True),
    (None, 'echo ${HOME}', False),
    (None, 'echo $HOME $USER', False),
    (None, 'echo $HOME; echo $USER', False),
    (None, 'git status 2>/dev/null || echo "$USER"', False),
    ('allowed-tools: Bash(python3 *)', "time python3 -c 'print(1)' 2>/dev/null || echo fb", True),
    ('allowed-tools: Bash(python3 *)', "nohup nice python3 -c 'print(1)'", True),
    ('allowed-tools: Bash(python3 *)', "LC_ALL=C TZ=UTC python3 -c 'print(1)'", True),
    (None, 'CI=1 git status --short', True),
    ('allowed-tools: Bash(node *)', "node -e 'console.log(1)' | python3 -c 'import sys;print(sys.stdin.read())'", False),
    ('allowed-tools: Bash(make test)', 'make test 2>&1 | tail -3', True),
    ('allowed-tools: Bash(make *)', 'make -n build > /dev/null 2>&1 || echo none', True),
    (None, "find . -name '*.md' -newer notes.txt | wc -l", True),
    (None, "find . -name '*.tmp' -delete", False),
    (None, 'git stash list | head -3', True),
    (None, 'git remote -v | head -2', True),
    (None, 'git tag --contains HEAD 2>/dev/null | head -3', True),
    (None, 'git branch -vv', True),
    (None, 'git log --since="2 weeks ago" --oneline | wc -l', True),
    (None, 'git show --stat --oneline HEAD | head -20', True),
    (None, 'du -sh node_modules 2>/dev/null || echo none', True),
    (None, 'sort -u notes.txt | wc -l', True),
    ('allowed-tools: Bash(jq *)', 'jq --version', True),
    (None, 'uname -s | tr A-Z a-z', True),
    (None, 'date +%s; sleep 0; date +%s', True),
    ('allowed-tools: Bash(curl *)', 'curl -s -m 2 https://example.invalid 2>/dev/null || echo offline', True),
    ('allowed-tools: Bash(python3 -m pytest *)', 'python3 -m pytest --co -q 2>/dev/null | tail -1 || echo none', True),
    ('allowed-tools: Bash(python3 *)', 'python3 -c "print(\'a|b\')"', True),
    (None, "echo 'its; fine' | wc -c", True),
    ('allowed-tools: Bash(git commit *)', 'git commit --dry-run 2>/dev/null | head -3 || echo none', True),
    (None, 'ls -1 *.txt | head -3; echo done', True),
    (None, 'cat notes.txt nonexistent 2>/dev/null; true', True),
    (None, '[ -f notes.txt ] && wc -l notes.txt || echo none', True),
    ('allowed-tools: Bash(*)', 'echo ${X:-d}', True),
    (None, 'cd .git; ls | head -2', True),
    (None, 'cat < notes.txt', True),
    (None, 'cat < /etc/hostname', False),
    ('allowed-tools: Bash(python3 -c *)', "python3 -c 'print(1)' 2>/dev/null >/dev/null; echo done", True),
    (None, 'echo "v: $(python3 -c \'print(1)\')"', False),
    ('allowed-tools: Bash(python3 *)', 'echo "v: $(python3 -c \'print(1)\')"', False),
    (None, 'echo "x $(date)" | wc -c', True),
    (None, 'git status 2>/dev/null || echo "none $(date)"', True),
    (None, 'printf "%s" "$(date)"', False),
    (None, 'basename "$(pwd)"', False),
    (None, 'echo $USER', False),
    (None, 'echo $PWD', False),
    (None, 'echo "$HOME" "$USER"', False),
    (None, 'echo $HOME | wc -c', True),
    (None, 'echo "$PWD" | wc -c', False),
    (None, 'echo $HOME $HOME', True),
    (None, 'echo $CI', False),
    (None, 'echo "$CI"', False),
    (None, 'echo "a $HOME b $USER c"', True),
    (None, 'git status 2>/dev/null || echo "$HOME"', True),
    (None, 'echo hi; echo "$HOME"', True),
    (None, 'echo "${HOME}"', False),
    (None, 'echo $MY_UNSET_VAR_ZZ', False),
    (None, 'echo "$MY_UNSET_VAR_ZZ"', False),
    (None, "sed -n '2p' notes.txt", True),
    (None, "sed 's/a/b/' notes.txt", False),
    (None, "sed -e 's/a/b/' -e 's/c/d/' notes.txt", False),
    (None, "sed '/x/d' notes.txt", False),
    (None, "sed -n '$p' notes.txt", False),
    (None, 'git branch --contains HEAD', True),
    (None, 'git branch --merged', True),
    (None, 'git tag -n1', False),
    (None, 'git branch -a --sort=-committerdate | head -3', True),
    (None, 'echo "$(git rev-parse --short HEAD)"', False),
    (None, 'echo "branch: $(git branch --show-current) at $(date +%F)"', True),
    (None, 'echo "$(cat /etc/hostname)"', False),
    (None, 'echo `date`', False),
    (None, 'echo "`date`"', False),
    (None, 'git log --oneline -5 2>/dev/null || echo "no commits"', True),
    (None, 'git diff --name-only HEAD 2>/dev/null | head -50 || echo none', True),
    (None, 'ls -1 .claude/skills 2>/dev/null | head -20 || echo "(none)"', True),
    (None, 'cat .claude/settings.json 2>/dev/null | head -c 2000 || echo "{}"', True),
    (None, "find . -maxdepth 2 -name '*.md' -not -path './node_modules/*' | head -30", True),
    (None, 'wc -l CLAUDE.md 2>/dev/null || echo "0 CLAUDE.md"', True),
    (None, 'echo "cwd: $PWD"', True),
    (None, 'echo "user=$USER home=$HOME"', True),
    (None, 'echo "$HOME/.claude"', True),
    (None, 'ls $HOME', False),
    (None, 'test -d $HOME/.claude && echo yes || echo no', True),
    (None, 'echo "count: $(ls | wc -l)"', False),
    (None, 'echo "$(date) is now"', True),
    (None, 'echo "today is $(date +%A)" | tr a-z A-Z', True),
    (None, 'echo "v: $(node --version) / $(python3 --version)"', True),
    (None, 'echo "v: $(npm --version)"', False),
    ('allowed-tools: Bash(npm *)', 'echo "v: $(npm --version)"', False),
    (None, "git tag -l 'v*' | tail -3", True),
    (None, 'git branch -r --contains HEAD', True),
    (None, 'git describe --tags --abbrev=0 2>/dev/null || echo "no tags"', True),
    (None, "sed -n '1,20p' CLAUDE.md 2>/dev/null || echo none", True),
    (None, "cat notes.txt | sed 's/a/b/'", True),
    (None, "cat notes.txt | sed -e 's/a/b/'", False),
    ('allowed-tools: Bash(sed *)', "sed 's/a/b/' notes.txt", True),
    (None, "head -n 5 notes.txt | cut -d' ' -f1 | sort | uniq -c | sort -rn", True),
    ('allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" *)', 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" a "b c" 2>/dev/null | head -5', True),
    ('allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" *)', 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py"', True),
    ('allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py":*)', 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/tool.py" x', True),
    ('allowed-tools: Read, Grep, Bash(git log *), Bash(gh pr view *)', 'gh pr view 2>/dev/null || git log -1 --oneline', True),
    (None, "ls -la | awk '{print $9}'", False),
    ('allowed-tools: Bash(awk *)', "ls -la | awk '{print $9}'", True),
    (None, 'echo "a" > /dev/stderr', False),
    (None, "git status --short 2>/dev/null | wc -l | tr -d ' '", True),
    (None, 'echo hi | tee /dev/null | wc -c', False),
    (None, 'cat notes.txt | xargs -n1 echo', False),
    (None, 'date "+%Y-%m-%d %H:%M"', True),
    (None, 'echo "${CLAUDE_SKILL_DIR}" | wc -c', True),
    (None, 'true && echo ok || echo bad', True),
    (None, 'ls -d */ 2>/dev/null | head -5 || echo none', True),
    (None, 'pwd | xargs basename', False),
    # ---- second round, the same day and version: write-capable options on
    # read-only commands, and relative paths with `..`. Each probe ran in its
    # own fresh directory <tmp>/proj (a git repository with one commit) holding
    # README.md, sub/README.md, a/x, b and - for the name rows - ..proj, b..,
    # a..b and x/..y, with a sibling <tmp>/other/README.md outside it. tree and
    # column are not installed on the probe machine, so their rows passed the
    # permission check and then exited non-zero, which counts as passed here.
    # NOT in the table, deliberately: `date -s 2020-01-01` with
    # `allowed-tools: Bash(date *)` and `hostname probe-new-name` with
    # `Bash(hostname *)`. Both loaded - that is, both ran, and set the clock and
    # the host name of the machine. Do not replay those two.
    (None, 'sort README.md', True),
    (None, 'sort -r README.md', True),
    (None, 'sort -u -k1,1 README.md', False),
    (None, 'sort -o sorted.txt README.md', False),
    (None, 'sort -osorted.txt README.md', False),
    (None, 'sort --output=sorted.txt README.md', False),
    (None, 'sort --output sorted.txt README.md', False),
    (None, 'sort README.md -o sorted.txt', False),
    (None, 'sort -ro sorted.txt README.md', False),
    (None, 'sort --compress-program=gzip README.md', False),
    (None, 'sort -T . README.md', False),
    (None, 'sort --files0-from=list0', False),
    (None, 'sort --debug README.md', False),
    (None, 'git diff --stat', True),
    (None, 'git diff', True),
    (None, 'git diff --output=out.patch', False),
    (None, 'git diff --output out.patch', False),
    (None, 'git diff --stat --output=out.patch', False),
    (None, 'git log -1 --oneline', True),
    (None, 'git log -1 --output=out.txt', False),
    (None, 'git show --stat HEAD', True),
    (None, 'git show --output=out.txt HEAD', False),
    (None, 'git diff --ext-diff', False),
    (None, 'git diff --no-ext-diff', True),
    (None, 'git grep -n a', True),
    (None, 'git grep -Ocat a', False),
    (None, 'git grep --open-files-in-pager=cat a', False),
    (None, 'git reflog', True),
    (None, 'git reflog expire --all', False),
    (None, 'git reflog delete HEAD@{0}', False),
    (None, 'git ls-remote .', False),
    (None, 'git ls-remote --upload-pack=echo .', False),
    (None, 'git blame --output=x README.md', False),
    (None, 'git status --short', True),
    (None, 'tree -L 1', True),
    (None, 'tree -o tree.txt', False),
    (None, 'date +%Y', True),
    (None, 'date -s 2020-01-01', False),
    (None, 'date --set=2020-01-01', False),
    (None, 'date -u', True),
    (None, 'date -r README.md', True),
    (None, 'hostname', True),
    (None, 'hostname -f', True),
    (None, 'hostname probe-new-name', False),
    (None, 'find . -name README.md', True),
    (None, 'find . -name README.md -fls found.txt', False),
    (None, 'find . -name README.md -fprintf found.txt %p', False),
    (None, 'find . -name README.md -print0', True),
    (None, 'uniq -c', True),
    (None, 'ls -o', True),
    (None, 'ps -o pid', False),
    (None, 'df --output=source', True),
    (None, 'cut --output-delimiter=: -c1-2 README.md', True),
    (None, 'grep -o a README.md', True),
    (None, 'column -o : README.md', True),
    (None, 'head -3 README.md', True),
    (None, 'head -3 sub/README.md', True),
    (None, 'head -3 ./README.md', True),
    (None, 'head -3 ../other/README.md', False),
    (None, 'head -3 sub/../README.md', False),
    (None, 'head -3 sub/../../other/README.md', False),
    (None, 'head -n3 -- ../other/README.md', False),
    (None, 'cat ./a/../b', False),
    (None, 'cat a/../../other/README.md', False),
    (None, 'ls ..', False),
    (None, 'ls ../other', False),
    (None, 'ls sub/..', False),
    (None, 'ls sub/../..', False),
    (None, 'ls .', True),
    (None, 'grep c ../other/README.md', False),
    (None, 'grep -c c README.md ../other/README.md', False),
    (None, 'grep -f ../other/README.md README.md', False),
    (None, 'grep -rn c ..', False),
    (None, 'wc -l < ../other/README.md', False),
    (None, 'wc -l ../other/README.md', False),
    (None, 'stat ../other/README.md', False),
    (None, 'diff README.md ../other/README.md', False),
    (None, 'find .. -maxdepth 1 -name other', False),
    (None, 'find ../other -name README.md', False),
    (None, 'test -f ../other/README.md && echo yes', True),
    (None, 'echo ../other/README.md', True),
    (None, 'tail -1 ../other/README.md', False),
    (None, 'cd .. && ls', False),
    (None, 'cd sub && ls', True),
    (None, 'cd sub && cat ../README.md', False),
    (None, 'cd sub && cat ../../other/README.md', False),
    (None, 'sort ../other/README.md', False),
    (None, 'git diff --no-index README.md ../other/README.md', False),
    (None, 'git log -1 --oneline -- ../other', True),
    (None, 'tree ..', True),
    (None, 'du -s ../other', True),
    (None, 'md5sum ../other/README.md', False),
    (None, 'file ../other/README.md', False),
    (None, 'nl ../other/README.md', False),
    (None, 'head -3 "../other/README.md"', False),
    (None, 'head -3 ..//other/README.md', False),
    (None, 'head -3 ./../other/README.md', False),
    (None, 'basename ../other/README.md', True),
    (None, 'dirname ../other/README.md', True),
    (None, 'realpath ../other/README.md', True),
    (None, 'sort -u README.md', True),
    (None, 'sort -k1,1 README.md', False),
    (None, 'sort -k 1,1 README.md', True),
    (None, 'sort -k1 README.md', False),
    (None, 'sort -k 2 README.md', True),
    (None, 'sort -n README.md', True),
    (None, 'sort -rn README.md', True),
    (None, 'sort -t: -k2 README.md', False),
    (None, 'sort -t : -k 2 README.md', True),
    (None, 'sort -c README.md', True),
    (None, 'sort -u -r README.md', True),
    (None, 'sort --reverse README.md', True),
    (None, 'sort --key=1 README.md', True),
    (None, 'sort -V README.md', True),
    (None, 'sort -f README.md', True),
    (None, 'sort -h README.md', True),
    (None, 'sort -s README.md', True),
    (None, 'sort -S 1M README.md', True),
    (None, 'sort --parallel=2 README.md', True),
    (None, 'sort -m README.md sub/README.md', True),
    (None, 'sort -z README.md', True),
    (None, 'sort -R README.md', True),
    (None, 'sort --random-source=README.md -R README.md', False),
    (None, 'ps aux', True),
    (None, 'ps -ef', True),
    (None, 'ps -o pid,comm', False),
    (None, 'ps e', False),
    (None, 'ps -p 1', True),
    (None, 'git ls-remote', True),
    (None, 'git ls-remote origin', False),
    (None, 'git ls-remote --heads', True),
    (None, 'git ls-remote --heads origin', False),
    (None, 'git diff --no-index README.md sub/README.md', True),
    (None, 'git diff --stat HEAD', True),
    (None, 'git diff --name-only HEAD~1', True),
    (None, 'git log --oneline -3 --stat', True),
    (None, 'git log -p -1 --output=x', False),
    (None, 'git shortlog -sn --output=x', False),
    (None, 'git rev-list --count HEAD', True),
    (None, 'head -3 ../proj/sub/../README.md', False),
    (None, 'head -3 sub/./README.md', True),
    (None, 'cat a/../b', False),
    (None, 'head -3 ../proj/../other/README.md', False),
    (None, 'ls ../proj/..', False),
    (None, 'ls ./..', False),
    (None, 'cat sub/../sub/README.md', False),
    (None, 'ls sub/../sub', False),
    (None, 'cat ..proj', True),
    (None, 'cat b..', True),
    (None, 'ls a..b', True),
    (None, 'cat x/..y', True),
    (None, 'head -3 .../README.md', True),
    (None, 'grep -r c --include=*.md ../other', False),
    (None, 'du -s ..', True),
    (None, 'du -sh ../other', True),
    (None, 'realpath ..', True),
    (None, 'tree ../other', True),
    (None, 'stat ..', False),
    (None, 'git diff -- ../other', False),
    (None, 'git status ..', True),
    (None, 'git ls-files ..', True),
    (None, 'git log -1 --oneline ../other', True),
    (None, 'find . -path ./.. -prune', False),
    (None, 'find . -name ..', True),
    (None, 'tr a b < sub/../README.md', False),
    (None, 'cat README.md ../other/README.md | head -3', False),
    (None, 'cd ../other && ls', False),
    (None, 'cd sub/.. && ls', False),
    (None, 'date -d ../x', True),
    (None, 'tree -o ../t.txt', False),
    ('allowed-tools: Bash(head *)', 'head -3 ../other/README.md', False),
    ('allowed-tools: Bash(head *)', 'head -3 sub/../README.md', False),
    ('allowed-tools: Bash(cat *)', 'cat ./a/../b', False),
    ('allowed-tools: Bash(ls *)', 'ls ..', False),
    ('allowed-tools: Bash(sort *)', 'sort -o sorted.txt README.md', True),
    ('allowed-tools: Bash(sort *)', 'sort -k1,1 README.md', True),
    ('allowed-tools: Bash(git diff *)', 'git diff --output=out.patch', True),
    ('allowed-tools: Bash(git diff:*)', 'git diff --output=out.patch', True),
    ('allowed-tools: Bash(tree *)', 'tree -o tree.txt', True),
    ('allowed-tools: Bash(find *)', 'find . -name README.md -fls found.txt', False),
    ('allowed-tools: Bash(head *)', 'head -3 /etc/hostname', False),
    ('allowed-tools: Bash(git *)', 'git reflog expire --all', True),
    ('allowed-tools: Bash(ps *)', 'ps -o pid', True),
    ('allowed-tools: Bash(git diff *)', 'git diff -- ../other', False),
    ('allowed-tools: Bash(find:*)', 'find . -name README.md -fls found.txt', False),
    ('allowed-tools: Bash(find *)', 'find . -name README.md -exec echo {} \\;', False),
    ('allowed-tools: Bash(find *)', 'find . -name nothing.tmp -delete', False),
    ('allowed-tools: Bash(find *)', 'find . -name README.md -fprint found.txt', False),
    ('allowed-tools: Bash(git log *)', 'git log -1 --output=out.txt', True),
    ('allowed-tools: Bash(git ls-remote *)', 'git ls-remote origin', True),
    ('allowed-tools: Bash(sort *)', 'sort --compress-program=gzip README.md', True),
    ('allowed-tools: Bash(sort *)', 'sort ../other/README.md', False),
    ('allowed-tools: Bash(sort *)', 'sort -o ../other/sorted.txt README.md', False),
    ('allowed-tools: Bash(sort *)', 'sort -o sub/../sorted.txt README.md', False),
    ('allowed-tools: Bash(sort *)', 'sort -o sub/sorted.txt README.md', True),
    (None, 'du -s /etc/hostname', True),
    (None, 'realpath /etc/hostname', True),
    (None, 'tree /etc/hostname', True),
    (None, 'date -r /etc/hostname', True),
    (None, 'git diff ../other', False),
    (None, 'git diff sub/../README.md', False),
    (None, 'git diff -- sub', True),
    (None, 'git show HEAD -- ../other', True),
    (None, 'git blame ../other/README.md', True),
    (None, 'git grep c -- ../other', False),
    (None, 'ps -eo pid', False),
    (None, 'ps axo pid', True),
    (None, 'ps --forest', True),
    (None, 'ps -u root', True),
    (None, 'ps -C sh', True),
    (None, 'hostname -F README.md', False),
    (None, 'hostname -b', False),
    (None, 'hostname -I', True),
    (None, 'date --rfc-3339=seconds', True),
    (None, 'date -d tomorrow +%F', True),
    (None, 'date -I', True),
    (None, 'find . -iname ..', True),
    (None, 'find . -newer ../other/README.md', False),
    (None, 'find . -name README.md -ls', True),
    (None, 'find . -name README.md -printf %p', True),
    (None, 'git log -1 --format=%H', True),
    (None, 'git diff --stat -- README.md', True),
    (None, 'sort -t , -k 2 README.md', True),
    (None, 'sort --field-separator=, --key=2 README.md', True),
    (None, 'sort -nr -k 2 README.md', True),
    (None, 'sort -bfr README.md', True),
    (None, 'sort -uo out.txt README.md', False),
]

# Observed, and knowingly not modelled: a path that climbs out of the working
# directory and straight back in through that directory's own name passed. The
# linter cannot know what the session's working directory will be called, so
# it reports these like any other `..` path. (The directory was named `cwd` in
# the first round and `proj` in the second; `../proj/sub/../README.md` and
# `ls ../proj/..` were rejected, see the table.)
OBSERVED_UNMODELLED = [
    (None, 'cat ../cwd/notes.txt', True),
    (None, 'head -3 ../proj/README.md', True),
    (None, 'ls ../proj', True),
    (None, 'cat ../proj/b', True),
]


class InjectionPermissionTests(TempCase):
    def problems(self, frontmatter, command, **kw):
        fm = cl.parse_frontmatter("---\n" + (frontmatter + "\n" if frontmatter else "") + "---\n")
        kw.setdefault("skill_dir_outside", True)
        return cl.injection_problems(command, fm.get("allowed-tools"), **kw)

    def test_model_reproduces_every_observed_verdict(self):
        self.assertGreater(len(OBSERVED), 550)
        wrong = []
        for frontmatter, command, passed in OBSERVED:
            if (not self.problems(frontmatter, command)) != passed:
                wrong.append((frontmatter, command, "really passed" if passed else "really aborted"))
        self.assertEqual(wrong, [])

    def test_lexer_is_quote_aware(self):
        ops, hazards = cl.split_operations('a "x || y; z | w" \'p && q\' || b 2>/dev/null; c | d |& e\nf')
        self.assertEqual([(o.sep, o.text) for o in ops],
                         [("", 'a "x || y; z | w" \'p && q\''), ("||", "b"), (";", "c"), ("|", "d"), ("|", "e"), ("\n", "f")])
        self.assertEqual(hazards, set())

    def test_redirections_are_dropped_and_classified(self):
        ops, hazards = cl.split_operations("a 2>/dev/null >/dev/null 2>&1 &>/dev/null >&2 x<in.txt y")
        self.assertEqual((ops[0].text, ops[0].reads, ops[0].writes, hazards), ("a x y", ["in.txt"], [], set()))
        for command in ("a > out.txt", "a >> out.txt", "a 2> err.txt", "a &> all.txt", "a>out.txt", 'a > "o ut"'):
            with self.subTest(command=command):
                ops, hazards = cl.split_operations(command)
                self.assertEqual((ops[0].text, hazards), ("a", {"redirect"}))

    def test_structures(self):
        cases = {"(a || echo x) | head": "subshell", "{ a; } | head": "group", "a &": "background",
                 "a > f": "redirect"}
        for command, hazard in cases.items():
            with self.subTest(command=command):
                self.assertEqual(cl.split_operations(command)[1], {hazard})
        self.assertEqual(cl.split_operations(r"find . -exec echo {} \;")[1], set())
        self.assertEqual(cl.split_operations("echo $((1+1)) # (not a subshell)")[1], set())
        ops, _ = cl.split_operations("cat <<EOF\n$(rm -rf /) | x\nEOF\n")
        self.assertEqual([o.text for o in ops], ["cat"])            # a here-document's body is data

    def test_bash_entries_forms(self):
        entries = cl.bash_entries
        self.assertEqual(entries(None), (False, []))
        self.assertEqual(entries("Read, Grep"), (False, []))
        self.assertEqual(entries("Bash"), (True, []))
        self.assertEqual(entries("Read, Bash, Grep"), (True, []))
        self.assertEqual(entries("Bash(*)"), (True, []))
        self.assertEqual(entries("bash(git *)"), (False, []))            # the tool name is case-sensitive
        self.assertEqual(entries("BashOutput, Read"), (False, []))
        self.assertEqual(entries("Read Bash(git log *) Bash(gh pr view:*),Grep"), (False, ["git log *", "gh pr view:*"]))
        self.assertEqual(entries(["Read", "Bash(python3 *)"]), (False, ["python3 *"]))
        stamp = 'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" stamp *)'
        self.assertEqual(entries(stamp + ", Read"), (False, [stamp[5:-1]]))
        self.assertEqual(entries("Bash(python3 -c 'print(1)'), Bash(a (b) c *)"), (False, ["python3 -c 'print(1)'", "a (b) c *"]))
        self.assertEqual(entries("Bash(python3 -c 'print(*)"), (False, ["python3 -c 'print(*"]))
        self.assertEqual(entries("Bash(echo don't *), Bash(ls *)"), (False, ["echo don't *", "ls *"]))
        self.assertEqual(entries("Bash(python3   x.py   *)"), (False, ["python3 x.py *"]))
        self.assertEqual(entries({"nested": True}), (False, []))

    def test_entry_forms_through_real_frontmatter(self):
        for frontmatter in ("allowed-tools: Bash(tool run *)", 'allowed-tools: "Bash(tool run *)"',
                            "allowed-tools: Read, Bash(tool run *)", "allowed-tools: Read Bash(tool run *)",
                            'allowed-tools: [Read, "Bash(tool run *)"]', "allowed-tools:\n  - Read\n  - Bash(tool run *)",
                            'allowed-tools:\n  - "Bash(tool run *)"', "allowed-tools: Bash(tool run:*)",
                            "allowed-tools: Bash", "allowed-tools: [Bash]", "allowed-tools: Bash(tool *) # narrow"):
            with self.subTest(frontmatter=frontmatter):
                self.assertEqual(self.problems(frontmatter, "tool run now 2>/dev/null || echo none"), [])
        for frontmatter in (None, "allowed-tools: Read", "allowed-tools: Bash(tool walk *)", "allowed-tools: bash",
                            "allowed-tools: Bash(tool run)", "allowed-tools: Bash(too *)"):
            with self.subTest(frontmatter=frontmatter):
                self.assertEqual([p.kind for p in self.problems(frontmatter, "tool run now")], ["uncovered"])

    def test_the_message_names_the_entry_to_add_and_it_works(self):
        cases = {
            'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" stamp 2.1.295 2>/dev/null || echo "n/a"':
                'Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" stamp *)',
            "claude --version 2>/dev/null || echo unknown": "Bash(claude --version)",
            "gh pr view --json title,body 2>/dev/null | head -c 4000": "Bash(gh pr view *)",
            "python3 -c 'print(1)'": "Bash(python3 -c *)",
            "FOO=1 npm run build --silent": "Bash(FOO=1 npm run build *)",
            "NODE_ENV=test timeout 5 npm test": "Bash(npm test)",
            "tool 'a (b)' c d": "Bash(tool 'a (b)' c:*)",
            "npm ls": "Bash(npm ls)",
        }
        for command, entry in cases.items():
            with self.subTest(command=command):
                problems = self.problems(None, command)
                self.assertEqual([(p.kind, p.entry) for p in problems], [("uncovered", entry)])
                self.assertIn(f"add `{entry}` to allowed-tools", problems[0].message())
                self.assertEqual(self.problems("allowed-tools: " + entry, command), [])

    def test_suggested_entries_cover_every_uncovered_observed_command(self):
        checked = 0
        for _, command, _ in OBSERVED:
            problems = self.problems(None, command)
            if not problems or any(p.kind != "uncovered" for p in problems):
                continue
            entries = ", ".join(sorted({p.entry for p in problems}))
            checked += 1
            self.assertEqual(self.problems("allowed-tools: " + entries, command), [], (command, entries))
        self.assertGreater(checked, 60)

    def test_outside_and_hazard_messages(self):
        outside = self.problems("allowed-tools: Bash(cat *)", 'cat "${CLAUDE_SKILL_DIR}/notes.md" | head -5')
        self.assertEqual([p.kind for p in outside], ["outside"])
        self.assertIn("does not help", outside[0].message())
        self.assertIn("Read the file", outside[0].message())
        # a project skill's own directory is inside the working directories
        self.assertEqual(self.problems(None, 'cat "${CLAUDE_SKILL_DIR}/notes.md" | head -5', skill_dir_outside=False), [])
        self.assertEqual([p.kind for p in self.problems(None, 'cat "${CLAUDE_PLUGIN_ROOT}/x"', skill_dir_outside=False)],
                         ["outside"])
        hazard = self.problems("allowed-tools: Bash(git *)", '(git status --short 2>/dev/null || echo "no data") | head -30')
        self.assertEqual([(p.kind, p.detail) for p in hazard], [("hazard", "subshell")])
        self.assertIn("only blanket `Bash` passes", hazard[0].message())
        self.assertEqual(self.problems("allowed-tools: Bash", '(git status || echo "no data") | head -30 > out.txt &'), [])

    def test_preprocessor_tokens_are_not_shell_expansions(self):
        self.assertEqual(self.problems(None, "git log --oneline -5 $ARGUMENTS"), [])
        self.assertEqual(self.problems(None, "git log --oneline -$0 $1"), [])
        self.assertEqual(self.problems(None, 'grep -c x "${CLAUDE_PROJECT_DIR}/notes.txt"'), [])
        self.assertEqual([p.detail for p in self.problems(None, "git log $branch")], ["expansion"])
        self.assertEqual(self.problems(None, "git log $branch", argument_names=("branch",)), [])
        self.assertEqual(self.problems(None, "echo 'costs $5 and $USER stays literal'"), [])

    def test_uncovered_injection_parts_keeps_its_contract(self):
        f = cl.uncovered_injection_parts
        self.assertEqual(f('python3 x.py a 2>/dev/null || echo "no"', "Bash(python3 x.py *)"), [])
        self.assertEqual(f('python3 x.py a 2>/dev/null || echo "no"', "Read"), ["python3 x.py a"])
        self.assertEqual(f("git status", "Bash, Read"), [])
        self.assertEqual(f("npm test", ["Bash(npm test:*)"]), [])
        self.assertEqual(f('echo "hi"', ""), [])
        self.assertEqual(f("a 2>/dev/null || b || echo x", "Bash(a *)"), ["b"])
        self.assertEqual(f("a; a; a", None), ["a"])

    def test_through_the_linter(self):
        self.plugin()
        inject = f'Version: !{BT}python3 tool.py stamp 1 2>/dev/null || echo "n/a"{BT}\n'

        def skill(front, body=inject, rel="skills/s/SKILL.md"):
            return write(self.tmp, rel, f"---\ndescription: d\n{front}---\n{body}")

        found = [f for f in self.findings(skill("")) if f.id == "SK013"]
        self.assertEqual([(f.severity, f.line) for f in found], [("warn", 4)])
        self.assertIn("add `Bash(python3 tool.py stamp *)` to allowed-tools", found[0].message)
        for front in ("allowed-tools: Bash(python3 tool.py *)\n", "allowed-tools:\n  - Read\n  - Bash(python3 tool.py stamp *)\n",
                      'allowed-tools: [Read, "Bash(python3 *)"]\n', "allowed-tools: Bash\n"):
            with self.subTest(front=front):
                self.assertEqual(self.ids(skill(front)), [])
        # read-only commands need no entry at all
        self.assertEqual(self.ids(skill("", f"!{BT}git status --short 2>/dev/null | head -20 || echo none{BT}\n")), [])
        # ${CLAUDE_SKILL_DIR}: outside for a plugin skill, inside for a project skill
        body = f'!{BT}head -20 "${{CLAUDE_SKILL_DIR}}/notes.md" 2>/dev/null || echo none{BT}\n'
        self.assertEqual(self.ids(skill("", body)), ["SK013"])
        project = os.path.join(self.tmp, "proj")
        self.assertEqual(self.ids(write(project, ".claude/skills/s/SKILL.md", f"---\ndescription: d\n---\n{body}")), [])
        # declared argument names are substituted before the shell sees them
        body = f"!{BT}git log --oneline -5 $branch 2>/dev/null || echo none{BT}\n"
        self.assertEqual(self.ids(skill("", body)), ["SK013"])
        self.assertEqual(self.ids(skill("arguments: [issue, branch]\n", body)), [])
        self.assertEqual(self.ids(skill("arguments: issue branch\n", body)), [])


# ---- reasons, reference tables and the checks they drive -------------------------

class ReasonTests(TempCase):
    def test_every_rule_has_a_reason(self):
        data = json.loads(run("rules", "--json").stdout)
        for rule in data["rules"]:
            with self.subTest(rule=rule["id"]):
                self.assertGreater(len(rule["why"].strip()), 20)
                self.assertFalse(rule["why"].rstrip().endswith("."))    # a clause: messages put it mid-sentence
        self.assertEqual(set(cl.RULE_WHY), {r[0] for r in cl.RULES})
        text = run("rules").stdout
        self.assertEqual(text.count("       why: "), len(cl.RULES))

    def test_findings_say_what_why_and_what_to_do(self):
        p = write(self.tmp, "CLAUDE.md", "line\n" * 312)
        (finding,) = self.findings(p)
        self.assertEqual(
            finding.message,
            "CLAUDE.md is 312 lines; the target is at most 200 - it is paid on every session and longer files dilute "
            "adherence (Claude Code skips an instruction file over 4 MiB outright). Move domain constraints to "
            "path-scoped rules and procedures to skills")
        # the message states the comparison the code performs: 200 lines pass, 201 do not, for a rule file too
        self.assertEqual(self.ids(write(self.tmp, "at/CLAUDE.md", "line\n" * 200)), [])
        for rel, rule_id in (("over/CLAUDE.md", "CM001"), (".claude/rules/long.md", "RU001")):
            (over,) = [f for f in self.findings(write(self.tmp, rel, "# T\n\nApplies when x.\n" + "line\n" * 198))
                       if f.id == rule_id]
            self.assertIn("is 201 lines; the target is at most 200 - ", over.message)
        # Two facts no prose file states any more live in a rule's reason, each once.
        why = {r["id"]: r["why"] for r in json.loads(run("rules", "--json").stdout)["rules"]}
        self.assertIn("over 4 MiB outright", why["CM001"])
        for needle in ("first 5,000 tokens of each skill", "25,000-token budget shared by all skills",
                       "most recently invoked first", "drop out entirely"):
            self.assertIn(needle, why["SK008"])
        text = run("rules").stdout + run("fields", "skill").stdout
        self.assertEqual((text.count("25,000-token"), text.count("4 MiB outright")), (1, 1))
        # one message per rule that is cheap to trip: each carries its measured value or subject, a reason and a fix
        write(self.tmp, ".claude/skills/Bad Name/SKILL.md",
              "---\nname: Bad Name\ndescription: " + "d" * 1600 + "\ndisable-model-invocation: true\n"
              "user-invocable: false\n---\n" + f"!{BT}cat secrets.txt{BT}\nAPI_KEY=abc123\n" + "x\n" * 510
              + "[gone](references/gone.md)\n")
        write(self.tmp, ".claude/rules/r.md", "1. first\n2. then\n$ARGUMENTS\n" + "x\n" * 200)
        write(self.tmp, ".claude/agents/a.md", "---\nname: a\ndescription: d\nbackground: true\n---\n$ARGUMENTS\n")
        seen = {}
        for path in collect_files(self.tmp):
            for f in self.findings(path):
                seen.setdefault(f.id, f.message)
        for rule_id in ("SK001", "SK003", "SK004", "SK005", "SK006", "SK007", "SK008", "SK009",
                        "RU001", "RU002", "RU003", "RU004", "RU005", "AG002", "AG003", "CM001"):
            with self.subTest(rule=rule_id):
                message = seen[rule_id]
                self.assertIn(" - ", message)                       # what - why. what to do
                self.assertGreater(len(message), 80)
                self.assertRegex(message, r"\b(Move|Rename|Put|Cap|End|Fix|Remove|Have|Keep|Split|State|Scope|"
                                          r"Start|Say|Set)\b")

    def test_kinds_map_names_real_rule_files_and_skills(self):
        kinds = json.loads(run("rules", "--json").stdout)["kinds"]
        self.assertEqual(set(kinds), set(cl.KINDS))
        self.assertEqual(kinds["plugin"], {"rule": None, "skill": None})
        mapped = set()
        for kind, entry in kinds.items():
            self.assertEqual(set(entry), {"rule", "skill"})
            if entry["rule"] is None:
                continue
            with self.subTest(kind=kind):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, entry["rule"])), entry["rule"])
                self.assertTrue(os.path.isfile(os.path.join(ROOT, "skills", entry["skill"], "SKILL.md")))
                mapped.add(os.path.basename(entry["rule"]))
        on_disk = {n for n in os.listdir(os.path.join(ROOT, "rules")) if n.endswith(".md")}
        self.assertEqual(mapped, on_disk)                            # every rules/*.md is delivered for some kind
        # and each rule file's own path scope describes the kind it is mapped to
        samples = {"skill": "x/skills/s/SKILL.md", "rule": "x/.claude/rules/r.md", "agent": "x/.claude/agents/a.md",
                   "memory": "x/CLAUDE.md", "hooks": "x/.claude/settings.json"}
        for kind, sample in samples.items():
            with open(os.path.join(ROOT, kinds[kind]["rule"]), encoding="utf-8") as f:
                self.assertTrue(cl.glob_matches(sample, cl.rule_paths(f.read())), kind)
        self.assertIn("kinds:", run("rules").stdout)


def collect_files(root):
    return cl.collect([root])


# Every field name the three reference skills stated before the tables took the data over.
SKILL_FIELDS_IN_PROSE = (
    "name description when_to_use argument-hint arguments disable-model-invocation user-invocable allowed-tools "
    "disallowed-tools model effort context agent background hooks paths shell metadata license compatibility").split()
AGENT_FIELDS_IN_PROSE = (
    "name description color tools disallowedTools permissionMode skills omitClaudeMd memory initialPrompt model "
    "effort maxTurns background isolation experimental mcpServers hooks").split()


class FieldsTests(TempCase):
    def test_tables_hold_every_field_the_prose_stated(self):
        for kind, names in (("skill", SKILL_FIELDS_IN_PROSE), ("agent", AGENT_FIELDS_IN_PROSE), ("rule", ["paths"])):
            data = json.loads(run("fields", kind, "--json").stdout)
            self.assertEqual(sorted(f["field"] for f in data["fields"]), sorted(names), kind)
            self.assertEqual(data["kind"], kind)
            self.assertEqual(data["verified_against"], cl.TABLES_VERIFIED_AGAINST)
            for row in data["fields"]:
                with self.subTest(kind=kind, field=row["field"]):
                    self.assertTrue({"field", "type", "default", "values", "effect", "since"} <= set(row))
                    self.assertTrue(row["type"] and row["default"] and row["effect"])
                    self.assertNotIn("\n", row["effect"])
                    self.assertEqual("plugin" in row, kind == "agent")

    def test_facts_that_must_not_be_lost(self):
        skill = {f["field"]: f for f in json.loads(run("fields", "skill", "--json").stdout)["fields"]}
        agent_data = json.loads(run("fields", "agent", "--json").stdout)
        agent = {f["field"]: f for f in agent_data["fields"]}
        self.assertEqual(skill["effort"]["values"], ["low", "medium", "high", "xhigh", "max"])
        self.assertEqual(skill["shell"]["values"], ["bash", "powershell"])
        self.assertEqual((skill["shell"]["default"], skill["user-invocable"]["default"]), ("bash", "true"))
        self.assertEqual(skill["background"]["since"], "2.1.218")
        self.assertIn("fork", skill["context"]["values"])
        self.assertEqual(agent["color"]["values"],
                         ["red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"])
        self.assertEqual(agent["memory"]["values"], ["user", "project", "local"])
        self.assertEqual(agent["permissionMode"]["values"],
                         ["default", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan", "manual"])
        self.assertEqual(agent["model"]["values"], ["haiku", "sonnet", "opus", "fable", "inherit"])
        self.assertEqual((agent["omitClaudeMd"]["since"], agent["experimental"]["since"]), ("2.1.271", "2.1.248"))
        self.assertEqual(sorted(f for f, row in agent.items() if row["plugin"] == "ignored"),
                         sorted(cl.PLUGIN_AGENT_IGNORED))
        self.assertIn("first 32", agent["skills"]["effect"])
        self.assertIn("256", agent["name"]["effect"])
        notes = " ".join(agent_data["notes"])
        for needle in ("AskUserQuestion", "EnterPlanMode", "ExitPlanMode", "ScheduleWakeup", "WaitForMcpServers",
                       "Workflow", "EndConversation",                       # withheld whatever `tools` lists
                       "TodoWrite", "MCP tools stay",                        # the background tool set
                       "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1", "2.1.251",
                       "bypassPermissions", "2.1.267",                       # permission-mode precedence
                       "managed, then CLI `--agents`, then project, then user, then plugin",
                       "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH", "${CLAUDE_PLUGIN_ROOT}"):
            self.assertIn(needle, notes)
        skill_notes = " ".join(json.loads(run("fields", "skill", "--json").stdout)["notes"])
        for needle in ("except `name` and `paths`", "`name`, `description`, `license`, `compatibility`, `metadata` "
                       "and `allowed-tools`", "1,536", "skillListingBudgetFraction"):
            self.assertIn(needle, skill_notes)
        for needle in ("nesting off", "`Agent(type, ...)`", "Base directory for this skill", "`:name` suffix",
                       "`cd` does not persist"):
            self.assertIn(needle, notes)
        self.assertIn("including for writes to protected paths such as `.git` and `.claude`",
                      agent["permissionMode"]["effect"])
        rule_notes = " ".join(json.loads(run("fields", "rule", "--json").stdout)["notes"])
        for needle in ("1,000 expanded patterns", "unbalanced `[` matches nothing", "Cursor", "every session",
                       "`paths` is the only field", "Quote every glob"):
            self.assertIn(needle, rule_notes)

    def test_notes_hold_field_data_and_leave_behaviour_to_the_skills(self):
        """Each of these has one home in a skill; a note that restates it is a second home."""
        notes = {kind: " ".join(json.loads(run("fields", kind, "--json").stdout)["notes"]) for kind in cl.REFERENCES}
        for needle in ("arrives with the tool result", "`cat`", "~/.claude/rules", "symlink", "At-sign imports",
                       "--add-dir", "--setting-sources", "/context", "InstructionsLoaded", "priority"):
            self.assertNotIn(needle, notes["rule"])
        self.assertEqual(len(cl.RULE_REFERENCE.notes), 4)
        for needle in ("The body is the system prompt", "git status snapshot", "permissions.deny", "tool search"):
            self.assertNotIn(needle, notes["agent"])
        for needle in ("All fields are optional", "only `description` is recommended"):
            self.assertNotIn(needle, notes["skill"])

    def table(self, *args):
        """(header lines, field rows, footer lines, note lines) of the human `fields` output."""
        lines = run("fields", *args).stdout.rstrip("\n").split("\n")
        blank = lines.index("")
        self.assertEqual(lines[blank + 1], "notes:")
        body = lines[2:blank]
        rows = [ln for ln in body if " | " in ln]
        return lines[:2], rows, [ln for ln in body if " | " not in ln], lines[blank + 2:]

    def test_human_output_is_one_line_per_field(self):
        for kind, reference in cl.REFERENCES.items():
            head, rows, footer, notes = self.table(kind)
            self.assertIn(cl.TABLES_VERIFIED_AGAINST, head[0])
            self.assertEqual(head[1], "field | type | default | effect")
            self.assertEqual([r.split(" | ")[0] for r in rows], [f.name for f in reference.fields])
            self.assertTrue(all(r.count(" | ") >= 3 for r in rows))
            self.assertTrue(all(ln.startswith("- ") for ln in notes))        # one note per line, under `notes:`
            self.assertGreaterEqual(len(notes), len(reference.notes))
            # compact, to be read in context: an effect is cut at about FIELDS_EFFECT_WIDTH characters
            for row, field in zip(rows, reference.fields):
                shown = row.split(" | ", 3)[3].split(" [")[0]
                if len(field.effect) <= cl.FIELDS_EFFECT_WIDTH:
                    self.assertEqual(shown, field.effect)
                else:
                    self.assertTrue(shown.endswith("..."), row)
                    self.assertLessEqual(len(shown), cl.FIELDS_EFFECT_WIDTH + 3)
                    self.assertTrue(field.effect.startswith(shown[:-3]))
            # and the line that says so gives the runnable command for the rest
            self.assertEqual(len(footer), 1, kind)
            self.assertIn(cl.self_command("fields", kind, "<field>"), footer[0])
            self.assertIn("--full", footer[0])
            self.assertLess(max(map(len, rows + footer + notes)), 400, kind)
        self.assertIn("[ignored in a plugin agent]", run("fields", "agent").stdout)
        self.assertIn("[since 2.1.218]", run("fields", "skill").stdout)
        self.assertEqual(run("fields").returncode, 2)
        self.assertEqual(run("fields", "hook").returncode, 2)

    def test_full_prints_every_effect_whole(self):
        for kind, reference in cl.REFERENCES.items():
            _, rows, footer, notes = self.table(kind, "--full")
            self.assertEqual(footer, [])
            for row, field in zip(rows, reference.fields):
                self.assertIn(f" | {field.effect}", row)
            self.assertEqual(notes, self.table(kind)[3])
        self.assertEqual(cl.shortened("short"), "short")
        self.assertEqual(cl.shortened("one two three four", 9), "one two...")
        self.assertEqual(cl.shortened("x" * 200, 110), "x" * 111 + "...")          # no space to cut at

    def test_one_field_prints_each_attribute_on_its_own_line(self):
        out = run("fields", "agent", "permissionMode").stdout.rstrip("\n").split("\n")
        field = cl.field_named(cl.AGENT_REFERENCE, "permissionMode")
        self.assertIn("agent frontmatter field `permissionMode`", out[0])
        self.assertIn(cl.TABLES_VERIFIED_AGAINST, out[0])
        self.assertEqual(out[1:], ["type: enum",
                                   "values: default, acceptEdits, auto, dontAsk, bypassPermissions, plan, manual",
                                   "default: the main conversation's mode", "in a plugin agent: ignored",
                                   "effect: " + field.effect])
        skill = run("fields", "skill", "background").stdout.split("\n")
        self.assertIn("since: 2.1.218", skill)
        self.assertFalse(any(ln.startswith("in a plugin agent") for ln in skill))
        self.assertIn("values: haiku, sonnet, opus, fable, inherit, or a full model id",
                      run("fields", "skill", "model").stdout.split("\n"))
        for kind, reference in cl.REFERENCES.items():
            for f in reference.fields:
                r = run("fields", kind, f.name)
                self.assertEqual((r.returncode, r.stderr), (0, ""), f.name)
                self.assertEqual(r.stdout.rstrip("\n").split("\n")[-1], "effect: " + f.effect)
        # --json with a field is that field's row from the kind's table, unchanged
        row = json.loads(run("fields", "agent", "tools", "--json").stdout)
        table = json.loads(run("fields", "agent", "--json").stdout)["fields"]
        self.assertEqual(row, next(r for r in table if r["field"] == "tools"))
        unknown = run("fields", "agent", "allowed-tools")
        self.assertEqual((unknown.returncode, unknown.stdout), (2, ""))
        self.assertIn("no agent frontmatter field is named `allowed-tools`; the fields are: name, description, tools", unknown.stderr)

    def test_edit_distance(self):
        self.assertEqual(cl.edit_distance("tools", "tools"), 0)
        self.assertEqual(cl.edit_distance("tool", "tools"), 1)
        self.assertEqual(cl.edit_distance("alowed-tools", "allowed-tools"), 1)
        self.assertEqual(cl.edit_distance("maxturns", "maxTurns"), 1)
        self.assertEqual(cl.edit_distance("abc", "xyz"), 3)
        self.assertEqual(cl.edit_distance("a", "abcdefgh"), 3)              # capped

    def unknown(self, path):
        return [f.message for f in self.findings(path) if f.id in ("SK017", "AG008")]

    def test_unknown_skill_field(self):
        p = write(self.tmp, "skills/s/SKILL.md", "---\ndescription: d\nalowed-tools: Read\ntriggers: x\n---\nb\n")
        found = [f for f in self.findings(p) if f.id == "SK017"]
        self.assertEqual([(f.line, f.severity) for f in found], [(3, "warn"), (4, "warn")])
        self.assertIn("`alowed-tools` is not a field Claude Code reads in skill frontmatter; did you mean "
                      "`allowed-tools`?", found[0].message)
        self.assertIn("an unrecognised field is ignored without an error, so a typo fails silently", found[0].message)
        self.assertNotIn("did you mean", found[1].message)                 # nothing within two edits of `triggers`
        quiet = ("allowed-tools: Read", "allowedTools: Read", "allowed_tools: Read", "Description: x",
                 "metadata:\n  a: b", "license: MIT", "compatibility: any", "version: 1.0.0", "author: me",
                 "when_to_use: x", "disable-model-invocation: true", "hooks:\n  Stop: []", "background: false")
        for line in quiet:
            with self.subTest(line=line):
                p = write(self.tmp, "skills/q/SKILL.md", f"---\ndescription: d\n{line}\n---\nbody\n")
                self.assertEqual(self.unknown(p), [])

    def test_command_file_does_not_take_name_or_paths(self):
        p = write(self.tmp, ".claude/commands/deploy.md", "---\ndescription: d\nname: deploy\npaths: src/**\n---\nb\n")
        found = self.unknown(p)
        self.assertEqual(len(found), 2)
        self.assertIn("`name` is not read in a `.claude/commands/` file", found[0])
        self.assertIn("except `name` and `paths`", found[1])
        self.plugin()                                    # a plugin's commands/ file does take `name`
        p = write(self.tmp, "commands/deploy.md", "---\ndescription: d\nname: deploy\n---\nbody\n")
        self.assertEqual(self.unknown(p), [])
        p = write(self.tmp, ".claude/skills/s/SKILL.md", "---\nname: s\ndescription: d\npaths: src/**\n---\nbody\n")
        self.assertEqual(self.unknown(p), [])

    def test_unknown_agent_field(self):
        def agent(extra, where=".claude/agents/a.md"):
            return write(self.tmp, where, f"---\nname: a\ndescription: d\n{extra}\n---\nbody\n")
        for line, hint in (("tool: Read", "`tools`"), ("allowed-tools: Read", "`tools`"), ("maxturns: 3", None),
                           ("max_turns: 3", None), ("permisionMode: plan", "`permissionMode`"),
                           ("when_to_use: x", "`description`"), ("mode: plan", ""), ("temperature: 1", "")):
            with self.subTest(line=line):
                found = self.unknown(agent(line))
                if hint is None:
                    self.assertEqual(found, [])                 # case and separators are folded by Claude Code
                else:
                    self.assertEqual(len(found), 1)
                    self.assertEqual("did you mean " + hint in found[0], bool(hint))
                    self.assertEqual("did you mean" in found[0], bool(hint))
        for line in ("autoCompactWindow: 200000", "observer: watcher", "experimental:\n  cacheTtl: 1h",
                     "omitClaudeMd: true", "color: red", "mcpServers:\n  - slack"):
            with self.subTest(line=line):
                self.assertEqual(self.unknown(agent(line)), [])
        self.plugin()                                    # a plugin agent's description may be when_to_use
        self.assertEqual(self.unknown(agent("when_to_use: x", "agents/a.md")), [])

    def enum(self, path):
        return [f.message for f in self.findings(path) if f.id in ("SK018", "AG009")]

    def test_enum_values(self):
        def agent(line):
            return write(self.tmp, ".claude/agents/a.md", f"---\nname: a\ndescription: d\n{line}\n---\nbody\n")

        def skill(line):
            return write(self.tmp, "skills/s/SKILL.md", f"---\ndescription: d\n{line}\n---\nbody\n")
        bad_agent = ("color: magenta", "effort: turbo", "permissionMode: yolo", "model: sonet", "memory: global",
                     "isolation: sandbox", "permissionMode: Plan")
        good_agent = ("color: cyan", "effort: xhigh", "effort: 5", "effort: HIGH", "permissionMode: manual",
                      "permissionMode: dontAsk", "model: opus", "model: Opus", "model: inherit",
                      "model: claude-opus-5-5", "model: us.anthropic.claude-sonnet-5-v1:0", "model: opusplan",
                      "model: 'sonnet[1m]'", "memory: project", "isolation: worktree", "isolation: remote",
                      "background: true", "maxTurns: 5")
        for line in bad_agent:
            with self.subTest(line=line):
                found = self.enum(agent(line))
                self.assertEqual(len(found), 1)
                self.assertTrue(found[0].startswith(f"`{line}` is not one of "), found[0])
                self.assertIn("the field behaves as if it were unset", found[0])
        for line in good_agent:
            with self.subTest(line=line):
                self.assertEqual(self.enum(agent(line)), [])
        self.assertIn("haiku, sonnet, opus, fable, inherit, or a full model id", self.enum(agent("model: sonet"))[0])
        for line in ("effort: turbo", "context: forked", "shell: zsh"):
            with self.subTest(line=line):
                self.assertEqual(len(self.enum(skill(line))), 1)
        for line in ("effort: max", "effort: 3", "context: fork", "context: inline", "shell: powershell",
                     "shell: Bash", "model: whatever"):          # a skill's `model` is not part of the check
            with self.subTest(line=line):
                self.assertEqual(self.enum(skill(line)), [])

    def test_own_plugin_trips_none_of_the_table_rules(self):
        ids = {f.id for f in cl.lint_paths([ROOT])}
        self.assertFalse(ids & {"SK017", "SK018", "AG008", "AG009", "AG010", "RU007"})


class AgentExtensionTests(TempCase):
    def agent(self, front, rel=".claude/agents/a.md"):
        return write(self.tmp, rel, f"---\n{front}\n---\nbody\n")

    def test_names_claude_code_skips_are_errors(self):
        for name, part in (("-reviewer", "starts with `-`"), ("team:reviewer", "contains `:`"),
                           ("r" * 257, "is 257 characters; the limit is 256")):
            with self.subTest(name=name[:20]):
                (f,) = [f for f in self.findings(self.agent(f"name: {name}\ndescription: d")) if f.id == "AG001"]
                self.assertEqual(f.severity, "error")
                self.assertIn(part, f.message)
                self.assertIn("Claude Code skips the file", f.message)
        self.assertEqual(self.ids(self.agent("name: " + "r" * 256 + "\ndescription: d")), [])
        self.assertEqual(cl.agent_name_problems("code-reviewer"), ())

    def test_every_name_problem_is_reported_not_only_the_first(self):
        name = "-team:" + "r" * 257
        self.assertEqual(len(cl.agent_name_problems(name)), 3)
        found = [f for f in self.findings(self.agent(f"name: {name}\ndescription: d")) if f.id == "AG001"]
        self.assertEqual([f.severity for f in found], ["error"] * 3)
        for part, f in zip(("starts with `-`", "contains `:`", "the limit is 256"), found):
            self.assertIn(part, f.message)
            self.assertIn("Claude Code skips the file", f.message)

    def test_other_shapes_are_a_convention_and_a_warn(self):
        for name in ("Code_Reviewer", "reviewer v2", "Reviewer"):
            with self.subTest(name=name):
                (f,) = [f for f in self.findings(self.agent(f"name: {name}\ndescription: d")) if f.id == "AG001"]
                self.assertEqual(f.severity, "warn")
                self.assertIn("a convention only", f.message)
        missing = [f for f in self.findings(self.agent("description: d")) if f.id == "AG001"]
        self.assertEqual([f.severity for f in missing], ["error"])

    def test_duplicate_names_in_one_scope_directory(self):
        a = self.agent("name: reviewer\ndescription: d", ".claude/agents/a.md")
        b = self.agent("name: reviewer\ndescription: d", ".claude/agents/team/b.md")
        c = self.agent("name: other\ndescription: d", ".claude/agents/c.md")
        cl._AGENT_NAMES.clear()
        found = cl.lint_paths([self.tmp])
        dup = [f for f in found if f.id == "AG010"]
        self.assertEqual(sorted(os.path.basename(f.path) for f in dup), ["a.md", "b.md"])
        self.assertTrue(all(f.severity == "warn" for f in dup))
        self.assertIn("picked by filesystem read order", dup[0].message)
        self.assertIn("b.md", [f for f in dup if f.path.endswith("a.md")][0].message)
        self.assertNotIn("AG010", self.ids(c))
        # one file at a time (hook mode) sees its twin too
        cl._AGENT_NAMES.clear()
        self.assertIn("AG010", self.ids(a))
        # a different scope directory is a different namespace
        other = os.path.join(self.tmp, "nested")
        d = write(other, ".claude/agents/a.md", "---\nname: unique-here\ndescription: d\n---\nbody\n")
        cl._AGENT_NAMES.clear()
        self.assertNotIn("AG010", self.ids(d))
        self.assertEqual(cl.agent_scope_root(d), os.path.join(other, ".claude", "agents"))
        self.assertIsNone(cl.agent_scope_root(os.path.join(self.tmp, "docs", "x.md")))

    def test_more_than_32_preloaded_skills(self):
        self.plugin()
        names = [f"s{i:02d}" for i in range(33)]
        for n in names:
            write(self.tmp, f"skills/{n}/SKILL.md", "---\ndescription: d\n---\nbody\n")
        listing = "\n".join(f"  - {n}" for n in names)
        p = self.agent(f"name: a\ndescription: d\nskills:\n{listing}", "agents/a.md")
        found = [f for f in self.findings(p) if f.id == "AG004"]
        self.assertEqual(len(found), 1)
        self.assertIn("lists 33 names; only the first 32 are preloaded - 's32'", found[0].message)
        listing = "\n".join(f"  - {n}" for n in names[:32])
        self.assertEqual(self.ids(self.agent(f"name: a\ndescription: d\nskills:\n{listing}", "agents/a.md")), [])


class RuleExtensionTests(TempCase):
    def rule(self, front, body="# R\n\nApplies when editing.\n"):
        return write(self.tmp, ".claude/rules/r.md", f"---\n{front}\n---\n{body}")

    def test_unclosed_bracket(self):
        for glob, unclosed in (("src/[ab/*.ts", True), ("src/[ab]/*.ts", False), ("src/\\[ab/*.ts", False),
                               ("a]b", False), ("[]", True), ("[a]x[", True), ("x[!a-z]y", False)):
            self.assertEqual(cl.unclosed_bracket(glob), unclosed, glob)
        (f,) = self.findings(self.rule('paths:\n  - "src/[ab/*.ts"'))
        self.assertEqual((f.id, f.severity), ("RU006", "warn"))
        self.assertIn("matches nothing", f.message)
        self.assertEqual(self.ids(self.rule('paths:\n  - "src/[ab]/*.ts"\n  - "docs/\\\\[draft/*.md"')), [])

    def test_brace_expansion_budget(self):
        count = cl.brace_expansion_count
        self.assertEqual(count("src/*.{ts,tsx}"), 2)                       # the docs' two examples
        self.assertEqual(count("{a,b}/{c,d}/*.{ts,tsx}"), 8)
        self.assertEqual(count("src/**/*.ts"), 1)
        self.assertEqual(count("{a,{b,c}}/x"), 3)
        self.assertEqual(count("{a,b}{c,d}{e,f}"), 8)
        self.assertEqual(count("\\{a,b\\}"), 1)
        self.assertEqual(count("{a}"), 1)
        self.assertEqual(count("{a,b"), 2)                                 # unclosed: counted as written
        self.assertEqual(cl.paths_expansion_total(["src/**/*.ts", "{a,b}/x", "{a,b,c}/y"]), 5)   # no braces: free
        ten = "{" + ",".join("abcdefghij") + "}"
        over = self.rule(f'paths:\n  - "{ten}/{ten}/{ten}/*.{{ts,tsx}}"')        # 2,000
        (f,) = self.findings(over)
        self.assertEqual((f.id, f.severity), ("RU006", "warn"))
        self.assertIn("expands to 2,000 patterns; the budget is 1,000", f.message)
        at_limit = self.rule(f'paths:\n  - "{ten}/{ten}/{ten}/*.ts"\n  - "lib/**"')    # exactly 1,000
        self.assertEqual(self.ids(at_limit), [])
        shared = self.rule(f'paths:\n  - "{ten}/{ten}/{ten}/*.ts"\n  - "x.{{a,b}}"')   # 1,002 across the list
        self.assertEqual(self.ids(shared), ["RU006"])

    def test_parse_failures_say_why(self):
        (f,) = self.findings(self.rule("paths:\n  - **/*.ts"))
        self.assertEqual(f.severity, "error")
        self.assertIn("is dropped, and the rule then loads in every session, silently", f.message)

    def test_imports_in_a_rule(self):
        write(self.tmp, "AGENTS.md", "one\ntwo\nthree\n")
        front = 'paths:\n  - "src/**"'
        p = self.rule(front, "# R\n\nApplies when editing.\n\nSee @../../AGENTS.md for the rest.\n")
        (f,) = self.findings(p)
        self.assertEqual((f.id, f.severity, f.line), ("RU007", "warn", 9))
        self.assertIn("@../../AGENTS.md is an import (3 lines) - an import pulls the whole target in on every load",
                      f.message)
        p = self.rule(front, "# R\n\nApplies when editing.\n\nSee @AGENTS.md here.\n")      # relative to the rule
        (f,) = self.findings(p)
        self.assertIn("does not resolve from", f.message)
        self.assertIn("imports nothing, silently", f.message)
        quiet = ("An at-sign path such as `@../../AGENTS.md` is an import.", "Ask @someone or mail a@b.co.",
                 f"{FENCE}\n@../../AGENTS.md\n{FENCE}", "<!-- @../../AGENTS.md -->", "Use the @scope/pkg package.")
        for body in quiet:
            with self.subTest(body=body):
                self.assertEqual(self.ids(self.rule(front, f"# R\n\nApplies when editing.\n\n{body}\n")), [])
        p = self.rule(front, "# R\n\nApplies when editing.\n\n@~/.claude/shared.md\n")       # cannot be checked
        self.assertEqual(self.ids(p), ["RU007"])
        p = self.rule(front, "# R\n\nApplies when editing.\n\n<!-- claude-lint-disable RU007 -->\n@../../AGENTS.md\n")
        self.assertEqual(self.ids(p), [])


class QuotedImportTests(TempCase):
    def test_a_quoted_import_is_reported_as_not_imported(self):
        write(self.tmp, "AGENTS.md", "x\n")
        write(self.tmp, "Design Docs/api.md", "x\n")
        p = write(self.tmp, "CLAUDE.md", '# P\n\nSee "@AGENTS.md" here.\n\n@"Design Docs/api.md"\n\n@AGENTS.md\n')
        found = self.findings(p)
        self.assertEqual([(f.id, f.severity, f.line) for f in found], [("CM002", "info", 3), ("CM002", "info", 5)])
        self.assertIn('"@AGENTS.md" is in quotes, and a quoted path is not imported', found[0].message)
        self.assertIn('@"Design Docs/api.md"', found[1].message)
        p = write(self.tmp, "CLAUDE.md", '# P\n\nHe said "@alice knows" and `"@AGENTS.md"`.\n')
        self.assertEqual(self.ids(p), [])
        self.assertEqual(cl.quoted_imports('a "@x.md" b\n@"y z.md"\n'), [(1, "x.md", '"@x.md"'), (2, "y z.md", '@"y z.md"')])


# ---- file-keyed triggers (SK016, AG007) ------------------------------------------
#
# Real descriptions, verbatim. The corpus the heuristic was tuned on: the 71
# distinct descriptions of every skill and agent under /mnt/skills and the
# synced plugins on 2026-10-11 (6 hits, each read and judged file-keyed), plus
# this plugin's own.

FILE_KEYED = [
    # claude-authoring 0.1.0, authoring-agents
    ("Use this skill whenever authoring, editing, or reviewing any subagent definition in .claude/agents/ or "
     "~/.claude/agents/, whenever choosing or debugging agent properties, or whenever a subagent has wrong "
     "permissions.", "editing", ".claude/agents/"),
    # claude-authoring 0.1.0, authoring-skills
    ("Use this skill whenever authoring, editing, or reviewing any SKILL.md or slash command, whenever choosing or "
     "debugging frontmatter.", "editing", "SKILL.md"),
    # claude-authoring 0.1.0, authoring-memory
    ("Use whenever editing or reviewing a CLAUDE.md, when it has grown too long or isn't being followed, when "
     "deciding between CLAUDE.md and a path-scoped rule, or after `/init` scaffolds one.", "editing", "CLAUDE.md"),
    # textual-tui, tui-verifier (an agent)
    ("Use proactively after implementing or changing any screen, widget, binding, or .tcss file, and before "
     "claiming a TUI feature works.", "changing", ".tcss"),
    # textual-tui, textual-dev-loop
    ("Use after every edit to a Textual App, Screen, Widget, or .tcss file, and whenever asked \"what does it look "
     "like now\".", "edit", ".tcss"),
    # c4-architecture, likec4-publish
    ("Also use to republish after the .c4 sources change.", "change", ".c4"),
    # shapes the spec names
    ("Load this when working on anything under src/api/ or touching a Dockerfile.", "working on", "src/api/"),
    ("Use before you modify package.json.", "modify", "package.json"),
    ("Apply whenever a file matching **/*.sql is opened.", "opened", "**/*.sql"),
    ("Use when creating hooks.json or settings.json.", "creating", "hooks.json"),
]

NOT_FILE_KEYED = [
    # the user says or provides the file: a request, which is what a description matches
    "If the user mentions a .pdf file or asks to produce one, use this skill.",                               # pdf
    "Trigger whenever the user asks for a PowerPoint or .pptx file, or references a .pptx or .potx filename, "
    "regardless of what they plan to do with the content afterward.",                                         # pptx
    "This means any task where the user wants to: open, read, edit, or fix an existing .xlsx, .xlsm, .xltx, .csv, "
    "or .tsv file (e.g., adding columns, computing formulas, formatting, charting, cleaning messy data).",    # xlsx
    "Trigger especially when the user references a spreadsheet file by name or path.",                        # xlsx
    "Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx) or Word "
    "templates (.dotx).",                                                                                     # docx
    "Use when the user uploads a CSV and wants it cleaned.",
    "Use when the user asks for a .docx.",
    "Use whenever the user asks for an architecture diagram, or mentions LikeC4 or .c4 files.",              # likec4
    "Use proactively after authoring or editing any extension, whenever asked to audit or review a skill, rule, or "
    "agent, or to sweep a repo's .claude/ tree.",                                                # authoring-auditor
    "Use this skill when a file has been uploaded but its content is NOT in your context — only its path at "
    "/mnt/user-data/uploads/ is listed in an uploaded_files block.",                                  # file-reading
    # a deliverable or a capability, not a trigger
    "Create beautiful visual art in .png and .pdf documents using design philosophy.",               # canvas-design
    "This includes: creating slide decks, pitch decks, or presentations as PowerPoint (.pptx) files; reading, "
    "parsing, or extracting text from any .pptx or .potx file.",                                              # pptx
    "Author, scaffold, and validate Claude Code hooks - in settings.json or in skill/agent frontmatter.",
    "Scaffolds a new Textual (Python TUI) project — layered src/ package, the tools/tuictl.py headless observation "
    "harness, an external .tcss, ast-grep rules, .claude/rules, a pre-commit gate, and CI.",
    "Determines whether new Claude Code functionality should be a rule (.claude/rules/), a skill (inline or "
    "context-fork), an authored subagent, or a hook.",
    "Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration.",
    # slashes and dots that are not paths
    "Use when writing down an intent for a piece of work, when deciding whether a task can close, and when driving "
    "a long run with /goal.",                                                                            # work-loop
    "Use when working in ios_core and asked where a TCA feature sits, its parent/children/clients/streams/GraphQL "
    "calls.",                                                                                            # ios-lens
    "Also use before editing ItemCardFeature, catchup/settling or replay-handling code.",           # live-lens-ios
    "Use when writing, refactoring or reviewing Python he owns, or when separating logic from I/O.",  # python-idioms
    "Use while writing or reviewing any code that imports textual, whenever unsure how a Textual feature works "
    "(Static.content not .renderable, Select.NULL not .BLANK).",                                     # textual-api
    "Use only when the user explicitly asks to run, see, or set up their morning brief, or if they invoke /morning "
    "by name.",                                                                                           # morning
    "Covers: Claude Code (how to install, Node.js requirements, platform/OS support), whenever you write about "
    "pricing.",                                                                             # product-self-knowledge
    "Read https://example.com/docs/guide.md before editing prose.",
    "Use when the mechanism is undecided - any question like \"should this be a skill or an agent\".",
]


class FileKeyedTriggerTests(TempCase):
    def test_file_keyed_descriptions(self):
        for text, verb, token in FILE_KEYED:
            with self.subTest(text=text[:60]):
                hits = cl.file_keyed_triggers(text)
                self.assertTrue(hits, text)
                self.assertEqual((hits[0][0], hits[0][1]), (verb, token))

    def test_descriptions_that_are_not(self):
        for text in NOT_FILE_KEYED:
            with self.subTest(text=text[:60]):
                self.assertEqual(cl.file_keyed_triggers(text), [])

    def test_path_like_tokens(self):
        def tokens(text):
            return [t for _, t in cl.path_like_tokens(text)]
        self.assertEqual(tokens("in .claude/agents/, ~/.claude/agents/ or a plugin agents/ directory"),
                         [".claude/agents/", "~/.claude/agents/", "agents/"])
        self.assertEqual(tokens("SKILL.md, CLAUDE.md / CLAUDE.local.md, AGENTS.md, hooks.json and settings.json"),
                         ["SKILL.md", "CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "hooks.json", "settings.json"])
        self.assertEqual(tokens("a Dockerfile, package.json, src/**/*.ts, *.md, a .tcss file and tools/x.py"),
                         ["Dockerfile", "package.json", "src/**/*.ts", "*.md", ".tcss", "tools/x.py"])
        for text in ("and/or", "read/write", "skill/agent frontmatter", "I/O", "L1/L2/L3", "/goal and /init",
                     "Node.js and p5.js", "e.g. this", "https://code.claude.com/docs/en/skills.md", "v2.1.296",
                     "mcp__claude-in-chrome__* tools", "Static.content", "docs.google.com", "80x24"):
            with self.subTest(text=text):
                self.assertEqual(tokens(text), [])

    def test_lint_reports_one_info_per_field(self):
        p = write(self.tmp, "skills/s/SKILL.md",
                  "---\ndescription: Use whenever editing any SKILL.md, or before you touch a Dockerfile.\n"
                  "when_to_use: Use when the user asks for a .docx.\n---\nbody\n")
        (f,) = self.findings(p)
        self.assertEqual((f.id, f.severity, f.line), ("SK016", "info", 2))
        self.assertIn('"whenever editing any SKILL.md" (and 1 more) ties `editing` to `SKILL.md`', f.message)
        self.assertIn("whether this loads when that file is touched is left to the model's judgement; a path-scoped "
                      "rule or a hook is guaranteed", f.message)
        p = write(self.tmp, ".claude/agents/a.md",
                  "---\nname: a\ndescription: Use proactively after changing any .tcss file.\n---\nbody\n")
        (f,) = self.findings(p)
        self.assertEqual((f.id, f.severity), ("AG007", "info"))
        p = write(self.tmp, "skills/t/SKILL.md", "---\ndescription: Use when the user asks for a .docx.\n---\nbody\n")
        self.assertEqual(self.ids(p), [])

    def test_this_plugins_own_descriptions(self):
        # They trip it until they are rewritten around the request; nothing else new fires on the plugin.
        found = [f for f in cl.lint_paths([ROOT]) if f.id in ("SK016", "AG007")]
        self.assertTrue(all(f.severity == "info" for f in found))
        self.assertLessEqual(len(found), 8)


# ---- check-injection ---------------------------------------------------------------

class CheckInjectionTests(TempCase):
    def test_loads(self):
        r = run("check-injection", 'git status --short 2>/dev/null | head -20')
        self.assertEqual((r.returncode, r.stdout), (0, "loads\n"))
        r = run("check-injection", 'gh pr view 2>/dev/null || echo "no PR"', "--allowed-tools", "Bash(gh pr view *)")
        self.assertEqual((r.returncode, r.stdout), (0, "loads\n"))

    def test_aborts_with_the_part_the_reason_and_the_entry(self):
        r = run("check-injection", 'gh pr view --json title 2>/dev/null || echo "no PR"')
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "aborts")
        self.assertIn("`gh pr view --json title`, which needs approval", lines[1])
        self.assertIn("aborts the skill load", lines[1])
        self.assertEqual(lines[2], "add to allowed-tools: Bash(gh pr view *)")
        self.assertEqual(run("check-injection", 'gh pr view --json title || echo x', "--allowed-tools",
                             "Read, Bash(gh pr view *)").returncode, 0)

    def test_json_and_other_problem_kinds(self):
        r = run("check-injection", "cat ../other/README.md | head -3", "--json")
        data = json.loads(r.stdout)
        self.assertEqual((r.returncode, data["verdict"]), (1, "aborts"))
        self.assertEqual(set(data), {"verdict", "problems", "add", "fallback"})
        self.assertEqual([(p["kind"], p["entry"]) for p in data["problems"]], [("outside", None)])
        self.assertEqual(data["add"], [])
        self.assertIn("`..` component", data["problems"][0]["why"])
        r = run("check-injection", "(git status)", "--json")
        self.assertEqual(json.loads(r.stdout)["problems"][0]["kind"], "hazard")
        data = json.loads(run("check-injection", "date", "--json").stdout)
        self.assertEqual((data["verdict"], data["fallback"], data["problems"]), ("loads", False, []))
        self.assertIn("note: no fallback", run("check-injection", "date").stdout)
        self.assertNotIn("note:", run("check-injection", "date || echo n/a").stdout)

    def test_plugin_skill_directory_is_outside(self):
        command = 'cat "${CLAUDE_SKILL_DIR}/notes.md" | head -5'
        self.assertEqual(run("check-injection", command).returncode, 0)
        r = run("check-injection", command, "--plugin-skill")
        self.assertEqual(r.returncode, 1)
        self.assertIn("outside the session's working directories", r.stdout)

    def test_same_answer_as_the_lint_rule(self):
        for command, allowed in (("npm test", None), ("npm test", "Bash(npm test)"), ("echo hi", None),
                                 ("sort -o out.txt in.txt", None), ("find . -name '*.md' -delete", "Bash(find *)")):
            with self.subTest(command=command, allowed=allowed):
                verdict = cl.injection_verdict(command, allowed)
                self.assertEqual(verdict["verdict"] == "aborts", bool(cl.injection_problems(command, allowed)))
        self.assertEqual(run("check-injection").returncode, 2)


# ---- drift --------------------------------------------------------------------------

BUNDLE = (
    b'junk\x00\x01 var tK=["PreToolUse","PostToolUse","SessionStart","Stop"],x=["PreToolUse","PostToolUse"];'
    b'var Rc=new Set(["Stop","SessionStart","PreToolUse"]);'
    b'var M=["name","description","model","allowed-tools","argument-hint","when_to_use","paths","compatibility",'
    b'"disable-model-invocation","tools","omitClaudeMd"];'
    b'fVn=p(()=>u({name:Fp().optional().describe("Display name. {not a key: 1}"),description:Fp().optional(),'
    b'"allowed-tools":XP().optional().describe(`Tools, "quoted", (parens)`),"argument-hint":Fp().optional(),'
    b'"disable-model-invocation":DC().optional(),"user-invocable":DC().optional(),'
    b'effort:Ue([U(["low","medium","high"]),E().int()]).optional(),nested:u({inner:o()}).optional()})),'
    b'pVn=p(()=>fVn().extend({when_to_use:Fp().optional(),paths:XP().optional(),'
    b'context:U(["inline","fork"]).nullable().optional(),agent:Fp().optional()})),'
    b'ey=p(()=>u({description:o(),prompt:o(),omitClaudeMd:M().optional(),permissionMode:ce().optional()})),'
    b'lIe=p(()=>u({name:Fp(),description:Fp(),color:Fp().optional(),permissionMode:Fp().optional(),'
    b'omitClaudeMd:DC().optional(),isolation:Fp().optional(),experimental:u({cacheTtl:Fp()}).loose()})),'
    b'q={...dt&&{omitClaudeMd:dt}};var vH=["acceptEdits","auto","default","plan"];more\xff\xfe'
)


class DriftTests(TempCase):
    def test_string_arrays_and_hook_events(self):
        arrays = cl.string_arrays(BUNDLE)
        self.assertIn(("PreToolUse", "PostToolUse"), arrays)
        self.assertIn(("inline", "fork"), arrays)
        self.assertEqual(cl.hook_events_in(arrays), ("PreToolUse", "PostToolUse", "SessionStart", "Stop"))
        self.assertEqual(cl.hook_events_in(cl.string_arrays(b'x=["a","b"]')), ())

    def test_object_keys(self):
        source = '{a:1,"b-c":f("x,y:{"),d:{e:1,f:[1,{g:2}]},h:`t ${1} }`,i:u({j:1})}'
        self.assertEqual(cl.object_keys(source, 0), ["a", "b-c", "d", "h", "i"])
        self.assertEqual(cl.object_keys(source, source.index("{e:")), ["e", "f"])
        self.assertIsNone(cl.object_keys("{return x}", 0))
        self.assertIsNone(cl.object_keys("x", 0))
        self.assertIsNone(cl.object_keys("{a:1", 0))                         # never closed

    def test_schema_keys_are_found_by_content(self):
        base = cl.schema_keys(BUNDLE, "disable-model-invocation", ("allowed-tools", "argument-hint", "user-invocable"))
        self.assertEqual(base, ("name", "description", "allowed-tools", "argument-hint", "disable-model-invocation",
                                "user-invocable", "effort", "nested"))
        self.assertEqual(cl.schema_keys(BUNDLE, "when_to_use", ("paths", "context", "agent")),
                         ("when_to_use", "paths", "context", "agent"))
        # two other objects hold `omitClaudeMd`; only the frontmatter schema has the required keys
        self.assertEqual(cl.schema_keys(BUNDLE, "omitClaudeMd", ("name", "color", "isolation", "permissionMode")),
                         ("name", "description", "color", "permissionMode", "omitClaudeMd", "isolation",
                          "experimental"))
        self.assertIsNone(cl.schema_keys(BUNDLE, "omitClaudeMd", ("name", "no-such-key")))
        self.assertIsNone(cl.schema_keys(b"nothing here", "omitClaudeMd", ("name",)))

    def test_name_drift(self):
        self.assertEqual(cl.name_drift("x", ["a", "b"], ["a", "b"]), [])
        self.assertEqual(cl.name_drift("x", ["a", "b"], ["a", "b", "c"], known_extra=["c"]), [])
        self.assertEqual(cl.name_drift("skill fields", ["a", "gone"], ["a", "new", "internal"], known_extra=["internal"]),
                         ["skill fields: in the tables but not in this build: gone",
                          "skill fields: in this build but not in the tables: new"])

    def test_enum_drift(self):
        arrays = {("low", "medium", "high", "xhigh", "max"), ("low", "medium", "high", "xhigh"), ("bash", "powershell"),
                  ("zsh", "bash", "fish", "powershell")}
        levels = ("low", "medium", "high", "xhigh", "max")
        self.assertEqual(cl.enum_drift("effort", levels, arrays, True), ("ok", None))
        state, line = cl.enum_drift("effort", levels[:4], arrays, True)             # the build added `max`
        self.assertEqual((state, line), ("drift", "effort: this build has a value set with more in it: max"))
        state, line = cl.enum_drift("effort", levels + ("ultra",), arrays, True)    # the build dropped `ultra`
        self.assertEqual(state, "drift")
        self.assertIn("the nearest lacks ultra", line)
        state, line = cl.enum_drift("effort", levels[:4] + ("maximum",), arrays, True)      # renamed
        self.assertEqual(state, "drift")
        self.assertIn("lacks maximum and has max", line)
        self.assertEqual(cl.enum_drift("effort", ("a", "b", "c"), arrays, True), ("unknown", None))
        # a set of ordinary words is only looked for exactly: the larger shell list is not drift
        self.assertEqual(cl.enum_drift("shell", ("bash", "powershell"), arrays, False), ("ok", None))
        self.assertEqual(cl.enum_drift("shell", ("bash", "zsh"), arrays, False), ("unknown", None))

    def test_report_on_a_fixture_build(self):
        report = cl.drift_report(BUNDLE, ["PreToolUse", "PostToolUse", "SessionStart", "Stop"], "9.9.9")
        self.assertEqual((report["verified_against"], report["running"]), (cl.TABLES_VERIFIED_AGAINST, "9.9.9"))
        drift = "\n".join(report["drift"])
        self.assertNotIn("hook events", drift)
        self.assertIn("skill fields: in the tables but not in this build:", drift)       # the fixture has few fields
        self.assertIn("skill fields: in this build but not in the tables: nested", drift)
        self.assertNotIn("compatibility", drift)        # not in the schema, but still a key the build knows
        self.assertIn("agent fields: in the tables but not in this build:", drift)
        self.assertIn("hook event names (4 in this build)", report["checked"])
        report = cl.drift_report(BUNDLE, ["PreToolUse", "Stop", "Brand New"], None)
        self.assertIn("hook events: in the tables but not in this build: Brand New", report["drift"])
        self.assertIn("hook events: in this build but not in the tables: PostToolUse, SessionStart", report["drift"])

    def test_a_build_with_nothing_recognisable_is_not_checkable(self):
        report = cl.drift_report(b"#!/bin/sh\nexec node cli.js\n", ["PreToolUse"], "1.0.0")
        self.assertEqual((report["drift"], report["checked"]), ([], []))
        self.assertGreaterEqual(len(report["not_checked"]), 8)
        text = cl.drift_text(report)
        self.assertIn("not checkable", text)
        self.assertNotIn("no drift found", text)
        report = cl.drift_report(BUNDLE, None, "1.0.0")
        self.assertIn("hook events: `hooktool events --json` gave no list", report["not_checked"])

    def test_text_names_both_versions_and_what_was_not_checked(self):
        text = cl.drift_text({"verified_against": "2.1.296", "running": "2.2.0", "build": "/x/claude",
                              "drift": ["agent fields: in this build but not in the tables: newField"],
                              "checked": ["agent frontmatter fields (23 in this build's schema)"],
                              "not_checked": ["the numeric limits"]})
        lines = text.split("\n")
        self.assertEqual(lines[0], "tables verified against 2.1.296; running 2.2.0")
        self.assertIn("drift: agent fields: in this build but not in the tables: newField", lines)
        self.assertIn("NOT checked:", lines)
        self.assertNotIn("no drift found", text)

    def test_without_claude_on_path(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        r = run("drift", env=dict(os.environ, PATH=empty))
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith(f"tables verified against {cl.TABLES_VERIFIED_AGAINST}; running unknown\n"))
        self.assertIn("`claude` is not on PATH", r.stdout)
        self.assertIn("not checkable", r.stdout)
        data = json.loads(run("drift", "--json", env=dict(os.environ, PATH=empty)).stdout)
        self.assertEqual(set(data), {"verified_against", "running", "build", "drift", "checked", "not_checked"})

    def test_a_drifted_build_exits_1(self):
        fake = os.path.join(self.tmp, "fakebin")
        os.makedirs(fake)
        with open(os.path.join(fake, "claude"), "wb") as f:
            f.write(b"#!/bin/sh\necho '9.9.9 (Claude Code)'\nexit 0\n" + BUNDLE)
        os.chmod(os.path.join(fake, "claude"), 0o755)
        r = run("drift", env=dict(os.environ, PATH=fake + os.pathsep + "/usr/bin:/bin"))
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith(f"tables verified against {cl.TABLES_VERIFIED_AGAINST}; running 9.9.9\n"))
        self.assertIn("drift: skill fields: in this build but not in the tables: nested", r.stdout)

    @unittest.skipUnless(shutil.which("claude"), "no `claude` on PATH")
    def test_against_the_installed_claude_code(self):
        r = run("drift", "--json")
        data = json.loads(r.stdout)
        self.assertIn(r.returncode, (0, 1))
        self.assertEqual(r.returncode, 1 if data["drift"] else 0)
        if data["running"] == cl.TABLES_VERIFIED_AGAINST:
            # the build the tables were verified against: everything locatable, nothing drifted
            self.assertEqual(data["drift"], [])
            checked = " ".join(data["checked"])
            for what in ("hook event names", "skill frontmatter fields", "agent frontmatter fields", "effort levels",
                         "permission modes", "model aliases"):
                self.assertIn(what, checked)


# ---- rule delivery on first touch ---------------------------------------------------

class RuleDeliveryTests(TempCase):
    def setUp(self):
        super().setUp()
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(self.state)
        self.env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT")}
        self.env["TMPDIR"] = self.state
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(self.project)
        self.plugin_name = cl.own_plugin_name()

    def event(self, path, tool="Write", session="s1", **extra):
        return json.dumps(dict({"session_id": session, "cwd": self.project, "hook_event_name": "PostToolUse",
                                "tool_name": tool, "tool_input": {"file_path": path}}, **extra),
                          separators=(",", ":"))

    def hook(self, payload):
        r = run("hook", stdin=payload, env=self.env)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        if not r.stdout:
            return None
        out = json.loads(r.stdout)
        self.assertEqual(list(out), ["hookSpecificOutput"])
        self.assertEqual(set(out["hookSpecificOutput"]), {"hookEventName", "additionalContext"})
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        return out["hookSpecificOutput"]["additionalContext"]

    LINT_COMMAND = f'python3 "{LINT}" rules'
    HOOKTOOL_COMMAND = f'python3 "{os.path.join(ROOT, "skills", "authoring-hooks", "scripts", "hooktool.py")}" events'
    LINT_LINE = "Mechanical invariants and their reasons: " + LINT_COMMAND
    HOOKTOOL_LINE = "Hook events and handler fields: " + HOOKTOOL_COMMAND

    def rule_body(self, name):
        with open(os.path.join(ROOT, "rules", name), encoding="utf-8") as f:
            return cl.parse_frontmatter(f.read()).body.strip()

    def litmus(self):
        return (f"[{self.plugin_name}] Litmus for any model-facing prose you write or edit: if you could write an "
                "assertion for it, write code; if you would need a rubric, write prose.\n\n")

    def rule_block(self, rule, line=None):
        """One rule as it is delivered: header, body, then the one line with the runnable command."""
        return (f"[{self.plugin_name}] rule {rule}\n\n" + self.rule_body(rule + ".md")
                + "\n\n" + (line or self.LINT_LINE))

    def test_first_write_gets_the_rule_then_the_findings_in_one_object(self):
        bad = write(self.project, "skills/demo/SKILL.md", "---\nname: BAD\n---\nbody\n")
        ctx = self.hook(self.event(bad))
        header = self.litmus() + f"[{self.plugin_name}] rule skill-invariants\n\n"
        self.assertTrue(ctx.startswith(header))
        self.assertEqual(ctx, self.litmus() + self.rule_block("skill-invariants") + f"\n\n[claude-lint] {bad}\n"
                         + ctx.split(f"[claude-lint] {bad}\n")[1])
        self.assertNotIn("paths:", ctx.split("[claude-lint]")[0])               # frontmatter is stripped
        self.assertRegex(ctx.split(f"[claude-lint] {bad}\n")[1], r"^2: error SK001 .* - `name` is the command")
        # the second skill write in the session: findings only
        other = write(self.project, "skills/two/SKILL.md", "---\nname: BAD\n---\nbody\n")
        ctx = self.hook(self.event(other))
        self.assertTrue(ctx.startswith(f"[claude-lint] {other}\n2: error SK001 "))
        self.assertNotIn("rule skill-invariants", ctx)
        # and a clean one says nothing at all
        clean = write(self.project, "skills/ok/SKILL.md", "---\ndescription: d\n---\nbody\n")
        self.assertIsNone(self.hook(self.event(clean)))

    def test_a_read_delivers_the_rule_and_does_not_lint(self):
        rule = write(self.project, ".claude/rules/x.md", "no applies line, no paths\n")
        ctx = self.hook(self.event(rule, tool="Read", tool_response={"file": {"filePath": rule, "content": "x"}}))
        self.assertEqual(ctx, self.litmus() + self.rule_block("rule-invariants"))
        self.assertIsNone(self.hook(self.event(rule, tool="Read")))
        self.assertIn("RU005", self.hook(self.event(rule, tool="Edit")))        # an edit is linted as before

    def test_each_kind_once_per_session_and_per_agent(self):
        files = {
            "skill-invariants": write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n"),
            "rule-invariants": write(self.project, ".claude/rules/r.md", "---\npaths: \"src/**\"\n---\n# R\n\nApplies when x.\n"),
            "subagent-invariants": write(self.project, ".claude/agents/a.md", "---\nname: a\ndescription: d\n---\nbody\n"),
            "claude-md-invariants": write(self.project, "CLAUDE.md", "# P\n"),
            "hook-invariants": write(self.project, ".claude/settings.json", "{}\n"),
        }
        for n, (rule, path) in enumerate(files.items()):
            with self.subTest(rule=rule):
                command = self.HOOKTOOL_LINE if rule == "hook-invariants" else None
                # the litmus leads the session's first delivery, whichever kind that is, and no later one
                self.assertEqual(self.hook(self.event(path, tool="Read")),
                                 (self.litmus() if n == 0 else "") + self.rule_block(rule, command))
                self.assertIsNone(self.hook(self.event(path, tool="Read")))
        manifest = write(self.project, ".claude-plugin/plugin.json", '{"name": "demo"}\n')
        self.assertIsNone(self.hook(self.event(manifest, tool="Read")))          # `plugin` has no rule
        skill = files["skill-invariants"]
        # a subagent has its own context: it gets the rule once too, and so does another session
        first = self.litmus() + self.rule_block("skill-invariants")
        self.assertEqual(self.hook(self.event(skill, tool="Read", agent_id="agent-7")), first)
        self.assertIsNone(self.hook(self.event(skill, tool="Read", agent_id="agent-7")))
        self.assertEqual(self.hook(self.event(files["rule-invariants"], tool="Read", agent_id="agent-7")),
                         self.rule_block("rule-invariants"))                # its second kind: no litmus
        self.assertEqual(self.hook(self.event(skill, tool="Read", agent_id="agent-8")), first)
        self.assertEqual(self.hook(self.event(skill, tool="Read", session="s2")), first)
        markers = sorted(os.path.relpath(os.path.join(base, f), self.state)
                         for base, _, names in os.walk(self.state) for f in names)
        root = f"claude-{self.plugin_name}-plugin"
        self.assertIn(os.path.join(root, "s1", "main", "skill.seen"), markers)
        self.assertIn(os.path.join(root, "s1", "agent-7", "skill.seen"), markers)
        self.assertIn(os.path.join(root, "s2", "main", "skill.seen"), markers)
        for agent in (("s1", "main"), ("s1", "agent-7"), ("s1", "agent-8"), ("s2", "main")):
            self.assertIn(os.path.join(root, *agent, "litmus.seen"), markers)   # one more marker tracks it

    def test_no_delivered_payload_holds_a_placeholder_or_an_unexpanded_variable(self):
        """What reaches the model must be runnable as written: the rule body carries no command, and the one
        line appended to it has the tool's real path."""
        import re
        files = {
            "skill": write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n"),
            "rule": write(self.project, ".claude/rules/r.md", "---\npaths: \"src/**\"\n---\n# R\n\nApplies when x.\n"),
            "agent": write(self.project, ".claude/agents/a.md", "---\nname: a\ndescription: d\n---\nbody\n"),
            "memory": write(self.project, "CLAUDE.md", "# P\n"),
            "hooks": write(self.project, ".claude/settings.json", "{}\n"),
        }
        self.assertEqual(set(files), {kind for kind, (rule, _) in cl.KIND_GUIDES.items() if rule})
        for n, (kind, path) in enumerate(files.items()):
            with self.subTest(kind=kind):
                raw = run("hook", stdin=self.event(path, tool="Read", session=f"p{n}"), env=self.env).stdout
                ctx = json.loads(raw)["hookSpecificOutput"]["additionalContext"]
                for text in (raw, ctx):
                    self.assertNotIn("<plugin>", text)
                    self.assertNotIn("<abs", text)
                    self.assertIsNone(re.search(r"\$\{?[A-Za-z_]", text), text)       # ${CLAUDE_PLUGIN_ROOT}, $VAR
                last = ctx.split("\n")[-1]
                self.assertEqual(last, self.HOOKTOOL_LINE if kind == "hooks" else self.LINT_LINE)
                self.assertEqual(ctx.count(": python3 \""), 1)
                tool = last.split('"')[1]
                self.assertTrue(os.path.isabs(tool) and os.path.isfile(tool), tool)
                self.assertEqual(os.path.realpath(tool), tool)                    # from the script's real path
        # a plugin installed under a path with a space: still one quoted, runnable word
        self.assertEqual(cl.tool_command("skill", "/opt/my plugins/kit"), 'python3 "/opt/my plugins/kit/scripts/claude-lint" rules')
        self.assertEqual(cl.tool_command("hooks", "/p"), 'python3 "/p/skills/authoring-hooks/scripts/hooktool.py" events')

    def kind_files(self):
        return {
            "skill": write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n"),
            "rule": write(self.project, ".claude/rules/r.md", "---\npaths: \"src/**\"\n---\n# R\n\nApplies when x.\n"),
            "agent": write(self.project, ".claude/agents/a.md", "---\nname: a\ndescription: d\n---\nbody\n"),
            "memory": write(self.project, "CLAUDE.md", "# P\n"),
            "hooks": write(self.project, ".claude/settings.json", "{}\n"),
        }

    def test_every_kinds_appended_line_is_one_command_that_runs_as_written(self):
        """Pasted into a shell, the command after the colon must run and exit 0 - no pipeline, no placeholder."""
        files = self.kind_files()
        for n, (kind, path) in enumerate(files.items()):
            with self.subTest(kind=kind):
                ctx = self.hook(self.event(path, tool="Read", session=f"c{n}"))
                line = ctx.split("\n")[-1]
                self.assertNotIn("|", line)
                command = line.split(": ", 1)[1]
                r = subprocess.run(command, shell=True, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, (command, r.stderr))
                self.assertTrue(r.stdout.strip(), command)

    def test_installed_natively_delivers_the_litmus_and_the_command_not_the_rule(self):
        files = self.kind_files()
        for kind, path in files.items():
            rule = cl.KIND_GUIDES[kind][0]
            installed = os.path.join(self.project, ".claude", "rules", f"{self.plugin_name}-{rule}")
            write(self.project, os.path.relpath(installed, self.project), "no paths: loads everywhere\n")
        lines = {kind: self.HOOKTOOL_LINE if kind == "hooks" else self.LINT_LINE for kind in files}
        # first touch of any kind: litmus + the command line, no rule body; a second kind: the line alone
        first = self.hook(self.event(files["skill"], tool="Read"))
        self.assertEqual(first, self.litmus() + lines["skill"])
        self.assertNotIn("rule skill-invariants", first)
        self.assertIsNone(self.hook(self.event(files["skill"], tool="Read")))
        self.assertEqual(self.hook(self.event(files["hooks"], tool="Read")), lines["hooks"])
        # another session starts again with the litmus, whichever kind comes first
        self.assertEqual(self.hook(self.event(files["hooks"], tool="Read", session="s2")),
                         self.litmus() + lines["hooks"])
        # and a Write is still linted after it
        bad = write(self.project, "skills/bad/SKILL.md", "---\nname: BAD\n---\nbody\n")
        ctx = self.hook(self.event(bad, session="s3"))
        self.assertTrue(ctx.startswith(self.litmus() + self.LINT_LINE + "\n\n[claude-lint] "))

    def test_rule_delivered_by_the_hook_leads_with_litmus_once_then_each_kinds_line(self):
        files = self.kind_files()
        self.assertEqual(self.hook(self.event(files["skill"], tool="Read")),
                         self.litmus() + self.rule_block("skill-invariants"))
        self.assertEqual(self.hook(self.event(files["hooks"], tool="Read")),
                         self.rule_block("hook-invariants", self.HOOKTOOL_LINE))

    def test_no_session_id_means_no_delivery(self):
        skill = write(self.project, "skills/a/SKILL.md", "---\nname: BAD\n---\nbody\n")
        ctx = self.hook(json.dumps({"tool_name": "Write", "tool_input": {"file_path": skill}}))
        self.assertTrue(ctx.startswith("[claude-lint] "))
        self.assertEqual(os.listdir(self.state), [])

    def test_startup_clear_and_compact_reset_and_other_sources_do_not(self):
        skill = write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n")

        def start(source, session="s1"):
            r = run("hook", stdin=json.dumps({"session_id": session, "hook_event_name": "SessionStart",
                                              "source": source, "cwd": self.project}), env=self.env)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))   # SessionStart stdout is context

        def delivered(**extra):
            return self.hook(self.event(skill, tool="Read", **extra)) is not None
        self.assertTrue(delivered())
        self.assertTrue(delivered(agent_id="sub"))
        for source in ("resume", "fork", "", "nonsense"):       # the delivered text is still in context
            start(source)
            self.assertFalse(delivered(), source)
        start("compact", session="another")
        self.assertFalse(delivered())
        # startup too: a session can start with an id that already has markers (a child `claude -p` run
        # inherits its parent's id in some environments), and it has none of the delivered text
        self.assertEqual(cl.RESET_SOURCES, ("startup", "clear", "compact"))
        for source in cl.RESET_SOURCES:
            start(source)
            ctx = self.hook(self.event(skill, tool="Read"))
            self.assertTrue(ctx.startswith(self.litmus() + f"[{self.plugin_name}] rule skill-invariants"), source)
            self.assertTrue(delivered(agent_id="sub"), source)                 # every agent of the session
            self.assertFalse(delivered(), source)

    def state_files(self):
        return sorted(os.path.relpath(os.path.join(base, f), self.tmp)
                      for base, _, names in os.walk(self.tmp) for f in names)

    def start(self, session, source="startup"):
        r = run("hook", stdin=json.dumps({"session_id": session, "hook_event_name": "SessionStart",
                                          "source": source, "cwd": self.project}), env=self.env)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_a_session_id_cannot_leave_the_marker_root(self):
        """`..` as a session id made the session directory the temp directory itself, and a reset then deleted
        every `*.seen` under each sibling directory there."""
        skill = write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n")
        root = os.path.join(self.state, f"claude-{self.plugin_name}-plugin")
        # other programs' files: siblings of the marker root in the temp directory, and files above it
        for rel in ("other-tool/cache.seen", "other-tool/deep/x.seen", "top.seen"):
            write(self.state, rel, "not ours\n")
        write(self.tmp, "above/x.seen", "not ours\n")
        self.assertTrue(self.hook(self.event(skill, tool="Read", session="real")))
        write(root, "real/main/notes.txt", "not a marker\n")
        inside = os.path.relpath(root, self.tmp) + os.sep
        real = os.path.join(inside, "real") + os.sep

        def others():
            """Every file that is not a hostile session's own: outside the marker root, or the real session's."""
            return [p for p in self.state_files() if not p.startswith(inside) or p.startswith(real)]

        before = others()
        self.assertEqual(len(before), 8)
        hostile = ("..", ".", "", "...", "../..", "../../above", "/", "//", "real/..", "..\\..", "\x00", "a\x00b",
                   "../" + os.path.basename(root) + "/real", os.path.join(self.tmp, "above"), 7, None, ["x"], {"a": 1})
        for session in hostile:
            with self.subTest(session=session):
                for source in cl.RESET_SOURCES:
                    self.start(session, source)
                self.assertEqual(others(), before)                           # nothing deleted that is not its own
                usable = cl.safe_id(session) is not None
                for agent_id in (None, "..", "../../above"):
                    extra = {"agent_id": agent_id} if agent_id else {}
                    ctx = self.hook(self.event(skill, tool="Read", session=session, **extra))
                    self.assertEqual(ctx is not None, usable)                # an unusable id: an unknown session
                self.assertEqual(others(), before)                           # nothing written outside the root
                for path in self.state_files():                              # and under it: session/agent/marker
                    if path.startswith(inside):
                        self.assertEqual(len(path[len(inside):].split(os.sep)), 3, path)
        # the pure pieces: one directory name or nothing, and a path that is a direct child of the root
        for bad in ("..", ".", "", "...", None, 7, b"x"):
            self.assertIsNone(cl.safe_id(bad), bad)
            self.assertIsNone(cl.session_marker_dir("/t", "kit", bad))
            self.assertIsNone(cl.marker_path("/t", "kit", bad, None, "skill"))
        self.assertEqual(cl.safe_id("../../etc"), ".._.._etc")
        self.assertEqual(cl.safe_id("a/b\\c d\x00é"), "a_b_c_d__")
        self.assertEqual(cl.safe_id("0199-ab_c.d"), "0199-ab_c.d")
        self.assertEqual(len(cl.safe_id("x" * 500)), 120)
        self.assertEqual(cl.session_marker_dir("/t", "kit", "../x"), os.path.join("/t", "claude-kit-plugin", ".._x"))
        # an agent id is one directory name too: `..` would have filed a subagent's markers in the root
        self.assertEqual(cl.marker_path("/t", "kit", "s", "..", "skill"),
                         os.path.join("/t", "claude-kit-plugin", "s", "unknown", "skill.seen"))
        self.assertEqual(cl.marker_path("/t", "kit", "s", "../../x", "skill"),
                         os.path.join("/t", "claude-kit-plugin", "s", ".._.._x", "skill.seen"))
        self.assertEqual(cl.marker_path("/t", "kit", "s", "", "../k"),
                         os.path.join("/t", "claude-kit-plugin", "s", "main", ".._k.seen"))

    def test_reset_deletes_only_inside_that_sessions_directory(self):
        skill = write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n")
        root = os.path.join(self.state, f"claude-{self.plugin_name}-plugin")
        for session in ("mine", "theirs"):
            self.assertTrue(self.hook(self.event(skill, tool="Read", session=session)))
            self.assertTrue(self.hook(self.event(skill, tool="Read", session=session, agent_id="sub")))
        outside = write(self.tmp, "outside/agent/skill.seen", "not ours\n")
        os.symlink(os.path.join(self.tmp, "outside", "agent"), os.path.join(root, "mine", "linked-agent"))
        os.symlink(os.path.join(self.tmp, "outside"), os.path.join(root, "linked-session"))
        write(root, "mine/main/keep.txt", "not a marker\n")
        write(root, "mine/stray.seen", "not in an agent directory\n")
        self.start("mine")
        self.start("linked-session")                             # a symlink where a session directory would be
        left = [p for p in self.state_files() if p.startswith(os.path.join("state", os.path.basename(root)))]
        mine = os.path.join("state", os.path.basename(root), "mine")
        theirs = os.path.join("state", os.path.basename(root), "theirs")
        self.assertEqual(left, sorted([os.path.join(mine, "main", "keep.txt"), os.path.join(mine, "stray.seen")]
                                      + [os.path.join(theirs, agent, name) for agent in ("main", "sub")
                                         for name in ("litmus.seen", "skill.seen")]))
        self.assertTrue(os.path.isfile(outside))                 # the links were not followed
        self.assertTrue(os.path.islink(os.path.join(root, "mine", "linked-agent")))

    def test_marker_directories_older_than_a_week_are_pruned_at_a_reset(self):
        skill = write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n")
        root = os.path.join(self.state, f"claude-{self.plugin_name}-plugin")
        for session in ("old", "old-with-a-file", "recent", "current"):
            self.assertTrue(self.hook(self.event(skill, tool="Read", session=session)))
            self.assertTrue(self.hook(self.event(skill, tool="Read", session=session, agent_id="sub")))
        write(root, "old-with-a-file/main/notes.txt", "not a marker\n")
        write(root, "stray-file", "not a session directory\n")
        os.symlink(os.path.join(self.tmp, "proj"), os.path.join(root, "linked"))
        now = time.time()

        def age(session, days):
            for base, dirs, _ in os.walk(os.path.join(root, session)):
                os.utime(base, (now - days * 86400, now - days * 86400))

        age("old", 8)
        age("old-with-a-file", 30)
        age("recent", 6)
        age("current", 30)                                       # the session being reset is never pruned
        os.utime(os.path.join(root, "recent", "sub"), (now, now))   # used an hour ago: the newest directory counts
        self.start("current", "compact")
        self.assertEqual(sorted(os.listdir(root)), ["current", "linked", "old-with-a-file", "recent", "stray-file"])
        self.assertEqual(sorted(os.listdir(os.path.join(root, "old-with-a-file"))), ["main"])
        self.assertEqual(os.listdir(os.path.join(root, "old-with-a-file", "main")), ["notes.txt"])
        self.assertEqual(sorted(os.listdir(os.path.join(root, "recent", "main"))), ["litmus.seen", "skill.seen"])
        self.assertTrue(os.path.isdir(self.project))             # a symlink in the root is not followed
        for source in ("resume", "fork"):                        # no reset, so no pruning either
            age("recent", 8)
            self.start("current", source)
            self.assertIn("recent", os.listdir(root))
        # the decision is a pure function of the ages
        week = cl.MARKER_MAX_AGE_S
        self.assertEqual(week, 7 * 24 * 3600)
        now = 10 * week
        self.assertEqual(cl.stale_sessions((("a", 0), ("b", now - week), ("c", now - week - 1), ("d", now)), now=now),
                         ("a", "c"))
        self.assertEqual(cl.stale_sessions((), now=now), ())
        cl.prune_markers(os.path.join(self.tmp, "missing"), time.time())         # nothing there: no raise

    def test_reset_script_and_hooks_json(self):
        skill = write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n")
        self.assertIsNotNone(self.hook(self.event(skill, tool="Read")))
        reset = os.path.join(ROOT, "hooks", "reset-rule-delivery.sh")
        payload = json.dumps({"session_id": "s1", "hook_event_name": "SessionStart", "source": "compact"})
        r = subprocess.run(["sh", reset], input=payload, capture_output=True, text=True,
                           env=dict(self.env, CLAUDE_PLUGIN_ROOT=ROOT))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertIsNotNone(self.hook(self.event(skill, tool="Read")))
        r = subprocess.run(["sh", reset], input=payload, capture_output=True, text=True, env=self.env)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))       # no plugin root: a no-op
        with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "Read|Write|Edit")
        self.assertEqual(len(hooks["SessionStart"]), 1)                         # no hook runs unscoped at start
        self.assertEqual(hooks["SessionStart"][0]["matcher"], "|".join(cl.RESET_SOURCES))
        self.assertEqual(hooks["SessionStart"][0]["hooks"][0]["command"],
                         'sh "${CLAUDE_PLUGIN_ROOT}/hooks/reset-rule-delivery.sh"')
        self.assertFalse(os.path.exists(os.path.join(ROOT, "hooks", "seam-punchline.sh")))
        hooktool = cl.find_hooktool()
        report = json.loads(subprocess.run([sys.executable, hooktool, "validate", os.path.join(ROOT, "hooks", "hooks.json"),
                                            "--json"], capture_output=True, text=True).stdout)
        self.assertEqual(report, {"valid": True, "errors": [], "warnings": []})

    def test_shim_passes_reads_through_and_agrees_with_the_linter(self):
        skill = write(self.project, "skills/a/SKILL.md", "---\nname: BAD\n---\nbody\n")
        env = dict(self.env, CLAUDE_PLUGIN_ROOT=ROOT)
        big = "x = 1  # filler\n" * 200000                                        # a 3 MB file riding in a Read
        r = subprocess.run(["sh", SHIM], input=self.event(skill, tool="Read", tool_response={"file": {"content": big}}),
                           capture_output=True, text=True, env=env)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("rule skill-invariants", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])
        py = write(self.project, "src/app.py", "x = 1\n")
        notes = write(self.project, "docs/notes.md", "x\n")
        for path in (py, notes):
            r = subprocess.run(["sh", SHIM], input=self.event(path, tool="Read", tool_response={"file": {"content": big}}),
                               capture_output=True, text=True, env=env)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_an_installed_rule_is_left_to_claude_code(self):
        r = run("install-rules", "--target", self.project)
        self.assertEqual(r.returncode, 0, r.stderr)
        skill = write(self.project, "skills/a/SKILL.md", "---\nname: BAD\n---\nbody\n")
        rule = write(self.project, ".claude/rules/mine.md", "---\npaths: \"src/**\"\n---\n# R\n\nApplies when x.\n")
        memory = write(self.project, "CLAUDE.md", "# P\n")
        ctx = self.hook(self.event(skill))
        # no rule body: the litmus and the kind's command line, then the findings
        self.assertTrue(ctx.startswith(self.litmus() + self.LINT_LINE + "\n\n[claude-lint] "))
        self.assertNotIn("rule skill-invariants", ctx)
        self.assertIsNone(self.hook(self.event(skill, tool="Read")))            # once per kind
        for path in (rule, memory):                                              # a second kind: its line, no litmus
            self.assertEqual(self.hook(self.event(path, tool="Read")), self.LINT_LINE)
        # the installed agent rule is scoped to .claude/agents/; a plugin's own agents/ is not matched by it,
        # so Claude Code will not load it there and the hook still does
        write(self.project, ".claude-plugin/plugin.json", '{"name": "demo"}\n')
        plugin_agent = write(self.project, "agents/a.md", "---\nname: a\ndescription: d\n---\nbody\n")
        self.assertIn("rule subagent-invariants", self.hook(self.event(plugin_agent, tool="Read")))
        project_agent = write(self.project, ".claude/agents/b.md", "---\nname: b\ndescription: d\n---\nbody\n")
        agent_line = self.hook(self.event(project_agent, tool="Read", session="s9"))
        self.assertEqual(agent_line, self.litmus() + self.LINT_LINE)           # installed: no rule body
        # a symlinked copy is not loaded by Claude Code, so it does not count as installed
        installed = os.path.join(self.project, ".claude", "rules", f"{self.plugin_name}-claude-md-invariants.md")
        os.remove(installed)
        os.symlink(os.path.join(ROOT, "rules", "claude-md-invariants.md"), installed)
        self.assertIn("rule claude-md-invariants", self.hook(self.event(memory, tool="Read", session="s9")))

    def test_project_dir_from_the_environment_wins_over_cwd(self):
        run("install-rules", "--target", self.project)
        skill = write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n")
        elsewhere = dict(json.loads(self.event(skill, tool="Read")), cwd=os.path.join(self.project, "skills"))
        self.assertIsNotNone(self.hook(json.dumps(elsewhere)))                   # cwd has no installed rules
        self.env["CLAUDE_PROJECT_DIR"] = self.project
        native = self.hook(json.dumps(dict(elsewhere, session_id="s2")))
        self.assertEqual(native, self.litmus() + self.LINT_LINE)                 # installed: no rule body
        self.assertNotIn("rule skill-invariants", native)

    def test_an_unusable_state_directory_never_silences_or_breaks(self):
        skill = write(self.project, "skills/a/SKILL.md", "---\nname: BAD\n---\nbody\n")
        with open(os.path.join(self.state, f"claude-{self.plugin_name}-plugin"), "w") as f:
            f.write("a file where the state directory should be\n")
        for _ in range(2):                                    # cannot be recorded: delivered each time
            ctx = self.hook(self.event(skill))
            self.assertIn("rule skill-invariants", ctx)
            self.assertIn("SK001", ctx)
        self.assertTrue(cl.claim_delivery(os.path.join(self.state, f"claude-{self.plugin_name}-plugin", "s", "a", "k.seen")))

    def test_two_hooks_racing_deliver_once(self):
        skill = write(self.project, "skills/a/SKILL.md", "---\ndescription: d\n---\nbody\n")
        payload = self.event(skill, tool="Read", session="race")
        procs = [subprocess.Popen([sys.executable, LINT, "hook"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, env=self.env) for _ in range(8)]
        outs = [p.communicate(payload) for p in procs]
        self.assertTrue(all(p.returncode == 0 for p in procs))
        self.assertEqual([err for _, err in outs if err], [])
        self.assertEqual(sum(1 for out, _ in outs if out), 1)
        marker = cl.marker_path(self.state, "p", "s", None, "skill")
        self.assertEqual([cl.claim_delivery(marker) for _ in range(3)], [True, False, False])

    def test_pure_pieces(self):
        rule_text = "---\npaths:\n  - \"**/SKILL.md\"\n---\n# T\n\nbody\n"
        self.assertEqual(cl.delivery_text("kit", "skill-invariants.md", rule_text), "[kit] rule skill-invariants\n\n# T\n\nbody")
        self.assertEqual(cl.delivery_text("kit", "skill-invariants.md", rule_text, 'Run: python3 "/p/x" rules'),
                         "[kit] rule skill-invariants\n\n# T\n\nbody\n\n" 'Run: python3 "/p/x" rules')
        self.assertEqual(cl.command_line("hooks", "/p"),
                         'Hook events and handler fields: python3 "/p/skills/authoring-hooks/scripts/hooktool.py" events')
        self.assertEqual(cl.litmus_text("kit"), "[kit] Litmus for any model-facing prose you write or edit: if you "
                         "could write an assertion for it, write code; if you would need a rubric, write prose.")
        self.assertEqual(cl.marker_path("/t", "kit", "a/b c", None, "skill"),
                         os.path.join("/t", "claude-kit-plugin", "a_b_c", "main", "skill.seen"))
        self.assertEqual(cl.rule_paths('---\npaths:\n  - "a/**"\n  - b/*.md\n---\nx'), ("a/**", "b/*.md"))
        self.assertEqual(cl.rule_paths('---\npaths: "a/**, b/*.md"\n---\nx'), ("a/**", "b/*.md"))
        self.assertEqual(cl.rule_paths("no frontmatter"), ())
        match = cl.glob_matches
        self.assertTrue(match("/p/x/.claude/agents/team/a.md", ["**/.claude/agents/**/*.md"]))
        self.assertTrue(match("/p/.claude/agents/a.md", ["**/.claude/agents/**/*.md"]))
        self.assertFalse(match("/p/agents/a.md", ["**/.claude/agents/**/*.md"]))
        self.assertTrue(match("/p/.claude/settings.local.json", ["**/.claude/settings*.json"]))
        self.assertFalse(match("/p/.claude/settings/x.json", ["**/.claude/settings*.json"]))
        self.assertTrue(match("/p/src/a.tsx", ["src/**/*.{ts,tsx}"]))
        self.assertFalse(match("/p/src/a.jsx", ["src/**/*.{ts,tsx}"]))
        self.assertTrue(match("/p/lib/b1.py", ["lib/[ab]?.py"]))
        self.assertFalse(match("/p/x", ["[unclosed"]))                        # a bad glob matches nothing, no raise
        self.assertTrue(cl.loads_natively("no paths: loads in every session", "/any/file"))
        self.assertFalse(cl.loads_natively('---\npaths: "**/SKILL.md"\n---\nx', "/p/commands/x.md"))
        reset = os.path.join(self.state, "sess")
        for agent in ("main", "sub"):
            self.assertTrue(cl.claim_delivery(os.path.join(reset, agent, "skill.seen")))
        cl.reset_delivery(reset)
        cl.reset_delivery(os.path.join(self.state, "missing"))               # nothing there: no raise
        self.assertTrue(cl.claim_delivery(os.path.join(reset, "main", "skill.seen")))

    def test_peek_reads_the_path_without_parsing(self):
        compact = b'{"session_id":"s","tool_name":"Read","tool_input":{"file_path":"/r/docs/n.md"},"tool_response":{}}'
        self.assertEqual(cl.peek_file_path(compact), "/r/docs/n.md")
        self.assertEqual(cl.peek_file_path(json.dumps({"tool_input": {"file_path": "/r/a b.md"}}).encode()), "/r/a b.md")
        self.assertEqual(cl.peek_file_path('{"tool_input":{"file_path":"/r/café.md"}}'.encode()), "/r/café.md")
        for unsure in (b'{"tool_input":{"file_path":"/r/a\\"b.md"}}', b'{"tool_input":{"file_path":"\\/r\\/a.md"}}',
                       b'{"tool_input":{"content":"x","file_path":"/r/a.md"}}', b'{"tool_input":{"file_path":"/r/a',
                       b'{"x":"\\"tool_input\\":{\\"file_path\\":\\"/r/a.md\\""}', b""):
            self.assertIsNone(cl.peek_file_path(unsure), unsure)
        # a large Read of a file that is not an artifact: decided from the first bytes, never parsed
        big = '{"tool_name":"Read","tool_input":{"file_path":"/r/docs/n.md"},"tool_response":{"content":"' \
              + "x" * 3_000_000 + '"}}'
        r = subprocess.run([sys.executable, "-X", "importtime", LINT, "hook"], input=big, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertNotIn("json", {ln.rsplit("|", 1)[-1].strip() for ln in r.stderr.splitlines()})
        self.assertIsNone(cl.read_hook_payload(big))
        self.assertEqual(cl.read_hook_payload('{"hook_event_name":"SessionStart","source":"clear","session_id":"s"}')[0],
                         "reset")


# ---- the auditor's Bash boundary ------------------------------------------------

GUARD = os.path.join(ROOT, "hooks", "auditor-bash-guard.sh")


class AuditorBashGuardTests(TempCase):
    """The auditor agent holds Bash only to run the linter. A PreToolUse hook holds it to that - for that
    agent alone - and costs every other Bash call a shell start."""

    def setUp(self):
        super().setUp()
        self.plugin_name = cl.own_plugin_name()
        self.auditor = f"{self.plugin_name}:{cl.AUDITOR_AGENT}"
        self.env = dict({k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}, CLAUDE_PLUGIN_ROOT=ROOT)

    def event(self, command, agent_type="auditor", compact=True, **extra):
        # the field order and the compact form are those of a real payload (logged from a headless run, 2.1.296)
        data = {"session_id": "s1", "cwd": self.tmp, "permission_mode": "default"}
        if agent_type:
            data.update(agent_id="a9fa001fce5346f86", agent_type=self.auditor if agent_type == "auditor" else agent_type)
        data.update(hook_event_name="PreToolUse", tool_name="Bash",
                    tool_input={"command": command, "description": "d"}, tool_use_id="toolu_01")
        data.update(extra)
        return json.dumps(data, separators=(",", ":")) if compact else json.dumps(data, indent=2)

    def guard(self, payload):
        """Run the shim as Claude Code does; the linter run directly must agree with it."""
        shim = subprocess.run(["sh", GUARD], input=payload, capture_output=True, text=True, env=self.env)
        direct = run("hook", stdin=payload, env=self.env)
        self.assertEqual((shim.returncode, shim.stdout, shim.stderr), (direct.returncode, direct.stdout, direct.stderr))
        self.assertEqual(shim.stdout, "")
        return shim

    def assert_allowed(self, command, **kwargs):
        for compact in (True, False):
            r = self.guard(self.event(command, compact=compact, **kwargs))
            self.assertEqual((r.returncode, r.stderr), (0, ""), command)

    def assert_blocked(self, command, reason, **kwargs):
        for compact in (True, False):
            r = self.guard(self.event(command, compact=compact, **kwargs))
            self.assertEqual(r.returncode, 2, command)
            # the block says what was refused, why the boundary exists, and the command that is allowed
            self.assertTrue(r.stderr.startswith(f"[{self.plugin_name}] Bash call blocked for the "
                                                f"{cl.AUDITOR_AGENT} agent: {reason}. "), r.stderr)
            self.assertIn("read-only and holds Bash only to run this plugin's linter", r.stderr)
            self.assertIn(f'python3 "{LINT}" <path>', r.stderr)
            self.assertIn(f'python3 "{LINT}" --all <dir>', r.stderr)
            self.assertIn("use Read, Glob and Grep", r.stderr)
            self.assertNotIn("<plugin>", r.stderr)
            self.assertNotIn("${", r.stderr)

    def test_one_linter_invocation_passes(self):
        target = write(self.tmp, "skills/demo/SKILL.md", "---\ndescription: d\n---\nbody\n")
        for command in (f'python3 "{LINT}" {target}',                     # the form the agent is given
                        f'python3 "{LINT}" --all {self.tmp}',
                        f'python3 "{LINT}" --json "{self.tmp}/skills/my demo"',
                        f"python3 '{LINT}' rules",
                        f'python3 "{LINT}" fields agent tools',
                        f'  python3   "{LINT}"   --all   .  ',
                        f'python3 "{LINT}" check-injection \'git log | head -3 || echo none\' --allowed-tools "Bash(git *)"',
                        f'python3 "{LINT}" install-rules --check',
                        f'python3 "{LINT}" install-rules --target {self.tmp} --dry-run',
                        f'python3 "{LINT}"'):
            with self.subTest(command=command):
                self.assert_allowed(command)
        link = os.path.join(self.tmp, "lint-link")
        os.symlink(LINT, link)
        self.assert_allowed(f'python3 "{link}" rules')                    # the same script by another path
        self.assert_allowed(f'python3 "{LINT}" rules', agent_type=cl.AUDITOR_AGENT)   # a copy outside the plugin

    def test_each_shell_operator_is_blocked(self):
        base = f'python3 "{LINT}" .'
        for tail, reason in (("; ls", "it uses the shell operator `;`"),
                             ("&& ls", "it uses the shell operator `&&`"),
                             ("|| ls", "it uses the shell operator `||`"),
                             ("| head", "it uses the shell operator `|`"),
                             ("|& head", "it uses the shell operator `|`"),
                             ("&", "it uses the shell operator `&`"),
                             ("> out.txt", "it uses the shell operator `>`"),
                             (">> out.txt", "it uses the shell operator `>>`"),
                             ("2>&1", "it uses the shell operator `>&`"),
                             ("2> /dev/null", "it uses the shell operator `>`"),
                             ("&> out.txt", "it uses the shell operator `&>`"),
                             ("< in.txt", "it uses the shell operator `<`"),
                             ("<<< x", "it uses the shell operator `<<<`"),
                             ("<(ls)", "it uses the shell operator `<`"),
                             ("\nls", "it is more than one command line"),
                             ("`ls`", "it uses command substitution or `$'...'` quoting"),
                             ("$(ls)", "it uses command substitution or `$'...'` quoting"),
                             ('"$(ls)"', "it uses command substitution or `$'...'` quoting"),
                             ('"it\'s $(ls) \'s"', "it uses command substitution or `$'...'` quoting"),
                             ("$'a\\'; ls #'", "it uses the shell operator `;`")):
            with self.subTest(tail=tail):
                self.assert_blocked(f"{base} {tail}", reason)
        self.assert_blocked(f"(python3 \"{LINT}\" .)", "it opens a subshell")
        self.assert_blocked(f"{{ python3 \"{LINT}\" . }}", "it uses group syntax")
        self.assert_blocked(f"python3 \"{LINT}\" $'x'", "it uses command substitution or `$'...'` quoting")
        # the same characters as data, inside single quotes, are an argument and pass
        self.assert_allowed(f"python3 \"{LINT}\" check-injection 'echo $(date) `id` ; a > b'")

    def test_any_other_command_is_blocked(self):
        other = write(self.tmp, "scripts/claude-lint", "print('not the linter')\n")
        for command, reason in (
                ("ls", "it runs `ls`"),
                ("cat CLAUDE.md", "it runs `cat`"),
                ("rm -rf build", "it runs `rm`"),
                ("git status", "it runs `git`"),
                ("", "it is empty"),
                ("   ", "it is empty"),
                ("# just a comment", "it is empty"),
                ("python3 -c 'print(1)'", "`python3` is not given this plugin's linter as its script"),
                (f'python3 -c "import os" "{LINT}"', "`python3` is not given this plugin's linter as its script"),
                (f'python3 "{other}" .', "`python3` is not given this plugin's linter as its script"),
                ("python3 scripts/claude-lint .", "`python3` is not given this plugin's linter as its script"),
                ("python3", "`python3` is not given this plugin's linter as its script"),
                (f'python3 -m pdb "{LINT}"', "`python3` is not given this plugin's linter as its script"),
                (f'python "{LINT}" .', "it runs `python`"),
                (f'"{LINT}" .', f"it runs `{LINT[:60]}`"),
                (f'sh -c \'python3 "{LINT}" .\'', "it runs `sh`"),
                (f'env python3 "{LINT}" .', "it runs `env`"),
                (f'PYTHONSTARTUP=x.py python3 "{LINT}" .', "it runs `PYTHONSTARTUP=x.py`"),
                (f'python3 "{LINT}" install-rules', "`install-rules` writes files; only its --check and --dry-run forms read"),
                (f'python3 "{LINT}" install-rules --target .', "`install-rules` writes files; only its --check and --dry-run forms read")):
            with self.subTest(command=command):
                self.assert_blocked(command, reason)

    def test_every_other_session_and_agent_is_untouched(self):
        for command in ("ls", "rm -rf /", f'python3 "{LINT}" . | head', "echo authoring-auditor",
                        'grep -r "authoring-auditor" agents', "cat agents/authoring-auditor",
                        f"echo '\"agent_type\":\"{self.auditor}\"'"):
            for agent_type in (None, "general-purpose", "Explore", f"other-plugin:{cl.AUDITOR_AGENT}",
                               f"{self.plugin_name}:other-agent", self.auditor + "-2", "x" + cl.AUDITOR_AGENT):
                with self.subTest(command=command, agent_type=agent_type):
                    self.assert_allowed(command, agent_type=agent_type)
        # only a Bash call that has not run yet is judged: the auditor's other events pass through
        for extra in ({"tool_name": "Read"}, {"hook_event_name": "PostToolUse"}, {"hook_event_name": "PermissionRequest"}):
            r = self.guard(self.event("ls", **extra))
            self.assertEqual((r.returncode, r.stderr), (0, ""), extra)

    def test_a_payload_that_cannot_be_judged_never_blocks(self):
        auditor = f'"agent_type":"{self.auditor}"'
        hostile = ["", "\n", "not json", "{", "[]", "null", "7", '"x"', "{}", "\x00\x01", "{" * 5000,
                   '{"hook_event_name":"PreToolUse"}', "{" + auditor + "}",
                   '{"hook_event_name":"PreToolUse",' + auditor,                               # cut off
                   '{"hook_event_name":"PreToolUse","tool_name":"Bash",' + auditor + "}",       # no tool_input
                   '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":7,' + auditor + "}",
                   '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{},' + auditor + "}",
                   '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":7},' + auditor + "}",
                   '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":["ls"]},' + auditor + "}",
                   '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"ls"},"agent_type":7}',
                   '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"ls"},'
                   '"agent_type":["' + self.auditor + '"]}',
                   '[{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"ls"},' + auditor + "}]",
                   self.event("ls")[:-1], self.event("ls") + "trailing"]
        for payload in hostile:
            with self.subTest(payload=payload[:60]):
                r = self.guard(payload)
                self.assertEqual((r.returncode, r.stderr), (0, ""))
        rng = random.Random(20261011)
        alphabet = list("ab $(){}[]<>|&;'\"`\\\n\t#=*!~/.-012") + ["$(", "${", "||", "&&", ">>", "2>", "$'", "python3 ", f'"{LINT}" ']
        for _ in range(3000):                                    # the judgement itself never raises
            command = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 30)))
            self.assertIsInstance(cl.auditor_bash_refusal(command, LINT), (str, type(None)))

    def test_the_shim_starts_python_only_for_a_payload_that_names_the_agent(self):
        fake = os.path.join(self.tmp, "fakebin")
        os.makedirs(fake)
        mark = os.path.join(self.tmp, "python-started")
        with open(os.path.join(fake, "python3"), "w") as f:
            f.write(f"#!/bin/sh\n: > '{mark}'\ncat > /dev/null\n")
        os.chmod(os.path.join(fake, "python3"), 0o755)

        def started(payload):
            if os.path.exists(mark):
                os.remove(mark)
            r = subprocess.run(["sh", GUARD], input=payload, capture_output=True, text=True,
                               env=dict(self.env, PATH=fake + os.pathsep + "/usr/bin:/bin"))
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
            return os.path.exists(mark)

        self.assertFalse(started(self.event("ls", agent_type=None)))                   # the main session
        self.assertFalse(started(self.event("ls", agent_type="general-purpose")))
        self.assertFalse(started(self.event("x = 1\n" * 20000, agent_type=None)))
        self.assertFalse(started(self.event('grep "authoring-auditor" -r .', agent_type=None)))   # \" is not "
        self.assertFalse(started(""))
        self.assertTrue(started(self.event("ls")))
        self.assertTrue(started(self.event("ls", agent_type=cl.AUDITOR_AGENT)))
        self.assertTrue(started(self.event("cat agents/authoring-auditor", agent_type=None)))   # unsure: Python decides
        # fails closed for a payload that may be the auditor's: with no linter, no python3, or a
        # linter that crashes, the call is blocked with the reason - and any other payload still passes
        only_cat = os.path.join(self.tmp, "only-cat")
        os.makedirs(only_cat)
        os.symlink(shutil.which("cat"), os.path.join(only_cat, "cat"))
        crashing = os.path.join(self.tmp, "crash")
        os.makedirs(crashing)
        with open(os.path.join(crashing, "python3"), "w") as f:
            f.write("#!/bin/sh\ncat > /dev/null\nexit 1\n")
        os.chmod(os.path.join(crashing, "python3"), 0o755)
        sh = shutil.which("sh")
        for env, why in (({"PATH": os.environ.get("PATH", "")}, "linter was not found"),          # no plugin root
                         ({"PATH": os.environ.get("PATH", ""), "CLAUDE_PLUGIN_ROOT": self.tmp}, "linter was not found"),
                         ({"PATH": only_cat, "CLAUDE_PLUGIN_ROOT": ROOT}, "python3 was not found"),
                         ({"PATH": crashing + os.pathsep + "/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": ROOT},
                          "guard itself failed (exit 1)")):
            r = subprocess.run([sh, GUARD], input=self.event("ls"), capture_output=True, text=True, env=env)
            self.assertEqual((r.returncode, r.stdout), (2, ""), env)
            self.assertIn(why, r.stderr)
            r = subprocess.run([sh, GUARD], input=self.event("ls", agent_type="general-purpose"),
                               capture_output=True, text=True, env=env)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""), env)
        with open(GUARD, encoding="utf-8") as f:
            code = "\n".join(ln for ln in f.read().split("\n") if not ln.lstrip().startswith("#"))
        self.assertIn("*'" + cl.AUDITOR_AGENT + "\"'*", code)                # the gate is the agent's name
        self.assertNotIn(self.plugin_name, code)                             # and the plugin's name is not in it
        self.assertLess(code.index("esac"), code.index("python3"))           # nothing starts before the gate

    def test_the_auditors_other_events_still_reach_rule_delivery(self):
        # a Read whose content mentions PreToolUse - the plugin's own hooks.json - is a touch, not a guard event
        hooks = os.path.join(ROOT, "hooks", "hooks.json")
        with open(hooks, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("PreToolUse", content)
        payload = json.dumps({"session_id": "s1", "agent_id": "a1", "agent_type": self.auditor, "cwd": self.tmp,
                              "hook_event_name": "PostToolUse", "tool_name": "Read",
                              "tool_input": {"file_path": hooks}, "tool_response": {"file": {"content": content}}},
                             separators=(",", ":"))
        step = cl.read_hook_payload(payload)
        self.assertEqual((step[0], step[3]), ("touch", hooks))
        self.assertEqual(cl.read_hook_payload(self.event("ls"))[0], "guard")
        self.assertEqual(cl.read_hook_payload(self.event("ls", compact=False))[0], "guard")
        self.assertIsNone(cl.read_hook_payload(self.event("ls", agent_type=None)))

    def test_pure_pieces_and_hooks_json(self):
        self.assertTrue(cl.is_own_auditor("kit:authoring-auditor", "kit"))
        self.assertTrue(cl.is_own_auditor("authoring-auditor", "kit"))
        for other in ("other:authoring-auditor", "kit:authoring-auditor-2", "kit:kit:authoring-auditor", "", None, 7):
            self.assertFalse(cl.is_own_auditor(other, "kit"), other)
        self.assertIsNone(cl.auditor_bash_refusal('python3 "/p/scripts/claude-lint" --all .', "/p/scripts/claude-lint"))
        self.assertEqual(cl.auditor_bash_refusal('python3 "/p/scripts/claude-lint" . | head', "/p/scripts/claude-lint"),
                         "it uses the shell operator `|`")
        message = cl.auditor_block_message("kit", "it runs `ls`")
        self.assertTrue(message.startswith("[kit] Bash call blocked for the authoring-auditor agent: it runs `ls`. "))
        for op in ("`;`", "`&&`", "`||`", "`|`", "backticks", "`$(`", "redirection"):
            self.assertIn(op, message)
        with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
            (group,) = json.load(f)["hooks"]["PreToolUse"]
        self.assertEqual(group["matcher"], "Bash")
        self.assertEqual([h["command"] for h in group["hooks"]], ['sh "${CLAUDE_PLUGIN_ROOT}/hooks/auditor-bash-guard.sh"'])
        # the agent the guard names is the agent the plugin ships
        with open(os.path.join(ROOT, "agents", cl.AUDITOR_AGENT + ".md"), encoding="utf-8") as f:
            front = cl.parse_frontmatter(f.read())
        self.assertEqual(front.get("name"), cl.AUDITOR_AGENT)
        self.assertIn("Bash", str(front.get("tools")))


# ---- hostile input ------------------------------------------------------------

class HostileInputTests(TempCase):
    def test_lexer_and_model_never_raise(self):
        rng = random.Random(20261009)
        alphabet = list("ab $(){}[]<>|&;'\"`\\\n\t#=*!~/.-012") + ["$(", "${", "||", "&&", ">>", "<<", "2>", "&>", "$((", "))"]
        for _ in range(3000):
            command = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 40)))
            allowed = "".join(rng.choice(alphabet + ["Bash(", "Bash", ", "]) for _ in range(rng.randrange(0, 20)))
            cl.injection_problems(command, allowed)
            cl.has_failure_fallback(command)
            cl.bash_entries(allowed)

    def test_hostile_files_do_not_crash_or_stall(self):
        self.plugin()
        nasty = {
            "backticks": "`" * 20000 + "\n" + " ".join("`" * n + "x" for n in range(1, 150)) + "\n",
            "directives": "".join(f"!{BT}{'(' * 50}a{i} | b ; c && d \"unterminated{BT}\n" for i in range(300)),
            "fenced": (FENCE + "!\n") * 500,
            "tokens": "**`$ARGUMENTS`** " * 5000 + "\n" + "`${CLAUDE_SKILL_DIR}` " * 5000 + "\n",
            "links": "[" * 5000 + "](" * 5000 + "\n" + "[a](" + "x" * 50000 + ")\n",
            "secrets": f"!{BT}x || echo y{BT}\n" + "A" * 200000 + "KEY=\n",
            "binary": "\x00\x01\ufffd" * 10000 + "\n---\n---\n",
            "nesting": f"!{BT}echo {'$(' * 3000}{BT}\n",
            "frontmatter-only": "",
        }
        fronts = ["description: d\n", "allowed-tools: " + "Bash(" * 2000 + "\n", "allowed-tools: [" + '"' * 999 + "\n",
                  "paths: " + "[" * 3000 + "\n", "name: " + "x" * 100000 + "\n", ": :\n- -\n\t\tx\n", "arguments: {a: [b\n"]
        cases = [("description: d\n", body) for _, body in sorted(nasty.items())]
        cases += [(front, f"!{BT}a | b{BT}\n**`$0`** [x](y.md)\n") for front in fronts]
        started = time.monotonic()
        with mock.patch.object(cl, "eprint", lambda *a: self.fail("internal error: " + " ".join(map(str, a)))):
            for i, (front, body) in enumerate(cases):
                for rel in (f"skills/h{i}/SKILL.md", f"rules/h{i}.md", f"agents/h{i}.md", f"h{i}/CLAUDE.md"):
                    with self.subTest(front=front[:20], body=body[:20], rel=rel):
                        cl.lint_file(write(self.tmp, rel, f"---\n{front}---\n{body}"))
        self.assertLess(time.monotonic() - started, 5)

    def test_a_body_dense_with_directives_is_linted_in_linear_time(self):
        # Finding each directive's line by counting newlines from the top, and re-masking the body per
        # directive, made 800 KB of directives take seconds and 5 MB take minutes. A regression to
        # quadratic shows up here as a ratio, and as the bound, long before it is that bad.
        self.plugin()
        line = f"Status: !{BT}git status --short || echo none{BT} and @notes.md then {BT}$ARGUMENTS{BT} here\n"
        block = f"{FENCE}!\ngit log -3 --oneline | head -3\n{FENCE}\n"

        def lint(n, rel):
            path = write(self.tmp, rel, "---\ndescription: d\n---\n" + (line * 9 + block) * (n // 10))
            started = time.monotonic()
            found = cl.lint_file(path)
            return time.monotonic() - started, found

        small, _ = lint(2000, "skills/small/SKILL.md")
        large, found = lint(16000, "skills/large/SKILL.md")
        self.assertLess(small, 5)
        self.assertLess(large, 20)
        self.assertLess(large, max(small, 0.05) * 40)        # 8 times the input: linear is 8, quadratic is 64
        self.assertEqual(sum(f.id == "SK012" for f in found), 16000 // 10 * 9)
        self.assertEqual([f.line for f in found if f.id == "SK008"], [4])
        # line numbers come from the precomputed offsets and are right at both ends
        text = "a\n" * 5000
        self.assertEqual([cl.line_of(text, o, 10) for o in (0, 1, 2, 9998, 9999, 10000)], [10, 10, 11, 5009, 5009, 5010])

    def test_an_internal_error_is_reported_not_raised(self):
        p = write(self.tmp, "CLAUDE.md", "x\n")
        seen = []
        with mock.patch.dict(cl.LINTERS, {"memory": lambda ctx: 1 / 0}), mock.patch.object(cl, "eprint", seen.append):
            self.assertEqual(cl.lint_file(p), [])
        self.assertIn("ZeroDivisionError", seen[0])

    def test_hostile_json_and_paths(self):
        self.plugin()
        for content in ("", "null", "[]", '"x"', "{" * 5000, '{"name": {"a": 1}}', '{"name": "\\u0000"}'):
            with self.subTest(content=content[:10]):
                cl.lint_file(write(self.tmp, ".claude-plugin/plugin.json", content))
                cl.lint_file(write(self.tmp, ".claude/settings.json", content))
        os.makedirs(os.path.join(self.tmp, "skills", "d", "SKILL.md"))          # a directory named like an artifact
        self.assertEqual(cl.lint_file(os.path.join(self.tmp, "skills", "d", "SKILL.md")), [])
        os.symlink("loop.md", os.path.join(self.tmp, "loop.md"))
        os.symlink("CLAUDE.md", os.path.join(self.tmp, "CLAUDE.md"))            # a link to itself
        self.assertEqual(cl.lint_file(os.path.join(self.tmp, "CLAUDE.md")), [])
        self.assertEqual(run("--all", self.tmp).returncode in (0, 1), True)


if __name__ == "__main__":
    unittest.main()
