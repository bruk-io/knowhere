"""Tests for scripts/board.py, board-check and close-task.

The first half tests the checks with plain values shaped like the files Backlog.md 1.53
writes. The second half builds a real board with the backlog CLI in a throwaway git
repository and runs the two commands against it; it is skipped when `backlog` is not on
PATH. Set HOOK_PYTHON to run the commands under another interpreter.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import board as b  # noqa: E402
from board import Board, Doc, Item, Task  # noqa: E402

PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)

INTENT = """---
id: TASK-1
title: 'Claims: status self-service'
status: To Do
assignee:
  - '@j.ortiz'
created_date: '2026-10-09 20:55'
labels:
  - size-5
dependencies: []
documentation:
  - backlog/docs/specs/doc-1 - Spec-Claims-status-self-service.md
type: intent
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem
Customers phone the contact centre.

## Open questions
- [x] Is SSO needed?
- [ ] Do third-party loss adjusters need access too?
- [ ] Mobile too? Carried forward: web first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Customers see claim status
- [x] #2 No new PII in the portal session
<!-- AC:END -->
"""

LEAF = """---
id: TASK-1.2
title: Status endpoint behind existing auth
status: In Progress
assignee: []
labels:
  - size-3
dependencies:
  - TASK-1.1
modified_files:
  - claims-api/routes/status.py
parent_task_id: TASK-1
type: task
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 test_status.py covers the four claim states (R1)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
### Order of work
1. Add the status endpoint behind existing auth.

### Risks
The claims-core API rate-limits at 50 rps.

### Proof
test_status.py covers the four claim states.
<!-- SECTION:PLAN:END -->
"""

SPEC = """---
id: doc-1
title: 'Spec: Claims status self-service'
type: specification
---
Intent: TASK-1

## Requirements

- R1. A signed-in customer sees each open claim's status.
- R2. The status shown is no more than 15 minutes old.

## Policies applied

- Security: existing authentication only.

## Areas of concern

- None yet.

## Open questions

- [ ] Do third-party loss adjusters need access too? Carried forward: not needed for R1-R2.

## Design questions

- How the portal stays under the rate limit: TASK-1.1.

## Out of scope

