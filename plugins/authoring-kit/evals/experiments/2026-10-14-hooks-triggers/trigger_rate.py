"""Trigger rate from an authoring-kit results.json: should-fire cases (those with a
skill-fired indicator) and near-misses (cases named *near-miss*, scored on not firing)."""
import json
import sys


def skill_called(run, skill):
    return any(s.get("kind") == "skill" and skill in s.get("title", "") for s in run.get("trajectory", []))


def summary(path, skill):
    res = json.load(open(path))
    fire, nm, per = [0, 0], [0, 0], []
    for c in res["cases"]:
        if c.get("skill") != skill:
            continue
        runs = c["with"]["runs"]
        hits = sum(skill_called(r, skill) for r in runs)
        if "near-miss" in c["name"]:
            nm[0] += hits; nm[1] += len(runs)
        else:
            fire[0] += hits; fire[1] += len(runs)
        per.append((c["name"], hits, len(runs)))
    return fire, nm, per, res["run"].get("costUsd")


if __name__ == "__main__":
    skill = sys.argv[1]
    for p in sys.argv[2:]:
        fire, nm, per, cost = summary(p, skill)
        print(f"{p}\n  should-fire {fire[0]}/{fire[1]}  near-miss false fires {nm[0]}/{nm[1]}  cost ${cost:.2f}")
        for name, h, n in per:
            print(f"    {name:40s} {h}/{n}")
