"""Tests for scripts/band.py and the band-check command."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import band  # noqa: E402

PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)
CALM = [0.2, 0.21, 0.19, 0.2, 0.22, 0.18, 0.2, 0.21, 0.19, 0.2]


@pytest.mark.parametrize(
    ("readings", "tier", "rule"),
    [
        (CALM + [1.9], "3sigma", "reading above 3 sigma"),
        (CALM + [0.228], "2sigma", "reading above 2 sigma"),
        (
            [0.2] * 10 + [0.25, 0.26, 0.25, 0.27, 0.25],
            "2sigma",
            "drift: 4 of the last 5 above 1 sigma",
        ),
        (CALM + [0.215], "1sigma", "reading above 1 sigma"),
        (CALM + [0.2], "none", ""),
    ],
)
def test_the_newest_reading_lands_in_its_band(readings, tier, rule):
    verdict = band.tier(readings)
    assert (verdict.tier, verdict.rule) == (tier, rule)


def test_eight_in_a_row_above_the_mean_is_drift():
    readings = [1.0, 3.0] * 8 + [2.1] * 8
    assert band.tier(readings).rule == "drift: 8 in a row above the mean"


def test_a_flat_baseline_does_not_flag_a_tiny_change():
    assert band.tier([0.5] * 10 + [0.505]).tier == "none"


def test_too_few_readings_is_an_error():
    with pytest.raises(band.BandError):
        band.tier([0.2] * 7)


def check(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "band-check"), "--metric", "m"],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_band_check_reads_day_value_pairs():
    pairs = [["2026-10-%02d" % (day + 1), value] for day, value in enumerate(CALM + [1.9])]
    result = check(json.dumps(pairs))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["tier"] == "3sigma"
    assert json.loads(result.stdout)["metric"] == "m"


def test_band_check_says_when_there_are_too_few_readings():
    result = check(json.dumps([0.1, 0.2]))
    assert result.returncode == 2 and "need at least" in result.stderr
