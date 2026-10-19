"""Tests for scripts/artefact.py, artefact-check and the write hook.

The checks are tested on small texts shaped like the templates, each broken one way.
The command and the hook are tested as programs, against a clean fixture under
`tests/fixtures/intent/sample` and against a broken copy of it in a temporary
directory. Set HOOK_PYTHON to run them under another interpreter.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import artefact as a  # noqa: E402

PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)
SAMPLE = ROOT / "tests" / "fixtures" / "intent" / "sample"

INTENT = """# Intent: a thing

Author: Someone. Status: draft.

## Problem

It is broken.

## Proposed outcome

It works.

## Affected users and systems

- Someone

## Constraints

- Keep it small.
- Don't break the API,
  which other teams call.

## Open questions

- [x] Settled? Yes.
- [ ] Later? Carried forward: it can wait for the next release.
"""

SPEC = """# Spec: a thing

Intent: [intent.md](intent.md), by Someone. Status: draft.

Applied: the house rules.

## Requirements

- **R1.** It works.
- **R2.** The API stays.

## Design

Plain.

## Constraint mapping

| Intent constraint | Met by |
|---|---|
| Keep it small | R1 |
| Don't break the API | R2 |

## Open questions

- [x] None left.

## Areas of concern

1. **Load.** Owner: Someone. Proposed: cache it,
   for a minute.
"""

PLAN = """# Plan: the first change

Spec: [spec.md](../spec.md), change 01. Delivers R1.

## Files that change

- `src/thing.py`

## Order of work

1. Fix it (R1).

## Risks

- None worth a line.

## Proof

