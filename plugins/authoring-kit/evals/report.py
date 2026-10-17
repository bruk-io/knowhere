#!/usr/bin/env python3
"""Run the eval suite and write two outputs: results.json and report.html.

    python3 evals/report.py run [claude plugin eval options...]
    python3 evals/report.py render <results.json> [-o report.html]

`run` calls `claude plugin eval .` from the plugin root with the options you
pass, adding `--keep-temp` and `--json` so every session's transcript survives
the run. It reads each transcript into a list of steps (the trajectory),
removes the sandboxes it kept, and writes into evals/results/<timestamp>/:

    results.json   the run, every case, every run of every arm, its grader
                   verdicts and its trajectory - the data the page is built from
    report.html    one self-contained page rendered from results.json
    raw.json       what `claude plugin eval --json` wrote, untouched

`render` rebuilds report.html from a results.json, for example after a change
to the page template.

The page's colours, type and spacing come from evals/_report/bh-01-tokens.json,
a copy of the bh-01 design system's tokens; its markup and script are
evals/_report/template.html. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
TOKENS_FILE = HERE / "_report" / "bh-01-tokens.json"
TEMPLATE_FILE = HERE / "_report" / "template.html"
RESULTS_SCHEMA = "authoring-kit-eval-results/1"

# Long tool inputs and outputs are cut to this many characters in the
# trajectory, so one runaway Read does not make the page unusable.
TEXT_CAP = 6000
_SANDBOX_RE = re.compile(r"^/tmp/claude-eval-[A-Za-z0-9]+$")
_WORKSPACE_RE = re.compile(r"/tmp/claude-eval-[A-Za-z0-9]+/home/cwd/?")
_LINT_GRADER_RE = re.compile(r"^lint-([A-Z]{2}\d{3})-")


# ---- functional core ------------------------------------------------------------

def _cap(text: str, limit: int = TEXT_CAP) -> tuple[str, bool]:
    return (text, False) if len(text) <= limit else (text[:limit], True)


def _plain(content: Any) -> str:
    """A tool result's content as text: a string, or the text parts of a block list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return "" if content is None else json.dumps(content)


def _short_path(path: str) -> str:
    return _WORKSPACE_RE.sub("", path)


def tool_summary(name: str, tool_input: Mapping[str, Any]) -> str:
    """One line that says what a tool call did, in the terms a reader cares about."""
    match name:
        case "Read" | "Write" | "Edit" | "NotebookEdit":
            return _short_path(str(tool_input.get("file_path", "")))
        case "Bash":
            return _short_path(str(tool_input.get("command", "")))
        case "Grep" | "Glob":
            where = tool_input.get("path")
            return f"{tool_input.get('pattern', '')}" + (f"  in {_short_path(str(where))}" if where else "")
        case "Skill":
            return str(tool_input.get("skill", ""))
        case "Agent" | "Task":
            kind = tool_input.get("subagent_type", "")
            return f"{kind}: {tool_input.get('description', '')}".strip(": ")
        case _:
            return _cap(json.dumps(tool_input, ensure_ascii=False), 160)[0]


def format_input(tool_input: Mapping[str, Any]) -> str:
    """A tool call's input for reading: short fields on one line, file contents
    and other long text as they would appear on disk rather than JSON-escaped."""
    out = []
    for key, value in tool_input.items():
        if isinstance(value, str) and ("\n" in value or len(value) > 100):
            out.append(f"{key}:\n{_short_path(value)}")
        else:
            shown = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            out.append(f"{key}: {_short_path(str(shown))}")
    return "\n".join(out)