- Notifications.
"""

SPEC_PATH = "backlog/docs/specs/doc-1 - Spec-Claims-status-self-service.md"


def board(*tasks: Task, docs: tuple[Doc, ...] = ()) -> Board:
    return Board(tasks, docs, b.TYPES, "task")


def intent(**changes: object) -> Task:
    return b.parse_task(INTENT, "backlog/tasks/task-1 - Claims.md")._replace(**changes)


def leaf(**changes: object) -> Task:
    return b.parse_task(LEAF, "backlog/tasks/task-1.2 - Status.md")._replace(**changes)


def spec() -> Doc:
    return b.parse_doc(SPEC, SPEC_PATH)


def messages(findings: list[b.Finding]) -> list[str]:
    return [f.message for f in findings]


# --- reading -------------------------------------------------------------------------


def test_parse_task_reads_what_the_cli_writes() -> None:
    task = intent()
    assert (task.id, task.title, task.status, task.type) == (
        "TASK-1",
        "Claims: status self-service",
        "To Do",
        "intent",
    )
    assert task.labels == ("size-5",)
    assert task.documentation == (SPEC_PATH,)
    assert task.criteria == (
        Item(False, "Customers see claim status"),
        Item(True, "No new PII in the portal session"),
    )
    assert "## Open questions" in task.description and "<!--" not in task.description


def test_parse_yaml_reads_flow_lists_and_quotes() -> None:
    data = b.parse_yaml('types: ["intent", "a, b", \'it\'\'s\']\ntask_prefix: "bh"\nlabels: []\n')
    assert data == {"types": ["intent", "a, b", "it's"], "task_prefix": "bh", "labels": []}


def test_open_questions_are_settled_when_ticked_or_carried() -> None:
    questions = b.open_questions(intent().description)
    assert [b.settled(q) for q in questions] == [True, False, True]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("5", ("TASK-5", "DRAFT-5")), ("1.2", ("TASK-1.2", "DRAFT-1.2")), ("task-3", ("TASK-3",))],
)
def test_candidate_ids(raw: str, expected: tuple[str, ...]) -> None:
    assert b.candidate_ids(raw, "task") == expected


def test_a_bare_number_finds_a_task_or_a_draft_but_not_both() -> None:
    draft = intent(id="DRAFT-2", status="Draft")
    assert b.find_task(board(intent(), draft), "2") == draft
    assert b.find_task(board(intent(), draft), "1") == intent()
    with pytest.raises(LookupError, match="both TASK-1 and DRAFT-1"):
        b.find_task(board(intent(), intent(id="DRAFT-1")), "1")


def test_parse_yaml_reads_folded_blocks_comments_and_a_bom() -> None:
    text = (
        "﻿---\nid: TASK-1\ntitle: >-\n  A very long title: with a colon, about\n"
        "  claims status\nstatus: Done   # closed by hand\ndocumentation:\n  - >-\n"
        "    backlog/docs/specs/doc-1 -\n    Spec-Claims.md\n  - short.md\ntype: task\n---\n"
    )
    task = b.parse_task(text, "backlog/tasks/task-1.md")
    assert task.title == "A very long title: with a colon, about claims status"
    assert task.status == "Done" and task.type == "task"
    assert task.documentation == ("backlog/docs/specs/doc-1 - Spec-Claims.md", "short.md")


def test_a_description_written_by_hand_still_has_its_questions() -> None:
    text = (
        "---\nid: DRAFT-1\nstatus: Draft\n---\n\n## Description\n\n## Problem\nX.\n\n"
        "## Open questions\n- [ ] Adjusters?\n\n## Acceptance Criteria\n- [ ] #1 Y\n"
    )
    task = b.parse_task(text, "backlog/drafts/draft-1.md")
    assert b.open_questions(task.description) == (Item(False, "Adjusters?"),)
    assert task.criteria == (Item(False, "Y"),)


@pytest.mark.parametrize("line", ["- R1. Text", "- **R1.** Text", "1. R1. Text", "R1: Text"])
def test_requirement_numbers_in_common_shapes(line: str) -> None:
    doc = spec()._replace(body="## Requirements\n\n%s\n" % line)
    assert b.requirements(doc) == ("1",)


def test_a_spec_is_found_by_number() -> None:
    assert b.find_doc(board(docs=(spec(),)), "1") == spec()


def test_a_task_is_not_its_own_child() -> None:
    selfish = intent(parent="TASK-1")
    assert b.children(board(selfish), selfish) == ()


# --- checks --------------------------------------------------------------------------


def test_ready_names_each_unsettled_question() -> None:
    found = b.check_ready(board(intent()), intent())
    assert messages(found) == [
        'open question is neither answered nor carried forward: "Do third-party loss adjusters '
        'need access too?". Tick it, or add "Carried forward:" and why it can wait'
    ]


def test_ready_wants_criteria_a_type_and_one_size() -> None:
    bare = intent(criteria=(), type="feature", labels=("size-4", "size-2"), description="")
    found = messages(b.check_ready(board(bare), bare))
    assert found[0].startswith("has no acceptance criteria")
    assert found[1].startswith("has type 'feature'")
    assert "size-4 is not a size: sizes are 1, 2, 3, 5 and 8" in found
    assert "has 2 size labels (size-4, size-2): keep one" in found
    unsized = intent(labels=("claims",))
    assert any(
        m.startswith("has no size label") for m in messages(b.check_ready(board(unsized), unsized))
    )


def test_sizes_across_the_board() -> None:
    draft = intent(id="DRAFT-2", status="Draft", labels=())
    done = intent(id="TASK-9", status="Done", labels=())
    started = intent(id="TASK-8", status="In Progress", labels=("size-8",))
    found = b.check_sizes(board(draft, done, started))
    assert [(f.id, f.message) for f in found] == [
        ("TASK-8", "is in progress at size 8 with no children: split it before it starts")
    ]


def test_plan_is_clean_when_shaped_and_cited() -> None:
    assert b.check_plan(board(intent(), leaf()), leaf()) == []


def test_plan_wants_its_sections_files_and_a_citation() -> None:
    thin = leaf(plan="### Order of work\n1. Do it.\n\n### Risks\n", modified_files=(), criteria=())
    assert messages(b.check_plan(board(intent(), thin), thin)) == [
        "plan's '### Risks' section is empty",
        "plan has no '### Proof' section",
        "lists no files: add each file that changes with --modified-file",
        "cites no requirement from TASK-1's spec: name the R-numbers it delivers",
    ]
    unplanned = leaf(plan="")
    assert messages(b.check_plan(board(unplanned), unplanned))[0].startswith(
        "has no implementation plan"
    )


def test_spec_is_clean_when_linked_and_complete() -> None:
    assert b.check_spec(board(intent(), leaf()), spec(), coverage=False) == []


def test_spec_coverage_names_uncited_requirements() -> None:
    found = b.check_spec(board(intent(), leaf()), spec(), coverage=True)
    assert messages(found) == ["R2 is not cited by any task under TASK-1"]


def test_spec_wants_its_link_sections_and_numbers() -> None:
    unlinked = intent(documentation=())
    broken = spec()._replace(body="Intent: TASK-1\n\n## Requirements\n\n- Something.\n")
    found = messages(b.check_spec(board(unlinked), broken, coverage=False))
    assert found[0] == 'TASK-1 does not link it: backlog task edit TASK-1 --doc "%s"' % SPEC_PATH
    assert "has no '## Out of scope' section" in found
    assert found[-1] == "lists no numbered requirements (R1, R2, ...)"


def test_close_wants_every_criterion_and_child() -> None:
    found = b.check_close(board(intent(), leaf()), intent())
    assert messages(found) == [
        'criterion #1 is not met: "Customers see claim status"',
        "child TASK-1.2 is In Progress: a parent stays open while its children are. Close it, "
        "or move it to a new intent that says why it was deferred",
    ]


def test_close_ignores_draft_children_and_refuses_a_draft() -> None:
    ticked = intent(criteria=(Item(True, "Customers see claim status"),))
    draft_child = leaf(id="DRAFT-3", status="Draft")
    assert b.check_close(board(ticked, draft_child), ticked) == []
    assert messages(b.check_close(board(ticked), ticked._replace(status="Draft"))) == [
        "is a draft: it was never accepted"
    ]


def test_moved_ignores_ticks_and_order_but_not_wording() -> None:
    then = (
        Item(False, "No new PII in the portal session"),
        Item(False, "Customers see claim status"),
    )
    assert b.check_moved(intent(), then, "abc1234def") == []
    changed = (Item(False, "Customers see claim status"), Item(False, "No PII"))
    found = b.check_moved(intent(), changed, "abc1234def")
    assert len(found) == 1 and found[0].message.startswith(
        "acceptance criteria changed since it was accepted in abc1234"
    )
    assert "removed 'No PII'" in found[0].message
    assert "added 'No new PII in the portal session'" in found[0].message
    assert b.check_moved(intent(labels=("size-5", "finish-moved")), changed, "abc1234") == []


def test_ticks_since_the_last_commit_are_the_review() -> None:
    committed = intent()
    ticked = intent(criteria=tuple(c._replace(ticked=True) for c in committed.criteria))
    assert b.check_uncommitted(ticked, committed) == []


def test_rewording_or_labelling_since_the_last_commit_is_refused() -> None:
    committed = intent()
    reworded = intent(
        criteria=(Item(True, "Customers see something"), committed.criteria[1]),
        labels=("size-5", "finish-moved"),
    )
    found = messages(b.check_uncommitted(reworded, committed))
    assert found[0].startswith(
        "the acceptance criteria have uncommitted changes (removed 'Customers see claim status'; "
        "added 'Customers see something')"
    )
    assert found[1].startswith("the finish-moved label is not committed")


def test_parallel_wants_files_and_no_overlap() -> None:
    a = leaf(id="TASK-1.2", modified_files=("api/status.py", "./api/tests.py"))
    other = leaf(id="TASK-1.3", modified_files=("api/tests.py",), dependencies=())
    bare = leaf(id="TASK-1.4", modified_files=())
    found = b.check_parallel(board(a, other, bare), (a, other, bare))
    assert [(f.id, f.message) for f in found] == [
        ("TASK-1.4", "lists no files, so overlap can't be checked: plan it first"),
        ("TASK-1.2", "shares api/tests.py with TASK-1.3: run them one after the other"),
    ]


def test_parallel_sees_a_task_waiting_on_another_through_a_third() -> None:
    first = leaf(id="TASK-2", dependencies=(), modified_files=("a.py",))
    middle = leaf(id="TASK-3", dependencies=("TASK-2",), modified_files=("b.py",))
    last = leaf(id="TASK-4", dependencies=("TASK-3",), modified_files=("c.py",))
    found = b.check_parallel(board(first, middle, last), (first, last))
    assert [(f.id, f.message) for f in found] == [("TASK-4", "waits on TASK-2: run them in order")]


@pytest.mark.parametrize(
    ("changes", "model", "effort"),
    [
        ({"labels": ("size-1",)}, "haiku", None),
        ({"labels": ("size-3", "api")}, "sonnet", "medium"),
        ({"type": "spike", "labels": ("size-2",)}, "opus", "high"),
    ],
)
def test_route_from_type_and_size(changes: dict, model: str, effort: str | None) -> None:
    task = leaf(**changes)
    chosen, found = b.route(board(task), task)
    assert found == [] and chosen is not None and (chosen.model, chosen.effort) == (model, effort)


def test_route_sends_split_work_to_the_orchestrator_and_refuses_unsized_or_8() -> None:
    parent = intent(type="task", labels=("size-8",))
    child = leaf()
    assert b.route(board(parent, child), parent)[0] == b.ORCHESTRATE
    assert b.route(board(parent), parent)[1][0].message == "is at size 8: split it before it starts"
    unsized = leaf(labels=())
    assert b.route(board(unsized), unsized)[1][0].message.startswith("needs exactly one size label")


def test_a_later_repro_replaces_an_earlier_one() -> None:
    notes = (
        "Repro at abc1234def00, test files: tests/test_a.py; command: `pytest tests/test_a.py` "
        "exited 1\n\nRepro at 999aaa999aaa, test files: tests/test_a.py, tests/test_b.py; "
        "command: `pytest tests` exited 1\n"
    )
    assert b.repro_records(notes) == [
        ("abc1234def00", ("tests/test_a.py",)),
        ("999aaa999aaa", ("tests/test_a.py", "tests/test_b.py")),
    ]
    found = b.check_repro(leaf(), {"tests/test_a.py": "999aaa999aaa"})
    assert found[0].message.startswith("the repro test tests/test_a.py changed since 999aaa9")


def test_a_bug_closes_with_a_repro_or_a_reason_for_none() -> None:
    bug = leaf(type="bug", criteria=(Item(True, "Fixed"),))
    assert messages(b.check_close(board(bug), bug))[0].startswith("a bug closes with its repro")
    with_repro = bug._replace(notes="Repro at abc1234def00, test files: t.py; command: `x`")
    assert b.check_close(board(with_repro), with_repro) == []
    excused = bug._replace(notes="No repro: a race only seen in production.")
    assert b.check_close(board(excused), excused) == []
    mentioned = bug._replace(notes="Check `pytest` exited 1\n\nlog: no repro: found")
    assert messages(b.check_close(board(mentioned), mentioned))[0].startswith("a bug closes")


def test_config_names_the_missing_types() -> None:
    found = b.check_config(Board((), (), ("bug", "task", "spike"), "task"))
    assert found[0].message.startswith("backlog/config.yml types lack intent, design")
    assert 'types: ["bug", "task", "spike", "intent", "design"]' in found[0].message


# --- the layout: intents, specs and plans as files paired by name -----------------------

NAMED_INTENT = """---
title: Claims status self-service
status: To Do
assignee:
  - '@j.ortiz'
