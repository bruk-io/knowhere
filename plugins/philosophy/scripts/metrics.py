"""The loop's own numbers, from git and PR history (intent/self-running-loop, R18, R19).

Two kinds. Readings are one value per day for a metric the control bands watch: the CI
failure rate, and the mean hours from a PR opening to its merge. The report is per
intent: how long each handover took, how much merged without the owner, what the
reviews found, and how often a spec changed after building began. The core takes plain
data (dates as ISO strings, as `gh` prints them) and returns values; the commands fetch
the data. Written for Python 3.9 and the standard library.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import NamedTuple, Optional

FAILED = frozenset({"failure", "timed_out", "startup_failure"})
FINISHED = FAILED | frozenset({"success"})


class Handovers(NamedTuple):
    """When each stage of one intent landed, as ISO timestamps, or None if not yet."""

    slug: str
    intent_merged: Optional[str]
    spec_opened: Optional[str]
    spec_merged: Optional[str]
    last_build_merged: Optional[str]


def when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def hours(start: Optional[str], end: Optional[str]) -> Optional[float]:
    if start is None or end is None:
        return None
    return round((when(end) - when(start)).total_seconds() / 3600, 2)


def day(stamp: str) -> str:
    return stamp[:10]


def ci_failure_rate(runs: list[dict]) -> list[tuple[str, float]]:
    """Per day, the share of finished runs that failed. Days with no finished run are
    left out rather than counted as zero."""
    finished: dict[str, int] = defaultdict(int)
    failed: dict[str, int] = defaultdict(int)
    for run in runs:
        if run.get("conclusion") in FINISHED:
            finished[day(run["createdAt"])] += 1
            failed[day(run["createdAt"])] += run["conclusion"] in FAILED
    return [(d, round(failed[d] / finished[d], 4)) for d in sorted(finished)]


def pr_cycle_hours(prs: list[dict]) -> list[tuple[str, float]]:
    """Per day of merge, the mean hours from a PR opening to its merge."""
    by_day: dict[str, list[float]] = defaultdict(list)
    for pr in prs:
        took = hours(pr.get("createdAt"), pr.get("mergedAt"))
        if took is not None:
            by_day[day(pr["mergedAt"])].append(took)
    return [(d, round(sum(v) / len(v), 2)) for d, v in sorted(by_day.items())]


def merged_without(prs: list[dict], owner: str) -> Optional[float]:
    """The share of merged PRs that merged with neither the owner's merge nor an
    approving review from them."""
    merged = [pr for pr in prs if pr.get("mergedAt")]
    if not merged:
        return None
    alone = [
        pr
        for pr in merged
        if (pr.get("mergedBy") or {}).get("login") != owner
        and not any(
            (review.get("author") or {}).get("login") == owner and review.get("state") == "APPROVED"
            for review in pr.get("reviews") or []
        )
    ]
    return round(len(alone) / len(merged), 4)


def important_findings(comments: list[dict], reviewer: str) -> int:
    """How many of the reviewer's comments on a PR are Important findings."""
    return sum(
        (comment.get("user") or comment.get("author") or {}).get("login") == reviewer
        and comment.get("body", "").lstrip().startswith("**Important")
        for comment in comments
    )


def spec_rework(spec_commits: list[str], first_plan: Optional[str]) -> int:
    """How many commits changed the spec after the intent's first plan landed."""
    if first_plan is None:
        return 0
    return sum(when(stamp) > when(first_plan) for stamp in spec_commits)


STALE_HOURS = 72


def stalled(taken: Optional[str], prs: list[dict], now: str) -> Optional[str]:
    """Why an intent has stalled, or None. `taken` is the change number whose build
    branch holds the intent (None when nothing holds it); `prs` are the PRs from that
    branch. It stalls when no PR from the branch is open, or the open one has waited
    more than STALE_HOURS."""
    if taken is None:
        return None
    open_prs = [pr for pr in prs if pr.get("state") == "OPEN"]
    if not open_prs:
        return "change %s is held by its build branch, but no PR from it is open" % taken
    waited = hours(min(pr["createdAt"] for pr in open_prs), now)
    if waited is not None and waited > STALE_HOURS:
        return "change %s's PR has been open %.0f hours" % (taken, waited)
    return None


def report_row(stages: Handovers) -> dict:
    return {
        "intent": stages.slug,
        "intent_to_spec_pr_hours": hours(stages.intent_merged, stages.spec_opened),
        "spec_to_last_build_hours": hours(stages.spec_merged, stages.last_build_merged),
    }
