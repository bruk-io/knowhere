"""Control bands over a metric's readings: is the newest one out of the ordinary?

The detection is the playbook's, and deterministic: a baseline of earlier readings gives
a mean and a standard deviation, and the newest reading is checked against 1, 2 and 3
sigma, with two Western Electric rules for slow drift (four of the last five above 1
sigma, eight in a row above the mean). No model is involved. `band-check` is the thin
command over it, and the workflow acts on the tier it prints. Written for Python 3.9
and the standard library.
"""

from __future__ import annotations

import statistics
from typing import NamedTuple

MIN_SIGMA = 0.01  # a flat baseline would otherwise flag the smallest change
MIN_BASELINE = 7  # readings needed before the newest can be judged against them


class Verdict(NamedTuple):
    tier: str  # "none", "1sigma", "2sigma" or "3sigma"
    rule: str
    reading: float
    mean: float
    sigma: float


class BandError(ValueError):
    """Too few readings to judge the newest one."""


def above(readings: list[float], line: float, need: int, out_of: int) -> bool:
    """Whether at least `need` of the last `out_of` readings are above `line`."""
    return sum(reading > line for reading in readings[-out_of:]) >= need


def tier(readings: list[float]) -> Verdict:
    """The band the newest reading falls in, against the readings before it.

    Raises:
        BandError: there are fewer than MIN_BASELINE readings before the newest.
    """
    baseline = readings[:-1]
    if len(baseline) < MIN_BASELINE:
        raise BandError(
            "need at least %d readings before the newest, have %d" % (MIN_BASELINE, len(baseline))
        )
    mean = statistics.mean(baseline)
    sigma = max(statistics.stdev(baseline), MIN_SIGMA)
    rules = (
        ("3sigma", "reading above 3 sigma", above(readings, mean + 3 * sigma, 1, 1)),
        ("2sigma", "reading above 2 sigma", above(readings, mean + 2 * sigma, 1, 1)),
        ("2sigma", "drift: 4 of the last 5 above 1 sigma", above(readings, mean + sigma, 4, 5)),
        ("2sigma", "drift: 8 in a row above the mean", above(readings, mean, 8, 8)),
        ("1sigma", "reading above 1 sigma", above(readings, mean + sigma, 1, 1)),
    )
    for name, rule, tripped in rules:
        if tripped:
            return Verdict(name, rule, readings[-1], round(mean, 4), round(sigma, 4))
    return Verdict("none", "", readings[-1], round(mean, 4), round(sigma, 4))
