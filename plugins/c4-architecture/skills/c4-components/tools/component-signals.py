#!/usr/bin/env python3
"""component-signals — deterministic scan of a codebase for C4 component candidates.

Detection is done by ast-grep (structural AST rules in ast-grep/rules/, each
gated by valid/invalid test cases); this script runs ast-grep, maps its matches
to C4 stereotypes, and does the clustering / route-grouping / entrypoint
aggregation. It does NOT decide what a component is — that's the skill's job.

Usage: python3 component-signals.py <dir> [--max-stereotypes N]
Output: JSON on stdout. Diagnostics on stderr. Exit 0 ok, 2 tool failure.

Rule id convention: "<c4-kind>__<framework>__<language>" (e.g.
controller__spring__java, http-route__express__js). Parsed as
[kind, framework, language] = id.split('__').

Python 3.9+, stdlib only. (ast-grep itself is a CLI dependency:
`npm i -g @ast-grep/cli`, with an npx fallback.)
"""

import json
import os
import re
import shutil
import subprocess
import sys

HELP = """component-signals — scan a codebase for C4 component candidate signals (via ast-grep)
Usage: python3 component-signals.py <dir> [--max-stereotypes N]
Output (JSON, stdout): frameworks, stereotypes (file:line evidence + language),
candidateClusters (stem-grouped stereotypes + route prefix groups),
directories, entrypoints. Diagnostics on stderr.
Detection rules live in ast-grep/; test them with ast-grep/run-tests.py.
Exit: 0 ok, 2 tool failure (bad dir / ast-grep unavailable)."""

if "--help" in sys.argv or "-h" in sys.argv:
    print(HELP)
    sys.exit(0)

args = sys.argv[1:]
root = args[0] if args and not args[0].startswith("--") else "."
MAX_STEREOTYPES = 300
if "--max-stereotypes" in args:
    MAX_STEREOTYPES = int(args[args.index("--max-stereotypes") + 1])

SELF_DIR = os.path.dirname(os.path.abspath(__file__))
SGCONFIG = os.path.join(SELF_DIR, "ast-grep", "sgconfig.yml")

if not os.path.isdir(root):
    print(f"component-signals: not a directory: {root}", file=sys.stderr)
    sys.exit(2)
if not os.path.exists(SGCONFIG):
    print(f"component-signals: ast-grep config not found at {SGCONFIG}", file=sys.stderr)
    sys.exit(2)

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "target", "out", "vendor",
    "venv", ".venv", "__pycache__", "coverage", ".next", ".nuxt",
    ".idea", ".vscode", ".gradle", ".mvn", "migrations", "Pods", ".build",
}
# Stack: TS/JS, Python, Java, Kotlin, Swift.
CODE_EXT = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".java", ".kt", ".kts", ".swift",
}
ENTRYPOINT_HINTS = [
    (re.compile(r"(^|/)(index|main|app|server|entrypoint)\.(ts|js|mjs|py|swift)$", re.I), "main"),
    (re.compile(r"Application\.(java|kt)$"), "main"),
]


# ---- detection: ast-grep -----------------------------------------------------
def ast_grep_cmd() -> str:
    if shutil.which("ast-grep"):
        return "ast-grep"
    return "npx --yes @ast-grep/cli"


def run_ast_grep():
    cmd = f'{ast_grep_cmd()} scan -c "{SGCONFIG}" --json .'
    # cwd=root + scanning '.' makes match.file paths relative to root.
    # `scan` exits non-zero when findings exist — stdout still holds the JSON.
    proc = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True)
    out = proc.stdout or ""
    if not out.strip():
        if proc.returncode != 0:
            print(
                "component-signals: ast-grep failed — install it (`npm i -g @ast-grep/cli`).\n"
                + (proc.stderr or "").strip()[-2000:],
                file=sys.stderr,
            )
            sys.exit(2)
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


stereotypes = []
frameworks_seen = set()
truncated = False

