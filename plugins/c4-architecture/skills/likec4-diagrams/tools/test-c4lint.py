#!/usr/bin/env python3
"""Regression test for c4lint.py + scaffold.py. Run after any edit to either
(or after a LikeC4 upgrade, to catch JSON-schema drift):

  python3 tools/test-c4lint.py

Python 3.9+, stdlib only.
"""

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"
failures = 0


def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def report(ok: bool, label: str, detail: str = "") -> None:
    global failures
    if ok:
        print(f"PASS: {label}")
    else:
        failures += 1
        print(f"FAIL: {label}")
        if detail:
            print(detail[:2000])


def c4lint(target):
    return run([PY, os.path.join(HERE, "c4lint.py"), target])


# 1. The bundled good example must be clean (exit 0, zero errors).
p = c4lint(os.path.join(HERE, "..", "examples", "internet-banking"))
report(p.returncode == 0 and "0 error(s)" in p.stdout, "good example clean",
       f"exit {p.returncode}\n{p.stdout}{p.stderr}")

# 2. The broken fixture must produce exactly the known violations (exit 1).
p = c4lint(os.path.join(HERE, "fixtures", "broken"))
errs = len(re.findall(r"^ERROR ", p.stdout, re.M))
warns = len(re.findall(r"^WARN ", p.stdout, re.M))
report(p.returncode == 1 and errs == 14 and warns == 1,
       "broken fixture caught (14 errors, 1 warning)",
       f"exit {p.returncode}, {errs} errors / {warns} warnings\n{p.stdout}")
broken_out = p.stdout

# 2b. Nested scaffold with a system + profile must produce a valid, lint-clean
#     project; bad profile exits 2.
tmpdir = tempfile.mkdtemp()
proj = os.path.join(tmpdir, "proj")
run([PY, os.path.join(HERE, "scaffold.py"), proj, "--profile", "layered", "--system", "internet-banking"])
ok = True
prof = os.path.join(proj, "shared", "_profile-layered.c4")
sys_c4 = os.path.join(proj, "models", "internet-banking", "internet-banking.c4")
ok &= os.path.isfile(prof) and "tag layered-domain" in open(prof).read()
ok &= os.path.isfile(sys_c4) and "internetBanking = softwareSystem" in open(sys_c4).read()
ok &= c4lint(proj).returncode == 0  # scaffolded project lints clean
report(ok, "nested scaffold (valid, id-derived, lint-clean)")
p = run([PY, os.path.join(HERE, "scaffold.py"), proj, "--profile", "nonsense"])
report(p.returncode == 2, "unknown profile exits 2", f"exit {p.returncode}")

# 2c. Multi-project export shape (array of project-models) must be read,
#     per-project prefixed, deduped by projectId, and aggregated.
p = c4lint(os.path.join(HERE, "fixtures", "multiproject.json"))
report(
    p.returncode == 1
    and re.search(r"\[beta\] widget: .*not a canonical C4 kind", p.stdout)
    and "3 elements" in p.stdout
    and "(2 projects)" in p.stdout,
    "multi-project array shape",
    f"exit {p.returncode}\n{p.stdout}",
)

# 2d. Black-box boundary: reaching into another software system's internals is
#     an error; a system→system edge is clean (and needs no protocol).
p = c4lint(os.path.join(HERE, "fixtures", "cross-system.json"))
report(
    p.returncode == 1
    and "alpha.api -> beta.db: reaches into another software system" in p.stdout
    and "1 error(s)" in p.stdout,  # only the reach-in; alpha→beta system edge is clean
    "black-box boundary (reach-in flagged, system→system clean)",
    f"exit {p.returncode}\n{p.stdout}",
)

# 2e. Explicit-reference house style: it/this and sourceless relationships warn.
p = c4lint(os.path.join(HERE, "fixtures", "style"))
report(
    "uses 'it'/'this'" in p.stdout and "sourceless relationship" in p.stdout,
    "explicit-style warnings (it/this + sourceless)",
    p.stdout,
)

# 3. Each rule family must fire at least once on the broken fixture.
patterns = [
    "not a canonical C4 kind",
    "is top-level — containers live inside",
    "missing description",
    "missing technology",
    "black boxes",
    "component nested in component",
    "no title",
    "inter-process relationship without technology",
    "vague title",
    "mixes abstraction levels",
    "unscoped view shows containers",
]
missing = [pat for pat in patterns if pat not in broken_out]
report(not missing, "all rule families fire", f"not firing: {missing}")

sys.exit(1 if failures else 0)