- The tests pass.
"""


def doc(text: str, path: str = "x.md") -> a.Doc:
    return a.parse(text, path)


def checks(findings: list[a.Finding]) -> list[str]:
    return [finding.check for finding in findings]


# --- parsing ------------------------------------------------------------------------


def test_parse_splits_title_header_and_sections():
    parsed = doc(INTENT)
    assert parsed.title == "Intent: a thing"
    assert parsed.header == "Author: Someone. Status: draft."
    assert [name for name, _ in parsed.sections] == list(a.INTENT_SECTIONS)


def test_items_join_wrapped_lines():
    constraints = a.items(a.section(doc(INTENT), "Constraints") or "", a.BULLET)
    assert constraints == ("- Keep it small.", "- Don't break the API, which other teams call.")


def test_carried_forward_question_is_settled():
    questions = a.checkboxes(a.section(doc(INTENT), "Open questions") or "")
    assert [a.settled(question) for question in questions] == [True, True]


def test_the_templates_placeholder_question_is_not_settled():
    for template in ("intent.md", "spec.md"):
        body = (ROOT / "templates" / template).read_text()
        questions = a.checkboxes(a.section(a.parse(body, template), "Open questions") or "")
        assert questions and not any(a.settled(q) for q in questions), template


def test_quoting_carried_forward_mid_sentence_does_not_settle_a_question():
    quoted = a.checkboxes('- [ ] Later? Tick it, or say "Carried forward:" and why.\n')
    assert [a.settled(question) for question in quoted] == [False]


def test_carried_forward_needs_a_reason():
    bare = a.checkboxes("- [ ] Later? Carried forward:\n")
    assert [a.settled(question) for question in bare] == [False]


def test_a_fence_closes_only_on_its_own_marker():
    text = INTENT.replace(
        "It is broken.\n",
        "It is broken.\n\n~~~\n```\n## Still inside\n~~~\n\n````\n```\n## Inside too\n````\n",
    )
    assert [name for name, _ in doc(text).sections] == list(a.INTENT_SECTIONS)


def test_a_fence_line_with_an_info_string_does_not_close_the_fence():
    text = INTENT.replace(
        "It is broken.\n", "It is broken.\n\n````\n```python\n## Still inside\n````\n"
    )
    assert [name for name, _ in doc(text).sections] == list(a.INTENT_SECTIONS)


def test_numbered_constraints_count():
    numbered = INTENT.replace(
        "- Keep it small.\n- Don't break the API,\n  which other teams call.\n",
        "1. Keep it small.\n2. Don't break the API.\n",
    )
    assert a.check_spec(doc(SPEC), doc(numbered)) == []


def test_a_table_without_a_separator_keeps_its_first_row():
    assert len(a.table_rows("| head |\n| first |\n| second |\n")) == 2
    assert len(a.table_rows("| head |\n|---|\n| first |\n")) == 1


def test_spec_listing_a_constraint_twice_is_found():
    broken = SPEC.replace("| Don't break the API | R2 |", "| Keep it small | R2 |")
    assert checks(a.check_spec(doc(broken), doc(INTENT))) == ["mapping"]


def test_a_heading_inside_a_code_fence_is_not_a_section():
    text = INTENT.replace(
        "It is broken.\n", "It is broken.\n\n```markdown\n## Not a section\n# Nor a title\n```\n"
    )
    parsed = doc(text)
    assert [name for name, _ in parsed.sections] == list(a.INTENT_SECTIONS)
    assert "## Not a section" in (a.section(parsed, "Problem") or "")


def test_table_rows_skip_header_and_separator():
    rows = a.table_rows(a.section(doc(SPEC), "Constraint mapping") or "")
    assert len(rows) == 2


# --- intent -------------------------------------------------------------------------


def test_clean_intent_has_no_findings():
    assert a.check_intent(doc(INTENT)) == []


def test_intent_missing_a_section_is_found():
    broken = INTENT.replace("## Proposed outcome\n\nIt works.\n\n", "")
    assert checks(a.check_intent(doc(broken))) == ["sections"]


def test_intent_with_an_open_question_is_found():
    broken = INTENT.replace("- [x] Settled? Yes.", "- [ ] Settled? Not yet.")
    assert checks(a.check_intent(doc(broken))) == ["questions"]


def test_intent_with_no_status_is_found():
    broken = INTENT.replace(" Status: draft.", "")
    assert checks(a.check_intent(doc(broken))) == ["header"]


def test_intent_with_an_empty_or_embedded_author_is_found():
    for header in ("Author: . Status: draft.", "CoAuthor: Someone. Status: draft."):
        broken = INTENT.replace("Author: Someone. Status: draft.", header)
        assert checks(a.check_intent(doc(broken))) == ["header"], header


def test_intent_with_the_wrong_title_is_found():
    broken = INTENT.replace("# Intent: a thing", "# A thing")
    assert checks(a.check_intent(doc(broken))) == ["title"]


# --- spec ---------------------------------------------------------------------------


def test_clean_spec_has_no_findings():
    assert a.check_spec(doc(SPEC), doc(INTENT)) == []


def test_spec_with_a_gap_in_requirements_is_found():
    broken = SPEC.replace("**R2.**", "**R3.**")
    found = a.check_spec(doc(broken), doc(INTENT))
    assert checks(found) == ["requirements"]
    assert "R2" in found[0].message


def test_spec_with_a_duplicate_requirement_is_found():
    broken = SPEC.replace("**R2.**", "**R1.**")
    assert "requirements" in checks(a.check_spec(doc(broken), doc(INTENT)))


def test_spec_missing_a_mapping_row_is_found():
    broken = SPEC.replace("| Don't break the API | R2 |\n", "")
    found = a.check_spec(doc(broken), doc(INTENT))
    assert checks(found) == ["mapping"]
    assert "2 constraints" in found[0].message


def test_spec_concern_with_no_owner_is_found():
    broken = SPEC.replace("Owner: Someone. ", "")
    assert checks(a.check_spec(doc(broken), doc(INTENT))) == ["concerns"]


def test_template_placeholders_are_not_values():
    cases = (
        (a.check_intent, INTENT, "Author: Someone.", "Author: <name>."),
        (a.check_intent, INTENT, "Status: draft.", "Status: <draft>."),
        (a.check_spec, SPEC, "Intent: [intent.md](intent.md), by", "Intent: <link>, by"),
        (a.check_spec, SPEC, "Applied: the house rules.", "Applied: <rules>"),
        (a.check_spec, SPEC, "Owner: Someone.", "Owner: <who>."),
        (a.check_spec, SPEC, "**R2.** The API stays.", "**R2.** <requirement>"),
    )
    for check, text, real, placeholder in cases:
        assert real in text, real
        args = (doc(INTENT),) if check is a.check_spec else ()
        assert check(doc(text), *args) == [], real
        found = check(doc(text.replace(real, placeholder)), *args)
        assert found, placeholder
        assert "placeholder" in found[0].message, placeholder


def test_a_value_quoting_a_placeholder_mid_sentence_passes():
    quoted = SPEC.replace("**R2.** The API stays.", "**R2.** Replace <value> with the API.")
    assert a.check_spec(doc(quoted), doc(INTENT)) == []


def test_spec_with_no_applied_line_is_found():
    broken = SPEC.replace("Applied: the house rules.\n", "")
    assert checks(a.check_spec(doc(broken), doc(INTENT))) == ["header"]


# --- plan ---------------------------------------------------------------------------


def test_clean_plan_has_no_findings():
    assert a.check_plan(doc(PLAN), "01-first.md", doc(SPEC)) == []


def test_plan_citing_an_undefined_requirement_is_found():
    broken = PLAN.replace("Delivers R1.", "Delivers R1 and R9.")
    found = a.check_plan(doc(broken), "01-first.md", doc(SPEC))
    assert checks(found) == ["citations"]
    assert "R9" in found[0].message


def test_plan_citing_nothing_is_found():
    broken = PLAN.replace("Delivers R1.", "Delivers it.").replace(" (R1)", "")
    assert checks(a.check_plan(doc(broken), "01-first.md", doc(SPEC))) == ["citations"]


def test_plan_listing_no_paths_is_found():
    broken = PLAN.replace("- `src/thing.py`", "- the thing module")
    assert checks(a.check_plan(doc(broken), "01-first.md", doc(SPEC))) == ["files"]


def test_plan_with_a_bad_name_is_found():
    assert checks(a.check_plan(doc(PLAN), "first.md", doc(SPEC))) == ["name"]


def test_plan_without_a_spec_is_found():
    assert checks(a.check_plan(doc(PLAN), "01-first.md", None)) == ["spec"]


def test_listed_paths_reads_backticked_bullets():
    assert a.listed_paths(doc(PLAN)) == ("src/thing.py",)


# --- the command and the hook, against real files -----------------------------------


def run_check(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "artefact-check"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def broken_copy(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    copy = tmp_path / "intent" / "sample"
    shutil.copytree(SAMPLE, copy)
    spec = copy / "spec.md"
    spec.write_text(spec.read_text().replace("**R2.**", "**R99.**"))
    return copy


def test_command_passes_on_a_clean_fixture():
    result = run_check(str(SAMPLE))
    assert result.returncode == 0, result.stdout + result.stderr


def test_command_reports_a_broken_copy(tmp_path):
    copy = broken_copy(tmp_path)
    result = run_check(str(copy), "--json")
    assert result.returncode == 1
    # R2 is renumbered R99, so the spec has a gap and plan 01 cites an undefined R2.
    found = {finding["check"] for finding in json.loads(result.stdout)}
    assert found == {"requirements", "citations"}


def test_command_exits_2_for_a_missing_path(tmp_path):
    assert run_check(str(tmp_path / "nowhere")).returncode == 2


def run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "hooks" / "artefact_hook.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def test_hook_reports_a_write_to_a_broken_artefact(tmp_path):
    copy = broken_copy(tmp_path)
    result = run_hook(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(copy / "spec.md")},
        }
    )
    assert result.returncode == 0
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "requirements" in context


def test_hook_is_silent_outside_intent(tmp_path):
    result = run_hook(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "src" / "thing.py")},
        }
    )
    assert (result.returncode, result.stdout) == (0, "")


def test_hook_is_silent_for_a_folder_named_intent_above_the_repository(tmp_path):
    repo = tmp_path / "intent" / "project"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    spec = repo / "spec.md"
    spec.write_text("not an artefact")
    result = run_hook(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(spec)},
        }
    )
    assert (result.returncode, result.stdout) == (0, "")


def test_hook_is_silent_for_a_clean_artefact():
    result = run_hook(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": str(SAMPLE / "intent.md")},
        }
    )
    assert (result.returncode, result.stdout) == (0, "")