def trajectory(lines: Iterable[str]) -> list[dict[str, Any]]:
    """The steps of one session, from its trace.jsonl lines.

    Each step is {kind, t, depth, title, body, truncated, status}. Kinds:
    session, hook, think, say, tool, skill, end. A tool step carries its
    result in `result` and is marked `status: "error"` when the tool failed
    or was denied. `t` is seconds since the first timestamped event; `depth`
    is 1 for steps inside a subagent.
    """
    steps: list[dict[str, Any]] = []
    by_tool_id: dict[str, dict[str, Any]] = {}
    start: dt.datetime | None = None
    last_t = 0.0

    def stamp(event: Mapping[str, Any]) -> float:
        nonlocal start, last_t
        raw = event.get("timestamp")
        if isinstance(raw, str):
            when = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            start = start or when
            last_t = (when - start).total_seconds()
        return last_t

    def add(kind: str, event: Mapping[str, Any], title: str, body: str = "", **extra: Any) -> dict[str, Any]:
        text, cut = _cap(body)
        step = {"kind": kind, "t": round(stamp(event), 1), "depth": 1 if event.get("parent_tool_use_id") else 0,
                "title": title, "body": text, "truncated": cut, "status": "ok", **extra}
        steps.append(step)
        return step

    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind, sub = event.get("type"), event.get("subtype")
        if kind == "system" and sub == "init":
            add("session", event, f"{event.get('model', '')}  ·  {event.get('permissionMode', '')}",
                "tools: " + ", ".join(event.get("tools", [])))
        elif kind == "system" and sub == "hook_response":
            output = event.get("output") or event.get("stdout") or ""
            add("hook", event, f"{event.get('hook_name', '')}  exit {event.get('exit_code', '')}", str(output),
                status="ok" if event.get("exit_code") in (0, None) else "error")
        elif kind == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "thinking":
                    # Thinking text is often withheld from the transcript; its duration is not.
                    text = block.get("thinking", "").strip()
                    took = event.get("thinking_duration_ms")
                    title = _cap(text.split("\n")[0], 140)[0] if text else (
                        f"(thinking not recorded, {took / 1000:.1f}s)" if isinstance(took, (int, float)) else "(thinking not recorded)")
                    add("think", event, title, text)
                elif block.get("type") == "text":
                    add("say", event, _cap(block.get("text", "").strip().split("\n")[0], 140)[0], block.get("text", ""))
                elif block.get("type") == "tool_use":
                    name = block.get("name", "")
                    tool_input = block.get("input") or {}
                    step = add("skill" if name == "Skill" else "tool", event,
                               tool_summary(name, tool_input),
                               format_input(tool_input),
                               tool=name, result="", resultTruncated=False)
                    by_tool_id[block.get("id", "")] = step
        elif kind == "user":
            stamp(event)
            content = (event.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    step = by_tool_id.get(block.get("tool_use_id", ""))
                    if step is None:
                        continue
                    text = _short_path(_plain(block.get("content")))
                    step["result"], step["resultTruncated"] = _cap(text)
                    denied = "denied" in text[:300].lower() or "no such tool available" in text[:200].lower()
                    if block.get("is_error") or denied:
                        step["status"] = "error"
        elif kind == "result":
            denials = event.get("permission_denials") or []
            body = "\n".join(f"denied: {d.get('tool_name', '')} {json.dumps(d.get('tool_input', {}))[:200]}"
                             for d in denials if isinstance(d, dict))
            add("end", event,
                f"{sub}  ·  {event.get('num_turns', '?')} turns  ·  {event.get('stop_reason', '')}", body,
                status="ok" if sub == "success" and not event.get("is_error") else "error")
    return steps


def case_meta(prompt_text: str) -> dict[str, Any]:
    """Tags and description from a case's prompt.md frontmatter."""
    tags = re.search(r"^tags:\s*\[([^\]]*)\]", prompt_text, re.M)
    desc = re.search(r'^description:\s*"?(.*?)"?\s*$', prompt_text, re.M)
    return {"tags": [t.strip() for t in tags.group(1).split(",")] if tags else [],
            "description": desc.group(1) if desc else ""}


def _kind(tags: list[str]) -> str:
    for k in ("capability", "regression", "judge-calibration"):
        if k in tags:
            return k
    return "untagged"


def _arm(runs: list[Mapping[str, Any]], trajectories: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out_runs = []
    for i, r in enumerate(runs, 1):
        graders = [{"name": g.get("name"), "passed": bool(g.get("passed")), "scored": g.get("scored", True),
                    "explanation": g.get("explanation") or "", "evidence": _cap(str(g.get("evidence") or ""), 1500)[0],
                    "votes": g.get("judgeVotes")} for g in r.get("graders", [])]
        out_runs.append({"n": i, "score": r.get("score"), "turns": r.get("turns"), "costUsd": r.get("costUsd"),
                         "durationSeconds": r.get("durationSeconds"), "error": r.get("error"),
                         "graders": graders, "trajectory": trajectories.get(r.get("tracePath") or "", [])})
    scores = [r["score"] for r in out_runs if isinstance(r["score"], (int, float))]
    return {"score": sum(scores) / len(scores) if scores else None, "runs": out_runs}


def build_results(raw: Mapping[str, Any], metas: Mapping[str, Mapping[str, Any]],
                  trajectories: Mapping[str, list[dict[str, Any]]], command: list[str]) -> dict[str, Any]:
    """Our results document: the raw run regrouped by skill and kind, with trajectories."""
    cases = []
    for c in raw.get("cases", []):
        directory = c.get("dir", "")
        parts = Path(directory).parts
        skill = parts[1] if len(parts) > 2 else "suite"
        meta = metas.get(directory, {"tags": [], "description": ""})
        arms = c.get("arms", {})
        with_arm = _arm(arms.get("with", []), trajectories)
        without_arm = _arm(arms.get("without", []), trajectories) if arms.get("without") else None
        fired = [any(g["name"] == "skill-fired" and g["passed"] for g in r["graders"]) for r in with_arm["runs"]]
        has_fired_grader = any(g.get("name") == "skill-fired" for g in c.get("graders", []))
        expected = None
        if _kind(meta["tags"]) == "judge-calibration":
            expected = "pass" if "-pass-" in c.get("name", "") else "fail"
        cases.append({
            "name": c.get("name"), "skill": skill, "dir": directory, "tags": meta["tags"],
            "kind": _kind(meta["tags"]), "description": meta["description"], "prompt": c.get("promptMarkdown", ""),
            "graders": [{"name": g.get("name"), "type": g.get("type"),
                         "lintRule": (m.group(1) if (m := _LINT_GRADER_RE.match(g.get("name") or "")) else None)}
                        for g in c.get("graders", [])],
            "with": with_arm, "without": without_arm, "delta": (c.get("aggregates") or {}).get("delta"),
            "fired": {"count": sum(fired), "of": len(fired)} if has_fired_grader else None,
            "expected": expected,
        })
    skills: dict[str, dict[str, Any]] = {}
    for case in cases:
        s = skills.setdefault(case["skill"], {"name": case["skill"], "cases": 0, "fired": 0, "firedOf": 0,
                                              "by": {}})
        s["cases"] += 1
        if case["fired"]:
            s["fired"] += case["fired"]["count"]
            s["firedOf"] += case["fired"]["of"]
        k = s["by"].setdefault(case["kind"], {"cases": 0, "with": [], "without": []})
        k["cases"] += 1
        if case["with"]["score"] is not None:
            k["with"].append(case["with"]["score"])
        if case["without"] and case["without"]["score"] is not None:
            k["without"].append(case["without"]["score"])
    for s in skills.values():
        for k in s["by"].values():
            k["with"] = sum(k["with"]) / len(k["with"]) if k["with"] else None
            k["without"] = sum(k["without"]) / len(k["without"]) if k["without"] else None
    suite = raw.get("suite", {})
    plugins = suite.get("plugins") or [{}]
    return {
        "schema": RESULTS_SCHEMA,
        "run": {"startedAt": raw.get("startedAt"), "claudeVersion": raw.get("claudeVersion"),
                "durationSeconds": raw.get("durationSeconds"), "costUsd": raw.get("costUsd"),
                "partial": raw.get("partial"), "ablation": suite.get("ablation"), "tagFilters": suite.get("tagFilters"),
                "threshold": suite.get("threshold"), "plugin": {k: plugins[0].get(k) for k in ("name", "version")},
                "judgeModel": _option(command, "--judge-model") or "default (background-task model)",
                "model": _option(command, "--model") or "default",
                "command": command},
        "aggregates": raw.get("aggregates", {}),
        "skills": sorted(skills.values(), key=lambda s: s["name"]),
        "cases": cases,
    }


def _option(command: list[str], flag: str) -> str | None:
    """The value given for `flag` in a command line, as `--flag value` or `--flag=value`."""
    for i, word in enumerate(command):
        if word == flag and i + 1 < len(command):
            return command[i + 1]
        if word.startswith(flag + "="):
            return word.split("=", 1)[1]
    return None


def tokens_css(tokens: Mapping[str, Any]) -> str:
    """CSS custom properties from bh-01's tokens.json: primitives and scales on
    :root, the semantic layer per theme. Values are never typed by hand."""
    def ref(value: str) -> str:
        return re.sub(r"\{([a-z0-9-]+)\}", r"var(--bh-\1)", value)

    root, light, dark = [], [], []
    for group in ("color", "spacing", "radius", "shadow", "fontSize", "fontWeight", "lineHeight", "letterSpacing",
                  "borderWidth", "zIndex", "duration", "easing"):
        for t in (tokens.get(group) or {}).get("tokens", []):
            value = t.get("value")
            if isinstance(value, dict):
                light.append(f"--bh-{t['name']}: {ref(str(value.get('light')))};")
                dark.append(f"--bh-{t['name']}: {ref(str(value.get('dark')))};")
            elif value is not None:
                root.append(f"--bh-{t['name']}: {ref(str(value))};")
    for family, stack in ((tokens.get("type") or {}).get("families") or {}).items():
        root.append(f"--bh-font-{family}: {stack};")
    return (":root {\n  " + "\n  ".join(root) + "\n}\n"
            ":root, [data-theme='light'] {\n  color-scheme: light;\n  " + "\n  ".join(light) + "\n}\n"
            "[data-theme='dark'] {\n  color-scheme: dark;\n  " + "\n  ".join(dark) + "\n}\n"
            "@media (prefers-color-scheme: dark) {\n  :root:not([data-theme='light']) {\n    color-scheme: dark;\n    "
            + "\n    ".join(dark) + "\n  }\n}\n")


def render_html(results: Mapping[str, Any], tokens: Mapping[str, Any], template: str) -> str:
    """The page: the template with the token CSS and the results embedded."""
    data = json.dumps(results, ensure_ascii=False).replace("</", "<\\/")
    title = f"Eval run {(results.get('run') or {}).get('startedAt', '')[:16].replace('T', ' ')}"
    return (template.replace("/*TOKENS*/", tokens_css(tokens))
            .replace("__TITLE__", html.escape(title))
            .replace("__DATA__", data))


# ---- imperative shell -------------------------------------------------------------

def _read_metas(raw: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    metas = {}
    for c in raw.get("cases", []):
        prompt = PLUGIN_ROOT / c.get("dir", "") / "prompt.md"
        metas[c.get("dir", "")] = case_meta(prompt.read_text(encoding="utf-8")) if prompt.exists() else {
            "tags": [], "description": ""}
    return metas


def _collect_traces(raw: Mapping[str, Any], trace_dir: Path) -> tuple[dict[str, list[dict[str, Any]]], set[Path]]:
    """Read every kept transcript, keep a copy without the token stream, and
    return the trajectories and the sandbox directories to remove."""
    trajectories, sandboxes = {}, set()
    for c in raw.get("cases", []):
        for arm, runs in (c.get("arms") or {}).items():
            for i, r in enumerate(runs, 1):
                path = Path(r.get("tracePath") or "")
                if not path.is_file():
                    continue
                lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
                         if '"type":"stream_event"' not in ln[:40]]
                trajectories[str(path)] = trajectory(lines)
                (trace_dir / f"{c.get('name')}--{arm}-{i}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
                sandbox = path.parent.parent
                if _SANDBOX_RE.match(str(sandbox)):
                    sandboxes.add(sandbox)
    return trajectories, sandboxes


def _remove_sandbox(sandbox: Path) -> None:
    # Kept sandboxes have their modes closed; reopen for the owner before removing.
    for p in [sandbox, *sandbox.rglob("*")]:
        try:
            if not p.is_symlink():
                p.chmod(p.stat().st_mode | 0o700)
        except OSError:
            pass
    shutil.rmtree(sandbox, ignore_errors=True)


def _write_outputs(results: Mapping[str, Any], out_dir: Path) -> Path:
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    page = render_html(results, json.loads(TOKENS_FILE.read_text(encoding="utf-8")),
                       TEMPLATE_FILE.read_text(encoding="utf-8"))
    report = out_dir / "report.html"
    report.write_text(page, encoding="utf-8")
    return report


def cmd_run(passthrough: list[str]) -> int:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_dir = HERE / "results" / stamp
    (out_dir / "traces").mkdir(parents=True)
    raw_path = out_dir / "raw.json"
    command = ["claude", "plugin", "eval", ".", *passthrough, "--keep-temp", "--json", str(raw_path),
               "--output-dir", str(out_dir / "claude")]
    print(f"Running: {' '.join(command)}", file=sys.stderr)
    code = subprocess.run(command, cwd=PLUGIN_ROOT).returncode
    if not raw_path.exists():
        print("Error: claude plugin eval wrote no JSON result; nothing to report.", file=sys.stderr)
        return code or 1
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    trajectories, sandboxes = _collect_traces(raw, out_dir / "traces")
    for sandbox in sandboxes:
        _remove_sandbox(sandbox)
    report = _write_outputs(build_results(raw, _read_metas(raw), trajectories, command), out_dir)
    print(f"{out_dir / 'results.json'}\n{report}")
    return code


def cmd_render(results_path: Path, output: Path | None) -> int:
    results = json.loads(results_path.read_text(encoding="utf-8"))
    out = output or results_path.with_name("report.html")
    out.write_text(render_html(results, json.loads(TOKENS_FILE.read_text(encoding="utf-8")),
                               TEMPLATE_FILE.read_text(encoding="utf-8")), encoding="utf-8")
    print(out)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["run"]:
        return cmd_run(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="run the suite (all other options go to claude plugin eval)")
    render = sub.add_parser("render", help="rebuild report.html from a results.json")
    render.add_argument("results", type=Path)
    render.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    return cmd_render(args.results, args.output)


if __name__ == "__main__":
    sys.exit(main())