labels:
  - size-5
---

## Problem
Customers phone the contact centre.

## Done when
- [ ] Customers see claim status
- [x] No new PII in the portal session

## Open questions
- [x] Is SSO needed?
- [ ] Do third-party loss adjusters need access too?
- [ ] Mobile too? Carried forward: web first.

## Notes
Spec approved by @p.owner
"""

NAMED_SPEC = """---
title: 'Spec: Claims status self-service'
---

## Requirements

- R1. A signed-in customer sees each open claim's status.
- R2. The customer lists all open claims.

## Policies applied

- Security: existing authentication only.

## Areas of concern

- None yet.

## Open questions

- [ ] Do third-party loss adjusters need access too? Carried forward: not needed for R1-R2.

## Design questions

- None.

## Out of scope

- Notifications.
"""

NAMED_PLAN = """---
title: 'Plan: Claims status self-service'
---

## Slices

1. **One claim.** A customer opens a claim.
   Tester sees: its status, next step and expected date.
   Depends on: none.
2. **All claims.** A customer lists every open claim.
   Tester sees: three open claims, newest first.
   Depends on: slice 1.
"""

NAME = "claims-status"


def named_intent(**changes: object) -> Task:
    return b.parse_intent(NAMED_INTENT, "backlog/intents/%s.md" % NAME)._replace(**changes)


def named_spec(text: str = NAMED_SPEC, name: str = NAME) -> Doc:
    return b.parse_named(text, "backlog/specs/%s.md" % name)


def named_plan(text: str = NAMED_PLAN, name: str = NAME) -> Doc:
    return b.parse_named(text, "backlog/plans/%s.md" % name)


def member(id: str, *labels: str, **changes: object) -> Task:
    return leaf(id=id, parent="", labels=("size-2", NAME, *labels), **changes)


def work(*tasks: Task, spec_text: str = NAMED_SPEC, plan_text: str = NAMED_PLAN) -> Board:
    return Board(
        (named_intent(), *tasks),
        (),
        b.TYPES,
        "task",
        (named_spec(spec_text),),
        (named_plan(plan_text),),
    )


def test_an_intent_file_reads_as_a_task_named_by_its_file() -> None:
    task = named_intent()
    assert (task.id, task.title, task.status, task.type) == (
        NAME,
        "Claims status self-service",
        "To Do",
        "intent",
    )
    assert task.labels == ("size-5",) and task.parent == ""
    assert task.criteria == (
        Item(False, "Customers see claim status"),
        Item(True, "No new PII in the portal session"),
    )
    assert task.notes.strip() == "Spec approved by @p.owner"


def test_open_questions_are_read_from_the_intent_file() -> None:
    questions = b.open_questions(named_intent().description)
    assert [b.settled(q) for q in questions] == [True, False, True]
    found = b.check_ready(work(), named_intent())
    assert messages(found) == [
        'open question is neither answered nor carried forward: "Do third-party loss adjusters '
        'need access too?". Tick it, or add "Carried forward:" and why it can wait'
    ]


def test_an_intent_without_a_done_when_list_says_where_to_add_it() -> None:
    bare = named_intent(criteria=())
    assert messages(b.check_ready(work(), bare))[0] == (
        "has no acceptance criteria, so nobody can tell when it is done: add a '## Done when' "
        "checklist to backlog/intents/claims-status.md"
    )


def test_acceptance_criteria_is_an_accepted_heading_for_done_when() -> None:
    text = NAMED_INTENT.replace("## Done when", "## Acceptance Criteria")
    assert len(b.parse_intent(text, "backlog/intents/x.md").criteria) == 2


def test_a_task_belongs_to_the_work_by_label_or_through_its_parent() -> None:
    a = member("TASK-1")
    sub = leaf(id="TASK-1.1", parent="TASK-1", labels=("size-1",))
    stray = leaf(id="TASK-9", parent="", labels=("size-1", "other"))
    draft = member("DRAFT-2", status="Draft")
    board = work(a, sub, stray, draft)
    assert [t.id for t in b.children(board, named_intent())] == ["TASK-1", "TASK-1.1"]
    assert b.intent_of(board, sub) == named_intent()
    assert b.intent_of(board, stray) is None
    assert b.ancestors(board, sub) == (a, named_intent())


def test_a_spec_is_found_by_its_work_name() -> None:
    assert b.find_doc(work(), "claims-status") == named_spec()
    assert b.find_doc(work(), "nope") is None


def test_a_paired_spec_is_clean_without_an_intent_line_or_a_link() -> None:
    assert b.check_spec(work(), named_spec(), coverage=False) == []


def test_a_spec_without_an_intent_is_an_orphan() -> None:
    orphan = named_spec(name="lonely")
    found = messages(b.check_spec(work(), orphan, coverage=False))
    assert found[0].startswith("has no backlog/intents/lonely.md: a spec is paired")


def test_coverage_counts_citations_under_the_work() -> None:
    delivers = member("TASK-1", "slice-1", type="task")
    delivers = delivers._replace(criteria=(Item(False, "Shows status (R1)"),))
    board = work(delivers)
    found = b.check_spec(board, named_spec(), coverage=True)
    assert messages(found) == ["R2 is not cited by any task under claims-status"]
    both = delivers._replace(criteria=(Item(False, "Shows status (R1, R2)"),))
    assert b.check_spec(work(both), named_spec(), coverage=True) == []


def test_a_plan_leaf_cites_a_requirement_when_its_work_has_a_spec() -> None:
    uncited = member("TASK-1", "slice-1", criteria=(Item(False, "Works"),))
    found = messages(b.check_plan(work(uncited), uncited))
    assert found == [
        "cites no requirement from claims-status's spec: name the R-numbers it delivers"
    ]


def test_the_plan_must_exist_before_the_work_is_split() -> None:
    board = Board((named_intent(), member("TASK-1", "slice-1")), (), b.TYPES, "task")
    assert messages(b.check_slices(board, named_intent())) == [
        "has 1 tasks but no backlog/plans/claims-status.md: the plan puts the slices in order "
        "and the tasks are derived from it, so write it before splitting"
    ]
    assert b.check_slices(Board((named_intent(),), (), b.TYPES, "task"), named_intent()) == []


def test_a_plan_with_ordered_slices_and_a_task_for_each_is_clean() -> None:
    board = work(member("TASK-1", "slice-1"), member("TASK-2", "slice-2"))
    assert b.check_slices(board, named_intent()) == []
    assert b.check_plan(board, named_intent()) == []


def test_a_draft_task_covers_its_slice_but_is_not_yet_work() -> None:
    board = work(member("TASK-1", "slice-1"), member("DRAFT-2", "slice-2", status="Draft"))
    assert b.check_slices(board, named_intent()) == []


def test_a_slice_with_no_task_is_named() -> None:
    found = b.check_slices(work(member("TASK-1", "slice-1")), named_intent())
    assert messages(found) == [
        "slice 2 has no task: derive one from it, or take the slice out of "
        "backlog/plans/claims-status.md"
    ]


def test_a_task_names_a_slice_the_plan_has() -> None:
    board = work(
        member("TASK-1"), member("TASK-2", "slice-1", "slice-7"), member("TASK-3", "slice-2")
    )
    found = [(f.id, f.message) for f in b.check_slices(board, named_intent())]
    assert found == [
        (
            "TASK-1",
            "names no slice of claims-status: add a slice-n label for the slice in "
            "backlog/plans/claims-status.md it comes from, so the plan and the tasks stay "
            "traceable",
        ),
        ("TASK-2", "names slice-7, which backlog/plans/claims-status.md does not have"),
    ]


def test_slices_are_numbered_in_order_and_name_what_a_tester_sees() -> None:
    plan = (
        "## Slices\n\n2. **Later.** Something.\n   Tester sees: a thing.\n"
        "1. **First.** Something.\n   Depends on: slice 2.\n"
    )
    found = messages(
        b.check_slices(work(member("TASK-1", "slice-1"), plan_text=plan), named_intent())
    )
    assert found[0].startswith("slices are numbered 2, 1: number them 1, 2, 3")
    assert found[1].startswith("slice 1 names nothing a tester can see: add 'Tester sees:")
    assert found[2].startswith("slice 1 depends on slice 2: a slice depends only on an earlier")


def test_a_plan_with_no_slices_says_why_they_are_needed() -> None:
    found = b.check_slices(work(member("TASK-1"), plan_text="## Notes\n\nLater.\n"), named_intent())
    assert messages(found)[0].startswith(
        "backlog/plans/claims-status.md has no numbered slices under '## Slices'"
    )


def test_the_whole_board_checks_pairing_and_names() -> None:
    odd = named_intent(id="Bad Name", status="Started")
    lonely_plan = named_plan(name="lonely")
    board = Board((odd, named_intent()), (), b.TYPES, "task", (), (lonely_plan,))
    found = [(f.id, f.check, f.message.split(":")[0]) for f in b.check_pairing(board)]
    assert found == [
        ("Bad Name", "layout", "is not a usable name"),
        ("Bad Name", "layout", "has status 'Started'"),
        ("lonely", "plan", "has no backlog/intents/lonely.md"),
    ]


@pytest.mark.parametrize("name", ["task-5", "size-3", "slice-1", "draft-2", "9lives", "Upper"])
def test_names_that_clash_with_ids_and_labels_are_refused(name: str) -> None:
    assert b.NAME.match(name) is None
    assert b.NAME.match("nux-ep2") is not None


def test_check_board_runs_every_layout_check() -> None:
    found = [(f.id, f.check) for f in b.check_board(work(member("TASK-1", "slice-1")), {})]
    assert found == [(NAME, "plan"), (NAME, "spec")]


def test_an_intent_routes_to_the_orchestrator_and_closes_against_its_work() -> None:
    board = work(member("TASK-1", "slice-1"))
    assert b.route(board, named_intent())[0] == b.ORCHESTRATE
    ticked = named_intent(criteria=(Item(True, "Done"),))
    assert messages(b.check_close(board, ticked)) == [
        "child TASK-1 is In Progress: a parent stays open while its children are. Close it, "
        "or move it to a new intent that says why it was deferred"
    ]


def test_closing_an_intent_sets_its_status_and_appends_the_notes() -> None:
    closed = b.closed_intent_text(NAMED_INTENT, "Verdict: closes.")
    again = b.parse_intent(closed, "backlog/intents/claims-status.md")
    assert again.status == "Done"
    assert again.notes.strip() == "Spec approved by @p.owner\n\nVerdict: closes."
    assert again.criteria == named_intent().criteria
    bare = b.closed_intent_text("---\nstatus: To Do\n---\n\n## Problem\nX.\n", "Done.")
    assert "## Notes\n\nDone.\n" in bare and "status: Done" in bare


# --- the layout against files on disk -------------------------------------------------


def lay_out(root: Path, intent_text: str = NAMED_INTENT) -> None:
    for folder in ("tasks", "intents", "specs", "plans"):
        (root / "backlog" / folder).mkdir(parents=True)
    (root / "backlog" / "config.yml").write_text(
        'task_prefix: "task"\ntypes: ["intent", "design", "spike", "task", "bug"]\n'
    )
    (root / "backlog" / "intents" / ("%s.md" % NAME)).write_text(intent_text)
    (root / "backlog" / "specs" / ("%s.md" % NAME)).write_text(NAMED_SPEC)
    (root / "backlog" / "plans" / ("%s.md" % NAME)).write_text(NAMED_PLAN)
    for number, slice_label in ((1, "slice-1"), (2, "slice-2")):
        (root / "backlog" / "tasks" / ("task-%d - Part.md" % number)).write_text(
            "---\nid: TASK-%d\ntitle: Part %d\nstatus: To Do\nlabels:\n  - size-2\n  - %s\n"
            "  - %s\ntype: task\n---\n\n## Acceptance Criteria\n<!-- AC:BEGIN -->\n"
            "- [ ] #1 Delivers (R%d)\n<!-- AC:END -->\n"
            % (number, number, NAME, slice_label, number)
        )


def test_load_board_reads_the_new_folders(tmp_path: Path) -> None:
    lay_out(tmp_path)
    loaded = b.load_board(tmp_path)
    assert [t.id for t in loaded.tasks] == ["TASK-1", "TASK-2", NAME]
    assert [d.name for d in loaded.specs] == [NAME] and [d.name for d in loaded.plans] == [NAME]
    assert b.check_board(loaded, {}) == []


def test_board_check_on_the_new_layout_without_the_cli(tmp_path: Path) -> None:
    lay_out(tmp_path)
    result = command(tmp_path, "board-check")
    assert result.returncode == 0 and result.stdout.strip() == (
        "ok: 2 tasks, 1 intents, 1 specs, 1 plans, 0 docs (finish lines not checked: no git history)"
    )
    spec = command(tmp_path, "board-check", "spec", NAME, "--coverage")
    assert spec.returncode == 0, spec.stdout
    assert command(tmp_path, "board-check", "plan", NAME).returncode == 0
    ready = command(tmp_path, "board-check", "ready", NAME)
    assert ready.returncode == 1 and ready.stdout.startswith(
        "claims-status ready: open question is neither answered"
    )
    missing = command(tmp_path, "board-check", "spec", "nope")
    assert missing.returncode == 2 and "no spec 'nope'" in missing.stderr


def test_board_check_names_what_a_deleted_intent_leaves_behind(tmp_path: Path) -> None:
    lay_out(tmp_path)
    (tmp_path / "backlog" / "intents" / ("%s.md" % NAME)).unlink()
    result = command(tmp_path, "board-check")
    assert result.returncode == 1
    assert "claims-status plan: has no backlog/intents/claims-status.md" in result.stdout
    assert "claims-status spec: has no backlog/intents/claims-status.md" in result.stdout


def test_close_task_closes_an_intent_file_and_commits_only_it(tmp_path: Path) -> None:
    lay_out(tmp_path, NAMED_INTENT.replace("- [ ] Customers", "- [x] Customers"))
    for task in sorted((tmp_path / "backlog" / "tasks").glob("*.md")):
        task.write_text(task.read_text().replace("status: To Do", "status: Done"))
    sh(tmp_path, "git", "init", "-q", "-b", "main")
    sh(tmp_path, "git", "config", "user.email", "test@example.com")
    sh(tmp_path, "git", "config", "user.name", "Test")
    sh(tmp_path, "git", "add", "-A")
    sh(tmp_path, "git", "commit", "-qm", "accept")
    result = command(tmp_path, "close-task", NAME, "--notes", "Verdict: closes.")
    assert result.returncode == 0, result.stdout + result.stderr
    assert sh(tmp_path, "git", "log", "-1", "--format=%s") == (
        "Close claims-status: Claims status self-service\n"
    )
    text = (tmp_path / "backlog" / "intents" / ("%s.md" % NAME)).read_text()
    assert "status: Done" in text and "Verdict: closes." in text


def test_a_reworded_intent_criterion_moves_the_finish_line(tmp_path: Path) -> None:
    lay_out(tmp_path)
    sh(tmp_path, "git", "init", "-q", "-b", "main")
    sh(tmp_path, "git", "config", "user.email", "test@example.com")
    sh(tmp_path, "git", "config", "user.name", "Test")
    path = tmp_path / "backlog" / "intents" / ("%s.md" % NAME)
    path.write_text(NAMED_INTENT.replace("status: To Do", "status: Draft"))
    sh(tmp_path, "git", "add", "-A")
    sh(tmp_path, "git", "commit", "-qm", "capture")
    path.write_text(NAMED_INTENT)
    sh(tmp_path, "git", "commit", "-qam", "accept")
    path.write_text(NAMED_INTENT.replace("Customers see claim status", "Customers see something"))
    result = command(tmp_path, "board-check", "moved")
    assert result.returncode == 1
    assert "claims-status moved: acceptance criteria changed since it was accepted" in result.stdout
    assert "removed 'Customers see claim status'" in result.stdout


# --- the commands against a real board ------------------------------------------------

needs_backlog = pytest.mark.skipif(
    shutil.which("backlog") is None, reason="backlog CLI not installed"
)


def sh(cwd: Path, *args: str) -> str:
    return subprocess.run(args, cwd=str(cwd), check=True, capture_output=True, text=True).stdout


def command(cwd: Path, name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / name), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A board with an accepted intent and one leaf under it, all committed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    sh(repo, "git", "init", "-q", "-b", "main")
    sh(repo, "git", "config", "user.email", "test@example.com")
    sh(repo, "git", "config", "user.name", "Test")
    sh(repo, "backlog", "init", "Test", "--defaults")
    config = repo / "backlog" / "config.yml"
    config.write_text(
        config.read_text().replace(
            "labels: []", 'labels: []\ntypes: ["intent", "design", "spike", "task", "bug"]'
        )
    )
    sh(repo, "backlog", "config", "set", "remoteOperations", "false")
    sh(
        repo,
        "backlog",
        "task",
        "create",
        "--draft",
        "Claims status",
        "--type",
        "intent",
        "-l",
        "size-5",
        "--ac",
        "Customers see status",
        "-d",
        "## Problem\nThey phone.\n\n## Open questions\n- [ ] Adjusters?",
    )
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "capture")
    sh(repo, "backlog", "draft", "promote", "DRAFT-1")
    sh(
        repo,
        "backlog",
        "task",
        "create",
        "Endpoint",
        "-p",
        "TASK-1",
        "--type",
        "task",
        "-l",
        "size-2",
        "--ac",
        "Tests pass",
    )
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "accept and split")
    return repo


@needs_backlog
def test_board_check_reports_and_exits_1(repo: Path) -> None:
    result = command(repo, "board-check", "ready", "1")
    assert result.returncode == 1
    assert result.stdout.startswith(
        'TASK-1 ready: open question is neither answered nor carried forward: "Adjusters?"'
    )


@needs_backlog
def test_board_check_json_and_clean_exit(repo: Path) -> None:
    result = command(repo, "board-check", "--json", "size")
    assert result.returncode == 0 and json.loads(result.stdout) == []
    assert command(repo / "backlog", "board-check", "size").stdout.strip() == "ok: sizes"


@needs_backlog
def test_board_check_finds_a_moved_finish_line(repo: Path) -> None:
    sh(repo, "backlog", "task", "edit", "TASK-1", "--ac", "Within 15 minutes")
    result = command(repo, "board-check", "moved")
    assert result.returncode == 1
    assert "TASK-1 moved: acceptance criteria changed since it was accepted" in result.stdout
    sh(repo, "backlog", "task", "edit", "TASK-1", "-l", "size-5,finish-moved")
    assert command(repo, "board-check", "moved").returncode == 0


@needs_backlog
def test_moved_survives_unicode_names_and_a_board_in_a_subfolder(tmp_path: Path) -> None:
    mono = tmp_path / "mono"
    board_root = mono / "svc"
    board_root.mkdir(parents=True)
    sh(mono, "git", "init", "-q", "-b", "main")
    sh(mono, "git", "config", "user.email", "test@example.com")
    sh(mono, "git", "config", "user.name", "Test")
    sh(board_root, "backlog", "init", "Test", "--defaults")
    sh(board_root, "backlog", "config", "set", "remoteOperations", "false")
    sh(board_root, "backlog", "task", "create", "Café menu, naïve", "-l", "size-1", "--ac", "One")
    sh(mono, "git", "add", "-A")
    sh(mono, "git", "commit", "-qm", "accept")
    sh(board_root, "backlog", "task", "edit", "1", "--ac", "Sneaky new criterion")
    result = command(board_root, "board-check", "moved")
    assert result.returncode == 1 and "added 'Sneaky new criterion'" in result.stdout


@needs_backlog
def test_without_git_the_moved_check_says_it_did_not_run(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    sh(plain, "git", "init", "-q", "-b", "main")
    sh(plain, "backlog", "init", "Test", "--defaults")
    shutil.rmtree(plain / ".git")
    result = command(plain, "board-check", "moved")
    assert result.returncode == 0 and "not checked: no git history" in result.stdout


@needs_backlog
def test_board_check_without_a_board_exits_2(tmp_path: Path) -> None:
    result = command(tmp_path, "board-check")
    assert result.returncode == 2 and "no backlog/config.yml" in result.stderr


@needs_backlog
def test_close_task_refuses_and_changes_nothing(repo: Path) -> None:
    before = sh(repo, "git", "status", "--porcelain")
    result = command(repo, "close-task", "1.1", "--notes", "Looks fine")
    assert result.returncode == 1
    assert 'TASK-1.1 close: criterion #1 is not met: "Tests pass"' in result.stdout
    assert sh(repo, "git", "status", "--porcelain") == before


@needs_backlog
def test_close_task_closes_and_commits_only_the_task(repo: Path) -> None:
    sh(repo, "backlog", "task", "edit", "1.1", "--check-ac", "1")
    (repo / "unrelated.txt").write_text("not part of the close")
    sh(repo, "git", "add", "unrelated.txt")
    result = command(repo, "close-task", "1.1", "--notes", "Verdict: closes. No findings filed.")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("closed TASK-1.1 in ")
    assert sh(repo, "git", "log", "-1", "--format=%s") == "Close TASK-1.1: Endpoint\n"
    assert (
        sh(repo, "git", "show", "--name-only", "--format=", "HEAD").strip()
        == "backlog/tasks/task-1.1 - Endpoint.md"
    )
    assert "A  unrelated.txt" in sh(repo, "git", "status", "--porcelain")
    text = (repo / "backlog" / "tasks" / "task-1.1 - Endpoint.md").read_text()
    assert "status: Done" in text and "Verdict: closes. No findings filed." in text


@needs_backlog
@pytest.mark.parametrize("how", ["cli", "file"])
def test_close_task_refuses_criteria_reworded_during_review(repo: Path, how: str) -> None:
    task_file = repo / "backlog" / "tasks" / "task-1.1 - Endpoint.md"
    if how == "cli":
        sh(repo, "backlog", "task", "edit", "1.1", "--remove-ac", "1", "--ac", "It compiles")
        sh(repo, "backlog", "task", "edit", "1.1", "--check-ac", "1", "-l", "size-2,finish-moved")
    else:  # a write the guard never saw
        text = task_file.read_text().replace("- [ ] #1 Tests pass", "- [x] #1 It compiles")
        task_file.write_text(text.replace("  - size-2", "  - size-2\n  - finish-moved"))
    before = task_file.read_text()
    result = command(repo, "close-task", "1.1", "--notes", "Closes")
    assert result.returncode == 1
    assert "removed 'Tests pass'; added 'It compiles'" in result.stdout
    assert "the finish-moved label is not committed" in result.stdout
    assert task_file.read_text() == before


@needs_backlog
def test_close_task_accepts_a_moved_finish_line_committed_before_review(repo: Path) -> None:
    sh(repo, "backlog", "task", "edit", "1.1", "--ac", "Docs updated", "-l", "size-2,finish-moved")
    sh(repo, "backlog", "task", "edit", "1.1", "--append-notes", "Added docs: the API changed.")
    sh(repo, "git", "commit", "-qam", "Move the finish line of TASK-1.1")
    sh(repo, "backlog", "task", "edit", "1.1", "--check-ac", "1", "--check-ac", "2")
    result = command(repo, "close-task", "1.1", "--notes", "Closes")
    assert result.returncode == 0, result.stdout + result.stderr


@needs_backlog
def test_close_task_refuses_a_task_never_committed(repo: Path) -> None:
    sh(repo, "backlog", "task", "create", "Late", "-p", "TASK-1", "--type", "task", "--ac", "Done")
    sh(repo, "backlog", "task", "edit", "1.2", "--check-ac", "1")
    result = command(repo, "close-task", "1.2", "--notes", "Closes")
    assert result.returncode == 1 and "its file has never been committed" in result.stdout


def failing_test(repo: Path) -> Path:
    test = repo / "tests" / "test_bug.py"
    test.parent.mkdir(exist_ok=True)
    test.write_text("import sys\nprint('expected 2, got 1')\nsys.exit(1)\n")
    sh(repo, "git", "add", "tests/test_bug.py")
    sh(repo, "git", "commit", "-qm", "Reproduce the bug")
    return test


@needs_backlog
def test_record_check_puts_the_raw_output_on_the_task(repo: Path) -> None:
    result = command(repo, "record-check", "1.1", "--lines", "2", "--", "seq 3; exit 3")
    assert result.returncode == 3 and result.stdout == "1\n2\n3\n"
    notes = b.parse_task((repo / "backlog/tasks/task-1.1 - Endpoint.md").read_text(), "x").notes
    assert (
        notes == "Check `seq 3; exit 3` exited 3\n\n(1 earlier lines omitted)\n```text\n2\n3\n```"
    )


@needs_backlog
def test_record_check_runs_a_declared_tier(repo: Path) -> None:
    missing = command(repo, "record-check", "1.1", "--tier", "full")
    assert missing.returncode == 2 and "no checks declared" in missing.stderr
    (repo / ".claude").mkdir()
    (repo / ".claude" / "checks.json").write_text('{"fast": "echo fast", "full": "echo full"}')
    result = command(repo, "record-check", "1.1", "--tier", "full")
    assert result.returncode == 0 and result.stdout == "full\n"
    notes = b.parse_task((repo / "backlog/tasks/task-1.1 - Endpoint.md").read_text(), "x").notes
    assert notes.startswith("Check `echo full` exited 0")
    both = command(repo, "record-check", "1.1", "--tier", "fast", "--", "echo x")
    assert both.returncode == 2 and "takes no command" in both.stderr


@needs_backlog
def test_a_declared_tier_runs_in_the_boards_repository(repo: Path, tmp_path: Path) -> None:
    (repo / ".claude").mkdir()
    (repo / ".claude" / "checks.json").write_text('{"fast": "pwd", "full": "pwd"}')
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".claude").mkdir()
    (elsewhere / ".claude" / "checks.json").write_text('{"full": "echo the wrong repository"}')
    result = command(elsewhere, "record-check", "1.1", "--tier", "full", "--root", str(repo))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(repo.resolve())


@needs_backlog
def test_close_task_refuses_checks_changed_since_acceptance(repo: Path) -> None:
    (repo / ".claude").mkdir()
    checks = repo / ".claude" / "checks.json"
    checks.write_text('{"fast": "just test", "full": "just check"}')
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "Declare the checks")
    sh(repo, "backlog", "task", "create", "Late", "-p", "TASK-1", "--type", "task", "--ac", "Ok")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "Accept TASK-1.2")
    checks.write_text('{"fast": "true", "full": "true"}')
    sh(repo, "backlog", "task", "edit", "1.2", "--check-ac", "1")
    sh(repo, "git", "commit", "-qam", "Weaken the checks")
    refused = command(repo, "close-task", "1.2", "--notes", "Closes")
    assert refused.returncode == 1
    assert ".claude/checks.json changed since TASK-1.2 was accepted" in refused.stdout
    sh(repo, "backlog", "task", "edit", "1.2", "--append-notes", "Checks changed: just moved.")
    sh(repo, "git", "commit", "-qam", "Explain")
    assert command(repo, "close-task", "1.2", "--notes", "Closes").returncode == 0


@needs_backlog
def test_record_check_wants_a_command(repo: Path) -> None:
    assert command(repo, "record-check", "1.1").returncode == 2


@needs_backlog
def test_a_fix_that_edits_its_repro_test_does_not_close(repo: Path) -> None:
    test = failing_test(repo)
    recorded = command(repo, "record-check", "1.1", "--repro", "--", "python3 tests/test_bug.py")
    assert recorded.returncode == 0, recorded.stderr
    test.write_text("print('fixed by editing the test')\n")
    sh(repo, "backlog", "task", "edit", "1.1", "--check-ac", "1")
    sh(repo, "git", "commit", "-qam", "Fix")
    result = command(repo, "close-task", "1.1", "--notes", "Closes")
    assert result.returncode == 1
    assert "the repro test tests/test_bug.py changed since" in result.stdout


@needs_backlog
def test_repro_must_fail_and_be_committed(repo: Path) -> None:
    test = failing_test(repo)
    test.write_text("print('passes')\n")
    dirty = command(repo, "record-check", "1.1", "--repro", "--", "python3 tests/test_bug.py")
    assert dirty.returncode == 2 and "commit the repro test first" in dirty.stderr
    sh(repo, "git", "commit", "-qam", "A passing test")
    passing = command(repo, "record-check", "1.1", "--repro", "--", "python3 tests/test_bug.py")
    assert passing.returncode == 2 and "doesn't reproduce the bug" in passing.stderr


@needs_backlog
def test_board_check_route_and_parallel(repo: Path) -> None:
    route = command(repo, "board-check", "--json", "route", "1.1")
    assert route.returncode == 0
    assert json.loads(route.stdout) == {
        "id": "TASK-1.1",
        "model": "sonnet",
        "effort": "medium",
        "why": "a leaf at size 2 to 5",
    }
    assert command(repo, "board-check", "route", "1").stdout.startswith(
        "TASK-1 route: opus at high"
    )
    alone = command(repo, "board-check", "parallel", "1.1")
    assert alone.returncode == 2 and "two or more" in alone.stderr
    sweep = command(repo, "board-check", "route", "--sweep")
    assert sweep.returncode == 0 and sweep.stdout.startswith("sweep route: ")


@needs_backlog
def test_close_task_wants_notes(repo: Path) -> None:
    result = command(repo, "close-task", "1.1", "--notes", "  ")
    assert result.returncode == 2 and "--notes is empty" in result.stderr


# --- the shipped examples ------------------------------------------------------------


def examples() -> list[str]:
    text = (ROOT / "docs" / "board-examples.md").read_text()
    return re.findall(r"```markdown\n(.*?)```", text, re.S)


def test_examples_agree_with_board_check() -> None:
    draft, accepted, spec_text, plan_text, design, leaf_text, second, _decision = examples()
    name = "claims-status"
    where = "backlog/intents/%s.md" % name
    draft_intent = b.parse_intent(draft, where)
    intent_task = b.parse_intent(
        accepted.split("## Notes")[0]
        + draft.split("---\n", 2)[2]
        + "\n## Notes"
        + accepted.split("## Notes")[1],
        where,
    )
    tasks = [
        b.parse_task(design, "backlog/tasks/task-1 - Decide.md"),
        b.parse_task(leaf_text, "backlog/tasks/task-2 - Status.md"),
        b.parse_task(second, "backlog/tasks/task-3 - List.md"),
    ]
    whole = Board(
        (intent_task, *tasks),
        (),
        b.TYPES,
        "task",
        (b.parse_named(spec_text, "backlog/specs/%s.md" % name),),
        (b.parse_named(plan_text, "backlog/plans/%s.md" % name),),
    )
    assert [f.message.split(":")[0] for f in b.check_ready(board(draft_intent), draft_intent)] == [
        "open question is neither answered nor carried forward"
    ]
    assert b.check_ready(whole, tasks[0]) == []
    assert b.check_board(whole, {}) == []
    assert b.check_spec(whole, whole.specs[0], coverage=True) == []
    assert b.check_plan(whole, tasks[1]) == []
    assert b.check_plan(whole, intent_task) == []


# --- migrating the old layout ---------------------------------------------------------

sys.path.insert(0, str(ROOT / "scripts"))

OLD_PLAN = """---
id: doc-2
title: 'Plan: Claims status self-service'
type: other
---
## Slices

