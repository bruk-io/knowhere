"""Tests for scripts/review-findings and scripts/answer-thread: the pure functions, then
each script as a subprocess against a fake `gh` that records its arguments and answers
with canned JSON.

Set HOOK_PYTHON to run them under another interpreter.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)


def _load(name: str, script: str):
    loader = SourceFileLoader(name, str(ROOT / "scripts" / script))
    spec = importlib.util.spec_from_file_location(name, loader.path, loader=loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


rf = _load("review_findings", "review-findings")
at = _load("answer_thread", "answer-thread")


def threads_answer(*nodes: dict) -> dict:
    return {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": list(nodes)}}}}}


def node(thread: str, resolved: bool, comment: int, body: str = "Nit: x") -> dict:
    return {
        "id": thread,
        "isResolved": resolved,
        "comments": {"nodes": [{"databaseId": comment, "path": "a.py", "line": 3, "body": body}]},
    }


def summary(body: str, when: str, login: str = "claude[bot]") -> dict:
    return {"id": hash(when), "user": {"login": login}, "created_at": when, "body": body}


# --- review-findings: the logic -------------------------------------------------------


def test_unresolved_keeps_only_open_threads_with_their_first_comment() -> None:
    found = rf.unresolved(threads_answer(node("PRRT_a", False, 1), node("PRRT_b", True, 2)))
    assert found == [
        {"thread": "PRRT_a", "comment": 1, "path": "a.py", "line": 3, "body": "Nit: x"}
    ]


def test_a_summary_someone_replied_to_since_counts_as_answered() -> None:
    comments = [
        summary("Nits: one.\n\nimportant=0 nits=1", "2026-10-19T01:00:00Z"),
        summary("Answered: declined, because...", "2026-10-19T01:30:00Z", login="brukhabtu"),
    ]
    found = rf.latest_summary(comments)
    assert found["answered"] is True
    assert rf.needs_answer([], found) is False


def test_latest_summary_is_the_reviewers_newest_comment() -> None:
    comments = [
        summary("old\nimportant=1 nits=0", "2026-10-19T01:00:00Z"),
        summary("new\nimportant=0 nits=0", "2026-10-19T02:00:00Z"),
        summary("mine", "2026-10-19T03:00:00Z", login="brukhabtu"),
    ]
    assert rf.latest_summary(comments)["body"].startswith("new")


@pytest.mark.parametrize(
    ("threads", "body", "needs"),
    [
        ([], None, False),
        ([], "Verdict: no findings.\n\nimportant=0 nits=0", False),
        ([], "Nits: one, below.\n\nimportant=0 nits=1", True),
        ([], "A summary with no counts line", True),
        ([{"thread": "PRRT_a"}], "important=0 nits=0", True),
    ],
)
def test_needs_answer(threads: list, body: str | None, needs: bool) -> None:
    found = None if body is None else {"id": 1, "body": body}
    assert rf.needs_answer(threads, found) is needs


# --- answer-thread: the logic ---------------------------------------------------------


@pytest.mark.parametrize(
    ("thread", "comment", "body", "ok"),
    [
        ("PRRT_kwDORKX2KM6tw5Ia", "4309747323", "Accepted, fixed in abc123.", True),
        ("PR_kwDO", "1", "x", False),
        ("PRRT_a; rm -rf /", "1", "x", False),
        ("PRRT_a", "12a", "x", False),
        ("PRRT_a", "1", "   ", False),
    ],
)
def test_refused(thread: str, comment: str, body: str, ok: bool) -> None:
    assert (at.refused(thread, comment, body) is None) is ok


# --- both scripts, against a fake gh -------------------------------------------------


@pytest.fixture
def fake_gh(tmp_path: Path) -> Path:
    """A `gh` on PATH that logs each call's arguments and answers from canned files."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "gh-calls"
    (tmp_path / "graphql.json").write_text(
        json.dumps(threads_answer(node("PRRT_open", False, 7), node("PRRT_done", True, 8)))
    )
    (tmp_path / "comments.json").write_text(
        json.dumps([[summary("Verdict: hold.\n\nimportant=1 nits=0", "2026-10-19T02:00:00Z")]])
    )
    script = bin_dir / "gh"
    script.write_text(
        "#!/bin/sh\n"
        'printf "%%s\\n" "$*" >> %s\n'
        'case "$*" in\n'
        '  *"api graphql"*resolveReviewThread*) echo \'{"data":{}}\' ;;\n'
        '  *"api graphql"*) cat %s ;;\n'
        '  *"/comments"*replies*) echo \'{"id": 1}\' ;;\n'
        '  *"/comments"*) cat %s ;;\n'
        "esac\n" % (log, tmp_path / "graphql.json", tmp_path / "comments.json")
    )
    script.chmod(0o755)
    return tmp_path


def run(script: str, fake: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PATH="%s:%s" % (fake / "bin", os.environ["PATH"]))
    env["GITHUB_REPOSITORY"] = "owner/repo"
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / script), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_review_findings_prints_the_open_thread_and_the_summary(fake_gh: Path) -> None:
    result = run("review-findings", fake_gh, "45")
    assert result.returncode == 0, result.stderr
    found = json.loads(result.stdout)
    assert [t["thread"] for t in found["threads"]] == ["PRRT_open"]
    assert found["summary"]["body"].endswith("important=1 nits=0")


def test_answer_thread_replies_then_resolves(fake_gh: Path) -> None:
    body = fake_gh / "reply.md"
    body.write_text("Accepted, fixed in abc123.")
    result = run("answer-thread", fake_gh, "45", "PRRT_open", "7", "--body-file", str(body))
    assert result.returncode == 0, result.stderr
    calls = (fake_gh / "gh-calls").read_text().splitlines()
    assert "repos/owner/repo/pulls/45/comments/7/replies" in calls[0]
    assert "resolveReviewThread" in calls[1] and "id=PRRT_open" in calls[1]


def test_answer_thread_refuses_a_bad_id_and_calls_nothing(fake_gh: Path) -> None:
    body = fake_gh / "reply.md"
    body.write_text("x")
    result = run("answer-thread", fake_gh, "45", "not-a-thread", "7", "--body-file", str(body))
    assert result.returncode == 2 and "review thread id" in result.stderr
    assert not (fake_gh / "gh-calls").exists()
