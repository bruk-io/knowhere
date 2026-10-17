#!/usr/bin/env python3
"""Does a skill written with the kit fire more often than one written without it?

Stage 1 runs the `description-e2e` cases (Claude writes a skill, with and without the
kit). Stage 2 takes each written skill, puts it alone in a throwaway plugin, and runs
the case's `triggers.json` prompts against it: should-fire prompts and near-misses.
The measure is how often the written skill is loaded.

    python3 evals/description_e2e.py run [--model haiku] [--judge-model haiku]
        [--runs-write 2] [--runs-probe 2] [-j 3] [--probes 3] [--probe-effort low]
    python3 evals/description_e2e.py summary evals/results/e2e-<stamp>/e2e.json

Stdlib only. Results go to evals/results/e2e-<stamp>/ (ignored by git).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report  # noqa: E402

PROBE_PLUGIN = "probe"
TAG = "description-e2e"
_PROBE_TOOLS = "[Read, Glob, Grep, Skill]"


# --- functional core -------------------------------------------------------------------

def description_of(skill_md: str) -> str:
    """The frontmatter `description`, as Claude Code would read it (plain, quoted or folded)."""
    m = re.match(r"---\n(.*?)\n---", skill_md, re.S)
    if not m:
        return ""
    lines = m.group(1).splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        value = line[len("description:"):].strip()
        if value[:1] in (">", "|"):
            block = []
            for nxt in lines[i + 1:]:
                if nxt and not nxt[0].isspace():
                    break
                block.append(nxt.strip())
            sep = " " if value.startswith(">") else "\n"
            return sep.join(b for b in block if b).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            inner = value[1:-1]
            return inner.replace("''", "'") if value[0] == "'" else inner.replace('\\"', '"')
        return value
    return ""


def _probe_case(skill: str, prompt: str, should_fire: bool) -> dict[str, str]:
    bounds = "min: 1" if should_fire else "min: 0\nmax: 0"
    return {
        "prompt.md": f"---\nmax_turns: 4\nallowed_tools: {_PROBE_TOOLS}\ntags: [probe]\n---\n\n{prompt}\n",
        "graders/fired.md": (f"---\ntype: tool_used\ntool: Skill\n"
                             f"input_match: '\"skill\"\\s*:\\s*\"{PROBE_PLUGIN}:{skill}\"'\n{bounds}\n---\n"),
    }


def probe_files(skill: str, triggers: Mapping[str, list[str]], skill_dir: Mapping[str, str]) -> dict[str, str]:
    """Every file of a throwaway plugin holding only the written skill and the trigger prompts."""
    files = {".claude-plugin/plugin.json": json.dumps({"name": PROBE_PLUGIN, "version": "0.0.0"}) + "\n"}
    files.update({f"skills/{skill}/{rel}": text for rel, text in skill_dir.items()})
    for kind, should in (("should_fire", True), ("near_miss", False)):
        for i, prompt in enumerate(triggers[kind], 1):
            prefix = "fire" if should else "miss"
            for rel, text in _probe_case(skill, prompt, should).items():
                files[f"evals/{prefix}-{i}/{rel}"] = text
    return files


def skill_loaded(lines: Iterable[str], skill: str) -> bool:
    """Whether the transcript shows a Skill call for the probe plugin's skill."""
    want = f"{PROBE_PLUGIN}:{skill}"
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "Skill" \
                    and (block.get("input") or {}).get("skill") == want:
                return True
    return False


def score_probe(raw: Mapping[str, Any], traces: Mapping[str, list[str]], skill: str) -> dict[str, list[int]]:
    """[loaded, runs] for should-fire and near-miss prompts of one probe run."""
    tally = {"should_fire": [0, 0], "near_miss": [0, 0]}
    for case in raw.get("cases", []):
        kind = "should_fire" if case["name"].startswith("fire-") else "near_miss"
        for run in case.get("arms", {}).get("with", []):
            tally[kind][1] += 1
            tally[kind][0] += skill_loaded(traces.get(run.get("tracePath") or "", []), skill)
    return tally


