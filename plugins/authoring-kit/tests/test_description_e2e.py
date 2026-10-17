"""Tests for evals/description_e2e.py's functional core. No eval is run."""

import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))
import description_e2e as e2e  # noqa: E402


class DescriptionOf(unittest.TestCase):
    def test_plain_quoted_and_folded(self):
        self.assertEqual(e2e.description_of("---\nname: x\ndescription: Plain words.\n---\nbody"), "Plain words.")
        self.assertEqual(e2e.description_of("---\ndescription: 'It''s quoted'\n---\n"), "It's quoted")
        self.assertEqual(e2e.description_of("---\ndescription: >-\n  Folded\n  over lines.\nname: x\n---\n"),
                         "Folded over lines.")

    def test_missing(self):
        self.assertEqual(e2e.description_of("no frontmatter"), "")
        self.assertEqual(e2e.description_of("---\nname: x\n---\n"), "")


class ProbeFiles(unittest.TestCase):
    def test_holds_only_the_written_skill_and_one_case_per_prompt(self):
        files = e2e.probe_files("notes", {"should_fire": ["a", "b"], "near_miss": ["c"]},
                                {"SKILL.md": "---\ndescription: d\n---\n", "references/x.md": "x"})
        self.assertEqual(json.loads(files[".claude-plugin/plugin.json"])["name"], "probe")
        self.assertIn("skills/notes/references/x.md", files)
        self.assertEqual(sorted(k for k in files if k.endswith("prompt.md")),
                         ["evals/fire-1/prompt.md", "evals/fire-2/prompt.md", "evals/miss-1/prompt.md"])
        self.assertIn("min: 1", files["evals/fire-1/graders/fired.md"])
        self.assertIn("max: 0", files["evals/miss-1/graders/fired.md"])
        self.assertIn('"probe:notes"', files["evals/miss-1/graders/fired.md"])


def _call(skill):
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]}})


class Scoring(unittest.TestCase):
    def test_only_the_probe_skill_counts(self):
        self.assertTrue(e2e.skill_loaded([_call("probe:notes")], "notes"))
        self.assertFalse(e2e.skill_loaded([_call("other:notes"), "not json"], "notes"))

    def test_score_and_summary(self):
        raw = {"cases": [{"name": "fire-1", "arms": {"with": [{"tracePath": "/t/1"}, {"tracePath": "/t/2"}]}},
                         {"name": "miss-1", "arms": {"with": [{"tracePath": "/t/3"}]}}]}
        tally = e2e.score_probe(raw, {"/t/1": [_call("probe:notes")], "/t/3": []}, "notes")
        self.assertEqual(tally, {"should_fire": [1, 2], "near_miss": [0, 1]})
        records = [{"case": "c", "arm": "with", "description": "d", "probe": tally},
                   {"case": "c", "arm": "without", "description": "", "probe": {"should_fire": [0, 2], "near_miss": [0, 0]}}]
        s = e2e.summarise(records)
        self.assertEqual(s["with"]["should_fire"], [1, 2])
        self.assertEqual(s["without"]["written"], [0, 1])
        self.assertIn("(no skill written)", e2e.format_summary(records))


if __name__ == "__main__":
    unittest.main()
