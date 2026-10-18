"""Tests for scripts/loop.py and the next-change, gated-paths and run-check commands.

The decisions are tested on plain values. The commands are tested as programs against a
throwaway git repository with a bare remote, so `next-change` sees real branches. Set
HOOK_PYTHON to run them under another interpreter.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import artefact as a  # noqa: E402
import loop  # noqa: E402

PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)

SPEC = """# Spec: a thing

Intent: [intent.md](intent.md), by Someone. Status: draft.

Applied: the house rules.

## Requirements

- **R1.** It works.
- **R2.** It stays fast.
- **R3.** It reports.

## Design

### What each piece is

| Piece | Why |
|---|---|
| 01 not a change | it sits in another table |

### Delivery order

| Change | Delivers |
|---|---|
| 01 The core | R1 |
| 02 Speed and reports | R2, R3 |

Each change is one PR.

### Afterwards

| Other | Table |
|---|---|
| 03 not a change either | R1 |

## Constraint mapping

| Intent constraint | Met by |
|---|---|
| Keep it small | R1 |

## Open questions

- [x] None.

## Areas of concern

1. **None.** Owner: Someone. Proposed: nothing.
"""

ORDER = loop.delivery_order(a.parse(SPEC, "spec.md"))
NONE: frozenset[str] = frozenset()


# --- the delivery order and the next change -----------------------------------------


def test_delivery_order_reads_only_its_own_table():
    assert ORDER == (
        loop.Change("01", "The core", (1,)),
        loop.Change("02", "Speed and reports", (2, 3)),
    )


def test_first_change_is_built_first():
    assert loop.next_change(ORDER, NONE, NONE) == loop.Next(loop.Step.BUILD, ORDER[0])


def test_a_planned_change_is_skipped():
    assert loop.next_change(ORDER, frozenset({"01"}), NONE) == loop.Next(loop.Step.BUILD, ORDER[1])


def test_a_change_in_flight_holds_the_rest():
    assert loop.next_change(ORDER, NONE, frozenset({"01"})) == loop.Next(loop.Step.TAKEN, ORDER[0])


def test_every_change_planned_is_done():
    assert loop.next_change(ORDER, frozenset({"01", "02"}), NONE) == loop.Next(loop.Step.DONE, None)


def test_this_intents_own_spec_has_eight_changes():
    spec = a.read(REPO / "intent" / "self-running-loop" / "spec.md")
    assert spec is not None
    assert [change.number for change in loop.delivery_order(spec)] == [
        "%02d" % n for n in range(1, 9)
    ]


# --- CODEOWNERS ---------------------------------------------------------------------

CODEOWNERS = """
# owners
/intent/*/spec.md @owner
.github/ @owner
*.c4 @owner
plugins/*/hooks/ @owner
docs/generated/ @owner
docs/generated/free.md
/notes/* @owner
"""
RULES = loop.parse_codeowners(CODEOWNERS)


@pytest.mark.parametrize(
    ("path", "owned"),
    [
        ("intent/thing/spec.md", True),
        ("intent/thing/intent.md", False),
        ("nested/intent/thing/spec.md", False),
        (".github/workflows/ci.yml", True),
        ("models/system.c4", True),
        ("deep/down/view.c4", True),
        ("plugins/philosophy/hooks/guard.py", True),
        ("plugins/philosophy/skills/build/SKILL.md", False),
        ("docs/generated/api.md", True),
        ("docs/generated/free.md", False),
        ("notes/today.md", True),
        ("notes/2026/today.md", False),
        ("README.md", False),
    ],
)
def test_codeowners_patterns_match_as_github_reads_them(path, owned):
    assert bool(loop.owners_of(path, RULES)) is owned


def test_gated_keeps_only_owned_paths():
    paths = ("README.md", ".github/workflows/ci.yml")
    assert loop.gated(paths, RULES) == (".github/workflows/ci.yml",)


# --- evidence -----------------------------------------------------------------------


def test_evidence_keeps_the_command_the_tail_and_the_exit_code():
    output = "\n".join("line %d" % n for n in range(1, 101)) + "\n"
    block = loop.evidence("make test", 1, output, 3)
    assert block.splitlines() == [
        "```",
        "$ make test",
        "line 98",
        "line 99",
        "line 100",
        "exit=1",
        "```",
    ]


def test_evidence_fences_output_that_holds_backticks():
    block = loop.evidence("x", 0, "```\nfake close\n````", 5)
    assert block.splitlines()[0] == "`````" and block.splitlines()[-1] == "`````"


def test_evidence_keeps_no_lines_for_zero():
    assert loop.evidence("x", 0, "a\nb\n", 0).splitlines() == ["```", "$ x", "exit=0", "```"]


def test_declared_reads_a_tier():
    text = json.dumps({"fast": "make test", "full": " "})
    assert (loop.declared(text, "fast"), loop.declared(text, "full")) == ("make test", None)


# --- the commands, against a throwaway repository -----------------------------------


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    )
    return done.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    git(work, "config", "user.email", "test@example.com")
    git(work, "config", "user.name", "Test")
    git(work, "remote", "add", "origin", str(remote))
    folder = work / "intent" / "thing"
    (folder / "plans").mkdir(parents=True)
    (folder / "spec.md").write_text(SPEC)
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "spec")
    git(work, "push", "-q", "origin", "main")
    return work


def command(name: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / name), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def test_next_change_names_the_first_change(repo):
    result = command("next-change", "intent/thing", cwd=repo)
    assert (result.returncode, result.stdout) == (0, "build 01\tThe core\tR1\n")


def test_next_change_holds_while_a_build_branch_exists(repo):
    git(repo, "push", "-q", "origin", "main:refs/heads/build/thing/01")
    result = command("next-change", "intent/thing", cwd=repo)
    assert (result.returncode, result.stdout) == (1, "taken 01\tThe core\n")


def test_next_change_moves_on_once_the_plan_is_in(repo):
    git(repo, "push", "-q", "origin", "main:refs/heads/build/thing/01")
    (repo / "intent" / "thing" / "plans" / "01-core.md").write_text("# Plan: the core\n")
    result = command("next-change", "intent/thing", cwd=repo)
    assert result.stdout.startswith("build 02\t")


def test_next_change_says_done(repo):
    for name in ("01-core.md", "02-speed.md"):
        (repo / "intent" / "thing" / "plans" / name).write_text("# Plan\n")
    result = command("next-change", "intent/thing", "--no-remote", cwd=repo)
    assert (result.returncode, result.stdout) == (1, "done\n")


def test_gated_paths_lists_owned_files(repo):
    (repo / ".github").mkdir()
    (repo / ".github" / "CODEOWNERS").write_text(CODEOWNERS)
    plan = repo / "intent" / "thing" / "plans" / "01-core.md"
    plan.write_text(
        "# Plan: x\n\n## Files that change\n\n- `src/a.py`\n- `.github/workflows/ci.yml`\n"
    )
    result = command("gated-paths", str(plan), cwd=repo)
    assert (result.returncode, result.stdout) == (1, ".github/workflows/ci.yml\t@owner\n")


def test_gated_paths_without_codeowners_gates_nothing(repo):
    plan = repo / "intent" / "thing" / "plans" / "01-core.md"
    plan.write_text("# Plan: x\n\n## Files that change\n\n- `.github/workflows/ci.yml`\n")
    assert command("gated-paths", str(plan), cwd=repo).returncode == 0


def test_run_check_prints_evidence_and_passes_the_exit_code_on(repo):
    (repo / ".claude").mkdir()
    (repo / ".claude" / "checks.json").write_text(json.dumps({"fast": "echo ok; exit 3"}))
    result = command("run-check", "fast", cwd=repo)
    assert result.returncode == 3
    assert result.stdout.splitlines() == ["```", "$ echo ok; exit 3", "ok", "exit=3", "```"]


def test_run_check_without_a_declaration_exits_2(repo):
    result = command("run-check", "fast", cwd=repo)
    assert result.returncode == 2
    assert result.stdout.startswith("run-check: ") and "checks.json" in result.stdout


def test_run_check_stops_a_check_that_runs_too_long(repo):
    (repo / ".claude").mkdir()
    (repo / ".claude" / "checks.json").write_text(json.dumps({"fast": "echo started; sleep 5"}))
    result = command("run-check", "fast", "--timeout", "1", cwd=repo)
    assert result.returncode == 124
    assert "started" in result.stdout and "stopped after 1s" in result.stdout


def test_run_check_refuses_negative_lines(repo):
    assert command("run-check", "fast", "--lines", "-5", cwd=repo).returncode == 2


def test_run_check_refuses_a_checks_file_that_is_not_an_object(repo):
    (repo / ".claude").mkdir()
    (repo / ".claude" / "checks.json").write_text("[]")
    result = command("run-check", "fast", cwd=repo)
    assert result.returncode == 2 and "JSON object" in result.stdout