def summarise(records: list[Mapping[str, Any]]) -> dict[str, dict[str, list[int]]]:
    """Totals per arm across cases: should-fire loads and near-miss false loads."""
    out: dict[str, dict[str, list[int]]] = {}
    for r in records:
        arm = out.setdefault(r["arm"], {"should_fire": [0, 0], "near_miss": [0, 0], "written": [0, 0]})
        arm["written"][1] += 1
        arm["written"][0] += bool(r["description"])
        for kind in ("should_fire", "near_miss"):
            arm[kind][0] += r["probe"][kind][0]
            arm[kind][1] += r["probe"][kind][1]
    return out


def format_summary(records: list[Mapping[str, Any]]) -> str:
    rows = [f"{'case':24} {'arm':8} fired   false  description"]
    for r in records:
        sf, nm = r["probe"]["should_fire"], r["probe"]["near_miss"]
        desc = (r["description"] or "(no skill written)").replace("\n", " ")
        rows.append(f"{r['case']:24} {r['arm']:8} {sf[0]:>2}/{sf[1]:<3}  {nm[0]:>2}/{nm[1]:<3} {desc[:110]}")
    rows.append("")
    for arm, t in summarise(records).items():
        sf, nm, w = t["should_fire"], t["near_miss"], t["written"]
        rate = f"{sf[0] / sf[1]:.0%}" if sf[1] else "-"
        rows.append(f"{arm:8} should-fire {sf[0]}/{sf[1]} ({rate})  near-miss false fires {nm[0]}/{nm[1]}  "
                    f"skills written {w[0]}/{w[1]}")
    return "\n".join(rows)


# --- imperative shell ------------------------------------------------------------------

def _model_opts(args: argparse.Namespace) -> list[str]:
    opts = []
    if args.model:
        opts += ["--model", args.model]
    if args.judge_model:
        opts += ["--judge-model", args.judge_model]
    return opts


def _eval(plugin_dir: Path, opts: list[str], out: Path, effort: str | None = None) -> dict[str, Any]:
    raw_path = out / "raw.json"
    command = ["claude", "plugin", "eval", str(plugin_dir), "--trust-plugin", "--no-publish", "--keep-temp",
               *opts, "--json", str(raw_path), "--output-dir", str(out / "claude")]
    env = {**os.environ, "CLAUDE_CODE_EFFORT_LEVEL": effort} if effort else None
    subprocess.run(command, cwd=plugin_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else {}


def _runs(raw: Mapping[str, Any]) -> Iterable[tuple[str, str, int, Mapping[str, Any]]]:
    for case in raw.get("cases", []):
        for arm, runs in case.get("arms", {}).items():
            for i, run in enumerate(runs, 1):
                yield case["name"], arm, i, run


def _sandbox(run: Mapping[str, Any]) -> Path | None:
    trace = run.get("tracePath")
    return Path(trace).parent.parent if trace else None


def _read_traces(raw: Mapping[str, Any]) -> tuple[dict[str, list[str]], set[Path]]:
    traces, sandboxes = {}, set()
    for _, _, _, run in _runs(raw):
        trace, box = run.get("tracePath"), _sandbox(run)
        if trace and Path(trace).exists():
            traces[trace] = Path(trace).read_text(encoding="utf-8", errors="replace").splitlines()
        if box:
            sandboxes.add(box)
    return traces, sandboxes


def _written_skill(run: Mapping[str, Any], skill: str) -> dict[str, str]:
    box = _sandbox(run)
    root = box / "home" / "cwd" / "skills" / skill if box else None
    if not root or not root.is_dir():
        return {}
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(root.rglob("*")) if p.is_file()}