for m in run_ast_grep():
    parts = str(m.get("ruleId") or "").split("__")
    if len(parts) < 2:
        continue
    kind, framework = parts[0], parts[1]
    language = parts[2] if len(parts) > 2 else None
    if not kind or not framework:
        continue
    frameworks_seen.add(framework)
    if len(stereotypes) >= MAX_STEREOTYPES:
        truncated = True
        break
    stereotypes.append({
        "name": (m.get("text") or "").strip("'\"`"),
        "kind": kind,
        "framework": framework,
        "language": language,
        "file": m.get("file"),
        "line": ((m.get("range") or {}).get("start") or {}).get("line", 0) + 1,
    })

# Deterministic order (ast-grep match order isn't guaranteed) so clustering and
# output are stable for the same codebase — the "same code → same components" rule.
stereotypes.sort(key=lambda s: (s["file"] or "", s["line"], s["name"]))

# ---- walk (structure only: directories, entrypoints, file count) -------------
dir_stats: dict = {}
entrypoints = []
files_scanned = 0

for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
    for fn in sorted(filenames):
        if fn.startswith("."):
            continue
        rel = os.path.relpath(os.path.join(dirpath, fn), root)
        ext = os.path.splitext(rel)[1]
        if ext not in CODE_EXT:
            continue
        files_scanned += 1
        rel_posix = rel.replace(os.sep, "/")
        parts = rel_posix.split("/")
        key = "/".join(parts[: min(2, len(parts) - 1)]) or "."
        d = dir_stats.setdefault(key, {"files": 0, "langs": {}})
        d["files"] += 1
        d["langs"][ext] = d["langs"].get(ext, 0) + 1
        for rx, hint_kind in ENTRYPOINT_HINTS:
            if rx.search(rel_posix):
                entrypoints.append({"file": rel_posix, "kind": hint_kind})

# ---- summarize (aggregation) --------------------------------------------------
by_kind: dict = {}
for s in stereotypes:
    by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1

SUFFIX = re.compile(r"(Controller|Service|Repository|Facade|Handler|Manager|Provider|Component|Resource|ViewSet|Gateway|Client|Impl)$")


def stem_of(name: str) -> str:
    n = re.sub(r"^I(?=[A-Z])", "", name)
    while True:
        prev = n
        n = SUFFIX.sub("", n)
        if n == prev or len(n) <= 2:
            break
    return n or name


def cluster_key(stem: str) -> str:
    return re.sub(r"s$", "", stem.lower())


cluster_map: dict = {}
for s in stereotypes:
    if s["kind"] == "http-route":
        continue
    stem = stem_of(s["name"])
    key = cluster_key(stem)
    entry = cluster_map.setdefault(key, {"stem": stem, "members": []})
    entry["members"].append({"name": s["name"], "kind": s["kind"], "file": s["file"], "line": s["line"]})
stereotype_clusters = sorted(cluster_map.values(), key=lambda c: -len(c["members"]))

route_map: dict = {}
for s in stereotypes:
    if s["kind"] != "http-route":
        continue
    # normalize: some frameworks (Vapor) write route paths without a leading slash
    raw = s["name"] if s["name"].startswith("/") else "/" + s["name"]
    m = re.search(r"/[^\s]*", raw)
    path = m.group(0) if m else "/"
    segs = path.split("/")
    prefix = "/" + (segs[1] if len(segs) > 1 else "")
    g = route_map.setdefault(prefix, {"prefix": prefix, "routes": 0, "files": {}})
    g["routes"] += 1
    g["files"][s["file"]] = True  # ordered de-dupe
route_groups = sorted(
    ({"prefix": g["prefix"], "routes": g["routes"], "files": list(g["files"].keys())} for g in route_map.values()),
    key=lambda g: -g["routes"],
)

directories = sorted(
    (
        {
            "path": path,
            "files": d["files"],
            "mainLang": max(d["langs"].items(), key=lambda kv: kv[1])[0] if d["langs"] else None,
        }
        for path, d in dir_stats.items()
    ),
    key=lambda x: -x["files"],
)[:40]

print(json.dumps({
    "root": root,
    "scanned": {"files": files_scanned, "stereotypesFound": len(stereotypes), "truncated": truncated},
    "frameworks": sorted(frameworks_seen),
    "countsByKind": by_kind,
    "candidateClusters": {"stereotypeClusters": stereotype_clusters, "routeGroups": route_groups},
    "stereotypes": stereotypes,
    "directories": directories,
    "entrypoints": entrypoints[:20],
}, indent=2))
