#!/usr/bin/env python3
"""Regression test for component-signals.py against the polyglot fixture.
Stack: TS/JS, Python, Java, Kotlin, Swift. Detection is ast-grep (see ast-grep/).
Run after any edit to the scanner:

  python3 tools/test-signals.py

Python 3.9+, stdlib only (no jq needed).
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"
failures = 0


def report(ok: bool, label: str, detail: str = "") -> None:
    global failures
    if ok:
        print(f"PASS: {label}")
    else:
        failures += 1
        print(f"FAIL: {label}" + (f" ({detail})" if detail else ""))


proc = subprocess.run(
    [PY, os.path.join(HERE, "component-signals.py"), os.path.join(HERE, "fixtures", "polyglot")],
    capture_output=True, text=True,
)
if proc.returncode != 0:
    print(f"FAIL: scanner exited {proc.returncode}\n{proc.stdout}{proc.stderr}")
    sys.exit(1)
d = json.loads(proc.stdout)

counts = d["countsByKind"]
clusters = d["candidateClusters"]["stereotypeClusters"]
routes = {g["prefix"]: g["routes"] for g in d["candidateClusters"]["routeGroups"]}
langs = sorted({s["language"] for s in d["stereotypes"]})

report(d["scanned"]["files"] == 10, "file count", str(d["scanned"]["files"]))
report(len(d["stereotypes"]) == 14, "total stereotypes", str(len(d["stereotypes"])))
report(counts.get("http-route") == 5, "http routes (express 2 + fastapi 1 + vapor 2)", str(counts.get("http-route")))
report(counts.get("controller") == 4, "controllers (nestjs + django + kotlin-spring + vapor)", str(counts.get("controller")))
report(counts.get("service") == 2, "services (nestjs + spring/java)", str(counts.get("service")))
report(counts.get("repository") == 2, "repositories (spring-data java + kotlin)", str(counts.get("repository")))
report(counts.get("task") == 1, "celery task", str(counts.get("task")))
report(len(d["frameworks"]) == 8, "framework breadth (nestjs,express,fastapi,django,celery,spring,springdata,vapor)", str(d["frameworks"]))
report(langs == ["java", "js", "kotlin", "py", "swift", "ts"], "all five stack languages detected", str(langs))
report(any(e["file"] == "src/index.ts" for e in d["entrypoints"]), "entrypoints found", str(d["entrypoints"]))
report(d["scanned"]["truncated"] is False, "no truncation on small tree")

# candidate clusters (deterministic seeding)
report(len(clusters) == 5, "stereotype cluster count", str(len(clusters)))
report(clusters[0]["stem"] == "Order", "Order cluster is largest", clusters[0]["stem"])
report(len(clusters[0]["members"]) == 4, "Order cluster spans nestjs+spring+spring-data", str(len(clusters[0]["members"])))
inv = next((c for c in clusters if c["stem"] == "Inventory"), None)
report(bool(inv) and len(inv["members"]) == 2, "Kotlin Inventory cluster (controller + spring-data)")
report(routes.get("/invoices") == 2, "express /invoices route group", str(routes))
report(routes.get("/users") == 2, "vapor /users route group (leading slash normalized)", str(routes))

# --help exits 0 and mentions usage
p = subprocess.run([PY, os.path.join(HERE, "component-signals.py"), "--help"], capture_output=True, text=True)
report(p.returncode == 0 and "Usage" in p.stdout, "--help")

# malformed input: nonexistent dir must exit 2
p = subprocess.run([PY, os.path.join(HERE, "component-signals.py"), "/nonexistent-dir"], capture_output=True, text=True)
report(p.returncode == 2, "bad dir exits 2", str(p.returncode))

sys.exit(1 if failures else 0)
