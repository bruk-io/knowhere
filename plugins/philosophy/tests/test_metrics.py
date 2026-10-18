"""Tests for scripts/metrics.py and the loop-readings and loop-metrics commands.

The commands run with a fake `gh` on PATH that answers from canned JSON, and
loop-metrics against a throwaway repository whose main has real merge commits.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import metrics  # noqa: E402

PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)
OWNER = "owner"


def test_ci_failure_rate_counts_only_finished_runs_per_day():
    runs = [
        {"conclusion": "success", "createdAt": "2026-10-01T01:00:00Z"},
        {"conclusion": "failure", "createdAt": "2026-10-01T02:00:00Z"},
        {"conclusion": "skipped", "createdAt": "2026-10-02T01:00:00Z"},
        {"conclusion": "", "createdAt": "2026-10-02T02:00:00Z"},
        {"conclusion": "success", "createdAt": "2026-10-03T01:00:00Z"},
    ]
    assert metrics.ci_failure_rate(runs) == [("2026-10-01", 0.5), ("2026-10-03", 0.0)]


def test_pr_cycle_hours_averages_by_day_of_merge():
    prs = [
        {"createdAt": "2026-10-01T00:00:00Z", "mergedAt": "2026-10-01T06:00:00Z"},
        {"createdAt": "2026-10-01T00:00:00Z", "mergedAt": "2026-10-01T10:00:00Z"},
        {"createdAt": "2026-10-01T00:00:00Z", "mergedAt": None},
    ]
    assert metrics.pr_cycle_hours(prs) == [("2026-10-01", 8.0)]


def test_merged_without_the_owner():
    prs = [
        {"mergedAt": "x", "mergedBy": {"login": OWNER}, "reviews": []},
        {"mergedAt": "x", "mergedBy": {"login": "claude[bot]"}, "reviews": []},
        {
            "mergedAt": "x",
            "mergedBy": {"login": "claude[bot]"},
            "reviews": [{"author": {"login": OWNER}, "state": "APPROVED"}],
        },
        {"mergedAt": "x", "mergedBy": {"login": "claude[bot]"}, "reviews": []},
    ]
    assert metrics.merged_without(prs, OWNER) == 0.5
    assert metrics.merged_without([], OWNER) is None


def test_important_findings_count_only_the_reviewers():
    comments = [
        {"user": {"login": "claude[bot]"}, "body": "**Important (policy):** x"},
        {"user": {"login": "claude[bot]"}, "body": "Nit: y"},
        {"user": {"login": OWNER}, "body": "**Important** from me"},
    ]
    assert metrics.important_findings(comments, "claude[bot]") == 1


def test_spec_rework_counts_changes_after_the_first_plan():
    commits = ["2026-10-01T00:00:00Z", "2026-10-04T00:00:00Z", "2026-10-05T00:00:00Z"]
    assert metrics.spec_rework(commits, "2026-10-03T00:00:00Z") == 2
    assert metrics.spec_rework(commits, None) == 0


def test_an_intent_nothing_holds_has_not_stalled():
    assert metrics.stalled(None, [], "2026-10-05T00:00:00Z") is None


def test_a_build_branch_with_no_open_pr_stalls_the_intent():
    prs = [{"state": "CLOSED", "createdAt": "2026-10-01T00:00:00Z"}]
    assert "no PR from it is open" in metrics.stalled("03", prs, "2026-10-01T01:00:00Z")
    assert "no PR from it is open" in metrics.stalled("03", [], "2026-10-01T01:00:00Z")


def test_a_pr_open_past_three_days_stalls_the_intent():
    prs = [{"state": "OPEN", "createdAt": "2026-10-01T00:00:00Z"}]
    assert metrics.stalled("03", prs, "2026-10-03T00:00:00Z") is None
    assert "open 96 hours" in metrics.stalled("03", prs, "2026-10-05T00:00:00Z")


def test_handover_hours():
    row = metrics.report_row(
        metrics.Handovers(
            "x", "2026-10-01T00:00:00Z", "2026-10-01T01:30:00Z", "2026-10-02T00:00:00Z", None
        )
    )
    assert row == {"intent": "x", "intent_to_spec_pr_hours": 1.5, "spec_to_last_build_hours": None}


# --- the commands, with a fake gh ----------------------------------------------------

RUNS = [
    {"conclusion": "success" if day % 3 else "failure", "createdAt": "2026-10-%02dT01:00:00Z" % day}
    for day in range(1, 11)
]


def fake_gh(tmp_path: Path, answers: dict[str, str]) -> dict[str, str]:
    """A `gh` that prints the canned answer for the first argument that matches."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    cases = "\n".join(
        '  *"%s"*) cat %s ;;' % (key, tmp_path / ("answer-%d.json" % i))
        for i, key in enumerate(answers)
    )
    for i, value in enumerate(answers.values()):
        (tmp_path / ("answer-%d.json" % i)).write_text(value)
    (bin_dir / "gh").write_text('#!/bin/sh\ncase "$*" in\n%s\n  *) echo "[]" ;;\nesac\n' % cases)
    (bin_dir / "gh").chmod(0o755)
    return dict(os.environ, PATH="%s:%s" % (bin_dir, os.environ["PATH"]))


