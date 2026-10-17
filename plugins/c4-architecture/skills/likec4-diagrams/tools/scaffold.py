#!/usr/bin/env python3
"""Scaffold an orthodox-C4, federation-ready LikeC4 project.

  python3 scaffold.py <dir> [--profile P]... [--system NAME]...

Emits the folder-per-element / extend convention:
  <dir>/
    .likec4rc                shared/_spec.c4 is auto-scanned; federated splits add include ../shared
    shared/_spec.c4          the canonical vocabulary — one home
    models/landscape.c4      actors + external systems + cross-system (black-box) edges
    models/<system>/         each software system, declared in its own folder
      <system>.c4            top-level declaration (no extend)
      _relationships.c4      intra-system edges, explicit endpoints
    views/landscape.c4       estate-wide views (root = spans systems)
    views/<system>/          system-scoped context/containers/components
    dynamic_views/<system>/  per-system scenarios; cross-system/ for multi-system flows

Add a system later by rerunning with --system NAME. Idempotent: never overwrites.
Python 3.9+, stdlib only.
"""

import os
import re
import shutil
import sys

SELF_DIR = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(SELF_DIR, "..", "references")

USAGE = "usage: scaffold.py <dir> [--profile P]... [--system NAME]..."


def to_id(kebab: str) -> str:
    """internet-banking -> internetBanking"""
    return re.sub(r"-([a-z0-9])", lambda m: m.group(1).upper(), kebab).replace("-", "")


def to_title(kebab: str) -> str:
    """internet-banking -> Internet Banking"""
    return re.sub(r"(^|-)([a-z])", lambda m: (" " if m.group(1) else "") + m.group(2).upper(), kebab).replace("-", " ")


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    target = argv[0]
    profiles: list[str] = []
    systems: list[str] = []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--profile":
            if i + 1 >= len(argv):
                print("--profile needs a name", file=sys.stderr)
                return 2
            p = argv[i + 1]
            pdir = os.path.join(REF, "profiles")
            if not os.path.isfile(os.path.join(pdir, f"{p}.c4")):
                have = " ".join(sorted(f[:-3] for f in os.listdir(pdir) if f.endswith(".c4")))
                print(f"unknown profile: {p} (have: {have} )", file=sys.stderr)
                return 2
            profiles.append(p)
            i += 2
        elif a == "--system":
            if i + 1 >= len(argv):
                print("--system needs a name", file=sys.stderr)
                return 2
            systems.append(argv[i + 1])
            i += 2
        else:
            print(f"unknown arg: {a}", file=sys.stderr)
            return 2

    os.makedirs(target, exist_ok=True)

    def put(rel: str, content=None, src=None) -> None:
        dest = os.path.join(target, rel)
        if os.path.exists(dest):
            print(f"skip  {rel} (exists)")
            return
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        if src:
            shutil.copyfile(src, dest)
        else:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)
        print(f"wrote {rel}")

    basename = os.path.basename(os.path.abspath(target))
    put(".likec4rc", content='{\n  "name": "%s"\n}\n' % to_id(basename))

    put("shared/_spec.c4", src=os.path.join(REF, "canonical-spec.c4"))
    for p in profiles:
        put(f"shared/_profile-{p}.c4", src=os.path.join(REF, "profiles", f"{p}.c4"))

    put("models/landscape.c4", content="""\
// LANDSCAPE LAYER — the only place cross-system wiring lives.
// Holds: people (actors), external systems, and CROSS-SYSTEM relationships.
// Software systems themselves are declared under models/<system>/ and bubble
// up to top level automatically — do NOT redeclare them here.
//
// FEDERATION RULE (enforced by c4lint's black-box check): cross-system edges
// connect systems as BLACK BOXES (system -> system). Never target another
// system's container/component — it breaks orthodox C4 and a future split into
// per-system projects.
model {
  // customer = person 'Customer' { description 'A user of the estate' }
  // paymentGateway = externalSystem 'Payment Gateway' { description 'Third-party payments' }
  //
  // customer -> internetBanking 'manages money using'          // person -> system
  // internetBanking -> paymentGateway 'settles payments via'   // system -> external
}
""")

    put("views/landscape.c4", content="""\
// ESTATE-WIDE views (root of views/ = spans multiple systems).
// System-scoped views live in views/<system>/. Keep root views at the
// system/landscape zoom level only — never container/component detail across
// systems (won't survive federation).
views {
  view index {
    title 'System Landscape'
    include *
  }
}
""")

    put("dynamic_views/cross-system/_scenarios.c4", content="""\
// Multi-system scenarios (a flow that touches more than one software system).
// Single-system scenarios live in dynamic_views/<system>/.
// Steps stay at the system/container level; use explicit endpoints (no it/this).
views {
}
""")

    for s in systems:
        sid, title = to_id(s), to_title(s)
        put(f"models/{s}/{s}.c4", content=f"""\
// Software system: {title}. Declared top-level (no extend).
// Containers live in sibling files via `extend {sid} {{ <name> = container ... }}`;
// components one level deeper under models/{s}/<container>/ via
// `extend {sid}.<container> {{ <name> = component ... }}`.
model {{
  {sid} = softwareSystem '{title}' {{
    description 'TODO: what {title} does for its users'
  }}
}}
""")
        put(f"models/{s}/_relationships.c4", content=f"""\
// Intra-system relationships for {title} (container<->container,
// component<->component). Explicit endpoints only — no it/this, no sourceless
// `-> x`. Inter-process edges carry a nested `technology`.
model {{
  // extend {sid} {{
  //   webApp -> apiApp 'makes API calls to' {{ technology 'JSON/HTTPS' }}
  // }}
}}
""")
        put(f"views/{s}/context.c4", content=f"""\
// System Context — {title} (scoped to this one system).
views {{
  view {sid}Context of {sid} {{
    title 'System Context — {title}'
    include {sid}
    // add neighbors as they appear:  include -> {sid}, {sid} ->
  }}
}}
""")
        put(f"views/{s}/containers.c4", content=f"""\
// Containers — {title}.
views {{
  view {sid}Containers of {sid} {{
    title 'Containers — {title}'
    include *
  }}
}}
""")
        put(f"dynamic_views/{s}/_scenarios.c4", content=f"""\
// Single-system scenarios for {title}. Explicit endpoints, container-level.
views {{
}}
""")

    print(f"done: {target}")
    print(f'  validate: npx likec4 validate "{target}"  &&  python3 {SELF_DIR}/c4lint.py "{target}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