1. **One claim.** A customer opens a claim.
   Tester sees: its status.
   Depends on: none.
2. **All claims.** A customer lists every open claim.
   Tester sees: three open claims.
   Depends on: slice 1.
"""


def old_board(root: Path, plan: str = OLD_PLAN, tagged: bool = True) -> None:
    """The intent task, its spec doc and plan doc, and two children, as the old layout has them."""
    for folder in ("tasks", "docs/specs", "docs/plans"):
        (root / "backlog" / folder).mkdir(parents=True)
    (root / "backlog" / "config.yml").write_text(
        'task_prefix: "task"\ntypes: ["intent", "design", "spike", "task", "bug"]\n'
    )
    (root / "backlog" / "tasks" / "task-1 - Claims.md").write_text(INTENT)
    (root / "backlog" / "docs" / "specs" / "doc-1 - Spec-Claims-status-self-service.md").write_text(
        SPEC
    )
    (root / "backlog" / "docs" / "plans" / "doc-2 - Plan.md").write_text(plan)
    for number in (1, 2):
        extra = "  - slice-%d\n" % number if tagged else ""
        (root / "backlog" / "tasks" / ("task-1.%d - Part.md" % number)).write_text(
            "---\nid: TASK-1.%d\ntitle: Part %d\nstatus: To Do\nlabels:\n  - size-2\n%s"
            "dependencies: []\nparent_task_id: TASK-1\ntype: task\n---\n\n"
            "## Acceptance Criteria\n<!-- AC:BEGIN -->\n- [ ] #1 Delivers (R%d)\n<!-- AC:END -->\n"
            % (number, number, extra, number)
        )


def r_numbers(findings: list[b.Finding]) -> list[str]:
    return sorted(
        match.group(1) for f in findings if (match := re.search(r"R(\d+) is not cited", f.message))
    )


def test_migrating_keeps_the_findings(tmp_path: Path) -> None:
    old_board(tmp_path)
    before = b.check_board(b.load_board(tmp_path), {})
    assert r_numbers(before) == []  # R1 and R2 are cited
    (tmp_path / "backlog" / "tasks" / "task-1.2 - Part.md").unlink()
    before = b.check_board(b.load_board(tmp_path), {})
    result = command(tmp_path, "migrate-layout", str(tmp_path), "--name", "claims-status")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "backlog" / "intents" / "claims-status.md").is_file()
    assert (tmp_path / "backlog" / "specs" / "claims-status.md").is_file()
    assert (tmp_path / "backlog" / "plans" / "claims-status.md").is_file()
    assert (
        not list((tmp_path / "backlog").rglob("task-1 - *"))
        and not (
            tmp_path / "backlog" / "docs" / "specs" / "doc-1 - Spec-Claims-status-self-service.md"
        ).exists()
    )
    after = b.check_board(b.load_board(tmp_path), {})
    assert r_numbers(after) == r_numbers(before) == ["2"]


def test_migrating_ties_children_to_the_work_by_label(tmp_path: Path) -> None:
    old_board(tmp_path)
    command(tmp_path, "migrate-layout", str(tmp_path), "--name", "claims-status")
    text = (tmp_path / "backlog" / "tasks" / "task-1.1 - Part.md").read_text()
    task = b.parse_task(text, "backlog/tasks/task-1.1 - Part.md")
    assert task.parent == "" and task.labels == ("size-2", "slice-1", "claims-status")
    assert "references:\n  - backlog/intents/claims-status.md" in text
    assert "Intent:" not in (tmp_path / "backlog" / "specs" / "claims-status.md").read_text()
    moved = b.parse_intent(
        (tmp_path / "backlog" / "intents" / "claims-status.md").read_text(), "backlog/intents/x.md"
    )
    assert moved.title == "Claims: status self-service" and moved.labels == ("size-5",)
    assert moved.criteria == intent().criteria
    assert b.open_questions(moved.description) == b.open_questions(intent().description)


def test_dry_run_changes_nothing_and_a_plan_without_slices_is_a_to_do(tmp_path: Path) -> None:
    old_board(tmp_path, plan="---\nid: doc-2\n---\n## Order\n\nFirst.\n", tagged=False)
    before = sorted(p.as_posix() for p in tmp_path.rglob("*.md"))
    result = command(
        tmp_path, "migrate-layout", str(tmp_path), "--name", "claims-status", "--dry-run"
    )
    assert result.returncode == 0 and result.stdout.count("would: ") == 5
    assert sorted(p.as_posix() for p in tmp_path.rglob("*.md")) == before
    assert "by hand: backlog/plans/claims-status.md has no numbered '## Slices'" in result.stdout
    assert "by hand: TASK-1.1: add the slice-n label" in result.stdout


def test_migrating_refuses_a_guess(tmp_path: Path) -> None:
    old_board(tmp_path)
    extra = tmp_path / "backlog" / "tasks" / "task-2 - Other.md"
    extra.write_text(INTENT.replace("TASK-1", "TASK-2"))
    result = command(tmp_path, "migrate-layout", str(tmp_path), "--name", "claims-status")
    assert result.returncode == 2 and "found 2 intent tasks" in result.stderr
    bad = command(
        tmp_path, "migrate-layout", str(tmp_path), "--name", "Task-9", "--intent", "TASK-1"
    )
    assert bad.returncode == 2 and "not a usable name" in bad.stderr


def test_ticking_an_intent_changes_only_the_boxes() -> None:
    ticked = b.ticked_intent_text(NAMED_INTENT, (1,))
    assert b.parse_intent(ticked, "backlog/intents/x.md").criteria == (
        Item(True, "Customers see claim status"),
        Item(True, "No new PII in the portal session"),
    )
    assert (
        ticked.replace("- [x] Customers see claim status", "- [ ] Customers see claim status")
        == NAMED_INTENT
    )
    assert "- [ ] Do third-party loss adjusters" in ticked
    with pytest.raises(LookupError, match="no criterion #3: the intent has 2"):
        b.ticked_intent_text(NAMED_INTENT, (3,))


def test_tick_intent_ticks_through_the_command(tmp_path: Path) -> None:
    lay_out(tmp_path)
    result = command(tmp_path, "tick-intent", NAME, "1")
    assert result.returncode == 0 and result.stdout.strip() == "ticked claims-status: #1"
    text = (tmp_path / "backlog" / "intents" / ("%s.md" % NAME)).read_text()
    assert "- [x] Customers see claim status" in text
    assert command(tmp_path, "tick-intent", NAME, "9").returncode == 2


# --- the approvals before a split -----------------------------------------------------


def test_a_split_needs_an_accepted_intent_an_approved_spec_and_a_spec_at_size_8() -> None:
    board = work(member("TASK-1", "slice-1"), member("TASK-2", "slice-2"))
    assert b.check_gates(board, named_intent()) == []
    draft = named_intent(status="Draft")
    assert messages(b.check_gates(work(member("TASK-1", "slice-1")), draft))[0].startswith(
        "has 1 accepted tasks but is still a Draft: accept the intent first"
    )
    unapproved = named_intent(notes="")
    unapproved_board = Board(
        (unapproved, member("TASK-1", "slice-1")), (), b.TYPES, "task", (named_spec(),), ()
    )
    assert messages(b.check_gates(unapproved_board, unapproved)) == [
        "has tasks but its spec is not approved: product approves the whole before the work is "
        "split. Add 'Spec approved by @name' under '## Notes' in backlog/intents/claims-status.md"
    ]
    big = named_intent(labels=("size-8",))
    no_spec = Board((big, member("TASK-1", "slice-1")), (), b.TYPES, "task")
    assert messages(b.check_gates(no_spec, big)) == [
        "is size-8 with tasks but has no backlog/specs/claims-status.md: work this size gets its "
        "requirements written down and approved before it is split"
    ]


def test_no_tasks_means_no_gates_yet() -> None:
    assert b.check_gates(work(), named_intent(status="Draft", notes="")) == []