def _probe(job: tuple[Path, str, Mapping[str, list[str]], dict[str, str], list[str], str | None]) -> dict[str, list[int]]:
    out, skill, triggers, skill_dir, opts, effort = job
    plugin = out / "plugin"
    for rel, text in probe_files(skill, triggers, skill_dir).items():
        (plugin / rel).parent.mkdir(parents=True, exist_ok=True)
        (plugin / rel).write_text(text, encoding="utf-8")
    raw = _eval(plugin, opts, out, effort)
    traces, sandboxes = _read_traces(raw)
    for box in sandboxes:
        report._remove_sandbox(box)
    # The written skill is kept in e2e.json; a plugin tree left in results/ would be
    # linted as if it were part of this repository.
    shutil.rmtree(plugin, ignore_errors=True)
    return score_probe(raw, traces, skill)


def cmd_run(args: argparse.Namespace) -> int:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    out = HERE / "results" / f"e2e-{stamp}"
    (out / "write").mkdir(parents=True)
    write_opts = ["--tag", TAG, "--scaffold", "--allow-tools", "Write", "Edit", "--runs", str(args.runs_write),
                  "-j", str(args.j), *_model_opts(args)]
    print(f"Stage 1: writing skills ({' '.join(write_opts)})", file=sys.stderr)
    raw = _eval(report.PLUGIN_ROOT, write_opts, out / "write")
    if not raw:
        print("Error: stage 1 wrote no JSON result.", file=sys.stderr)
        return 1
    triggers = {c.name: json.loads((c / "triggers.json").read_text(encoding="utf-8"))
                for c in HERE.glob("*/*/") if (c / "triggers.json").exists()}
    records, jobs = [], []
    for case, arm, i, run in _runs(raw):
        if case not in triggers:
            continue
        skill = triggers[case]["skill"]
        written = _written_skill(run, skill)
        record = {"case": case, "arm": arm, "run": i, "skill": skill,
                  "description": description_of(written.get("SKILL.md", "")), "files": written,
                  "writeScore": run.get("score"),
                  "probe": {"should_fire": [0, len(triggers[case]["should_fire"]) * args.runs_probe],
                            "near_miss": [0, 0]}}
        records.append(record)
        if written.get("SKILL.md"):
            probe_dir = out / "probe" / f"{case}-{arm}-{i}"
            probe_dir.mkdir(parents=True)
            jobs.append((record, (probe_dir, skill, triggers[case], written,
                                  ["--ablation", "none", "--runs", str(args.runs_probe), "-j", str(args.j),
                                   *_model_opts(args)], args.probe_effort)))
    _, sandboxes = _read_traces(raw)
    for box in sandboxes:
        report._remove_sandbox(box)
    print(f"Stage 2: probing {len(jobs)} written skills", file=sys.stderr)
    with cf.ThreadPoolExecutor(max_workers=args.probes) as pool:
        for record, tally in zip([r for r, _ in jobs], pool.map(_probe, [j for _, j in jobs])):
            record["probe"] = tally
    result = {"run": {"startedAt": stamp, "model": args.model or "default", "judgeModel": args.judge_model or "default",
                      "probeEffort": args.probe_effort or "default", "runsWrite": args.runs_write, "runsProbe": args.runs_probe,
                      "costUsdStage1": raw.get("costUsd")},
              "records": records, "summary": summarise(records)}
    (out / "e2e.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(format_summary(records))
    print(out / "e2e.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--model")
    run.add_argument("--judge-model")
    run.add_argument("--runs-write", type=int, default=2)
    run.add_argument("--runs-probe", type=int, default=2)
    run.add_argument("-j", type=int, default=3, help="concurrency inside each claude plugin eval")
    run.add_argument("--probes", type=int, default=3, help="probe plugins evaluated at once")
    run.add_argument("--probe-effort", choices=("low", "medium", "high", "xhigh", "max"),
                     help="effort for stage 2 only (CLAUDE_CODE_EFFORT_LEVEL); stage 1 keeps the default")
    show = sub.add_parser("summary")
    show.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "summary":
        print(format_summary(json.loads(args.path.read_text(encoding="utf-8"))["records"]))
        return 0
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
