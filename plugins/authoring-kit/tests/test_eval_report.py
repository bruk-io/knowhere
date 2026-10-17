"""Tests for evals/report.py's functional core: the trajectory parser, the
results document, the token CSS and the page. No eval is run and no file but
the bundled tokens and template is read."""

import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "evals"))
import report as rp  # noqa: E402


def _line(**event):
    return json.dumps(event)


_TRACE = [
    _line(type="system", subtype="hook_response", hook_name="SessionStart:startup", exit_code=0, output="ctx"),
    _line(type="system", subtype="init", model="claude-x", permissionMode="dontAsk", tools=["Read", "Write"]),
    _line(type="stream_event", event={}),
    _line(type="assistant", timestamp="2026-10-14T20:00:00Z", thinking_duration_ms=1200,
          message={"content": [{"type": "thinking", "thinking": ""}]}),
    _line(type="assistant", timestamp="2026-10-14T20:00:02Z",
          message={"content": [{"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "kit:x"}}]}),
    _line(type="user", timestamp="2026-10-14T20:00:03Z",
          message={"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "Launching skill"}]}),
    _line(type="assistant", timestamp="2026-10-14T20:00:04Z", message={"content": [{
        "type": "tool_use", "id": "t2", "name": "Write",
        "input": {"file_path": "/tmp/claude-eval-AbC123/home/cwd/.claude/rules/a.md", "content": "---\npaths: x\n---\n"}}]}),
    _line(type="user", timestamp="2026-10-14T20:00:05Z", message={"content": [
        {"type": "tool_result", "tool_use_id": "t2", "content": "Permission to use Write has been denied."}]}),
    _line(type="assistant", timestamp="2026-10-14T20:00:06Z", parent_tool_use_id="t9",
          message={"content": [{"type": "text", "text": "inside a subagent\nmore"}]}),
    _line(type="result", subtype="success", num_turns=3, stop_reason="end_turn",
          permission_denials=[{"tool_name": "Write", "tool_input": {"file_path": "x"}}]),
    "not json",
]


class Trajectory(unittest.TestCase):
    def setUp(self):
        self.steps = rp.trajectory(_TRACE)

    def test_kinds_in_order_without_the_token_stream(self):
        self.assertEqual([s["kind"] for s in self.steps], ["hook", "session", "think", "skill", "tool", "say", "end"])

    def test_a_tool_step_carries_its_result_and_a_denial_is_an_error(self):
        skill, write = self.steps[3], self.steps[4]
        self.assertEqual((skill["title"], skill["result"], skill["status"]), ("kit:x", "Launching skill", "ok"))
        self.assertEqual(write["status"], "error")
        self.assertEqual(write["title"], ".claude/rules/a.md")          # sandbox prefix removed
        self.assertIn("content:\n---\npaths: x", write["body"])          # file contents as text, not escaped JSON

    def test_time_depth_and_unrecorded_thinking(self):
        self.assertEqual(self.steps[2]["title"], "(thinking not recorded, 1.2s)")
        self.assertEqual([s["t"] for s in self.steps[2:6]], [0.0, 2.0, 4.0, 6.0])
        self.assertEqual(self.steps[5]["depth"], 1)
        self.assertEqual(self.steps[5]["title"], "inside a subagent")

    def test_the_end_step_lists_permission_denials(self):
        self.assertIn("denied: Write", self.steps[-1]["body"])

    def test_long_text_is_cut_and_marked(self):
        big = _line(type="assistant", message={"content": [{"type": "text", "text": "x" * (rp.TEXT_CAP + 10)}]})
        step = rp.trajectory([big])[0]
        self.assertEqual((len(step["body"]), step["truncated"]), (rp.TEXT_CAP, True))


def _raw():
    run = lambda score, fired, trace: {"score": score, "turns": 2, "tracePath": trace, "graders": [
        {"name": "lint-SK005-fallback", "passed": score == 1, "scored": True, "explanation": "e"},
        {"name": "skill-fired", "passed": fired, "scored": False}]}
    case = lambda name, d, w, o: {"name": name, "dir": d, "promptMarkdown": "p",
                                  "graders": [{"name": "lint-SK005-fallback", "type": "regex"},
                                              {"name": "skill-fired", "type": "tool_used"}],
                                  "arms": {"with": w, "without": o}, "aggregates": {"delta": 0.5}}
    return {"startedAt": "2026-10-14T20:00:00Z", "claudeVersion": "2.1.300", "suite": {
        "plugins": [{"name": "kit", "version": "1"}], "threshold": 1, "ablation": "with-without"},
        "aggregates": {"casesPassed": 1, "casesTotal": 2},
        "cases": [case("a", "evals/skill-a/a", [run(1, True, "/t/1")], [run(0.5, False, "/t/2")]),
                  case("judge-x-pass-1", "evals/_judges/judge-x-pass-1", [run(1, False, "/t/3")], [])]}


class BuildResults(unittest.TestCase):
    def setUp(self):
        metas = {"evals/skill-a/a": {"tags": ["skill-a", "capability"], "description": ""},
                 "evals/_judges/judge-x-pass-1": {"tags": ["judge-calibration"], "description": "d"}}
        self.res = rp.build_results(_raw(), metas, {"/t/1": [{"kind": "end"}]}, ["claude"])

    def test_cases_carry_skill_kind_arms_and_trajectory(self):
        a = self.res["cases"][0]
        self.assertEqual((a["skill"], a["kind"], a["with"]["score"], a["without"]["score"]), ("skill-a", "capability", 1, 0.5))
        self.assertEqual(a["with"]["runs"][0]["trajectory"], [{"kind": "end"}])
        self.assertEqual(a["without"]["runs"][0]["trajectory"], [])
        self.assertEqual(a["fired"], {"count": 1, "of": 1})
        self.assertEqual(a["graders"][0]["lintRule"], "SK005")

    def test_judge_calibration_cases_carry_their_label(self):
        j = self.res["cases"][1]
        self.assertEqual((j["kind"], j["expected"], j["without"]), ("judge-calibration", "pass", None))

    def test_skills_are_summarised_by_kind(self):
        a = next(s for s in self.res["skills"] if s["name"] == "skill-a")
        self.assertEqual(a["by"]["capability"], {"cases": 1, "with": 1.0, "without": 0.5})
        self.assertEqual(self.res["schema"], rp.RESULTS_SCHEMA)


class Page(unittest.TestCase):
    def test_tokens_become_css_with_both_themes_and_no_raw_references(self):
        css = rp.tokens_css(json.loads(rp.TOKENS_FILE.read_text(encoding="utf-8")))
        self.assertIn("--bh-color-bg:", css)
        self.assertIn("[data-theme='dark']", css)
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertNotIn("{color-", css)                                 # every reference resolved to var()

    def test_the_page_embeds_the_results_safely(self):
        res = {"run": {"startedAt": "2026-10-14T20:00:00Z"}, "cases": [{"prompt": "</script><b>"}]}
        page = rp.render_html(res, json.loads(rp.TOKENS_FILE.read_text(encoding="utf-8")),
                              rp.TEMPLATE_FILE.read_text(encoding="utf-8"))
        self.assertNotIn("</script><b>", page)
        self.assertNotIn("__DATA__", page)
        self.assertNotIn("/*TOKENS*/", page)
        self.assertIn("<title>Eval run 2026-10-14 20:00</title>", page)


if __name__ == "__main__":
    unittest.main()