def test_loop_readings_prints_day_value_pairs(tmp_path):
    env = fake_gh(tmp_path, {"run list": json.dumps(RUNS)})
    result = subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "loop-readings"), "ci_failure_rate", "--days", "100000"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    pairs = json.loads(result.stdout)
    assert len(pairs) == 10 and pairs[2] == ["2026-10-03", 1.0]


def git(cwd: Path, *args: str, date: str = "") -> None:
    env = dict(os.environ)
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=env)


def merge_file(repo: Path, branch: str, path: str, date: str) -> None:
    git(repo, "checkout", "-q", "-b", branch)
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text("x\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", branch, date="2026-01-01T00:00:00Z")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge " + branch, branch, date=date)


@pytest.fixture
def merged_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    (repo / "README.md").write_text("x\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "start", date="2026-01-01T00:00:00Z")
    merge_file(repo, "intent/x", "intent/x/intent.md", "2026-10-01T00:00:00+00:00")
    merge_file(repo, "spec/x", "intent/x/spec.md", "2026-10-02T00:00:00+00:00")
    merge_file(repo, "build/x/01", "intent/x/plans/01-a.md", "2026-10-02T06:00:00+00:00")
    merge_file(repo, "build/x/02", "intent/x/plans/02-b.md", "2026-10-03T00:00:00+00:00")
    return repo


def test_loop_metrics_times_each_handover_from_merges(tmp_path, merged_repo):
    env = fake_gh(
        tmp_path,
        {
            "--head spec/x": json.dumps([{"createdAt": "2026-10-01T02:00:00Z"}]),
            "--state merged": json.dumps(
                [
                    {
                        "number": 7,
                        "mergedAt": "2026-10-03T00:00:00Z",
                        "mergedBy": {"login": "claude[bot]"},
                        "reviews": [],
                    }
                ]
            ),
            "pulls/7/comments": json.dumps(
                [{"user": {"login": "claude[bot]"}, "body": "**Important:** z"}]
            ),
        },
    )
    result = subprocess.run(
        [
            PYTHON,
            str(ROOT / "scripts" / "loop-metrics"),
            "--owner",
            OWNER,
            "--root",
            str(merged_repo),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["intents"] == [
        {
            "intent": "x",
            "intent_to_spec_pr_hours": 2.0,
            "spec_to_last_build_hours": 24.0,
            "changes_merged": 2,
            "spec_changes_after_first_plan": 0,
            "stalled": None,
        }
    ]
    assert report["merged_without_owner"] == 1.0
    assert report["important_findings_by_pr"] == {"7": 1}
