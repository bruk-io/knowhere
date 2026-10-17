#!/usr/bin/env python3
"""Build a LikeC4 project into the three files a Claude Artifact needs.

    python3 build-artifact.py <likec4-project-dir> [-o OUTDIR] [--title TITLE] [--verify]

Runs `likec4 build --output-single-file`, then splits the single HTML into:

    OUTDIR/index.html   the page body the Artifact tool wraps (title, stylesheet link,
                        root div, module script tag) - no doctype/html/head/body
    OUTDIR/app.css      every <style> block, including the `<style rel="stylesheet">`
                        one that holds the real stylesheet
    OUTDIR/app.js       the inline module script

Why split rather than publish the single file: the Artifact validator rejects a
~3MB inline page (it misidentifies it), and supporting files are cleaner anyway.
Why escape U+FFFD: the bundle contains literal replacement characters inside JS
template strings and CSS; the Artifact tool refuses a page containing U+FFFD, so
they are rewritten as `\\uFFFD` (JS) and `\\FFFD ` (CSS), which mean the same thing.

--verify serves OUTDIR locally and loads the page in headless Chromium (whatever
Playwright has installed under $PLAYWRIGHT_BROWSERS_PATH, else `chromium` on PATH),
then asserts the LikeC4 app mounted and its stylesheet applied. Skipped with a
warning when no Chromium is found.

Prints the exact Artifact call to make on success. Exit 1 on any failure.
"""

from __future__ import annotations

import argparse
import glob
import http.server
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

PAGE = """<title>{title}</title>
<link rel="stylesheet" href="app.css">
<div id="likec4-root"></div>
<script type="module" src="app.js"></script>
"""


def build(project: Path, title: str) -> str:
    out = Path(tempfile.mkdtemp(prefix="likec4-build-"))
    cmd = [
        "npx", "--yes", "likec4", "build", "--output-single-file", "--use-hash-history",
        "--base", "./", "--title", title, "-o", str(out), str(project),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    index = out / "index.html"
    if r.returncode != 0 or not index.exists():
        sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
        sys.exit("likec4 build failed")
    return index.read_text(encoding="utf-8")


def split(html: str, outdir: Path, title: str) -> None:
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)
    scripts = re.findall(r'<script type="module"[^>]*>(.*?)</script>', html, re.S)
    if not styles or not scripts:
        sys.exit("unexpected build output: no <style> or module <script> found")
    if not re.search(r'<div id="likec4-root">', html):
        sys.exit("unexpected build output: no #likec4-root")
    css = "\n".join(styles).replace("\ufffd", "\\FFFD ")
    js = "\n".join(scripts).replace("\ufffd", "\\uFFFD")
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "app.css").write_text(css, encoding="utf-8")
    (outdir / "app.js").write_text(js, encoding="utf-8")
    (outdir / "index.html").write_text(PAGE.format(title=title), encoding="utf-8")
    for name in ("index.html", "app.css", "app.js"):
        text = (outdir / name).read_text(encoding="utf-8")
        assert "\ufffd" not in text, f"{name} still contains U+FFFD"
        if name != "index.html" and len(text) < 10_000:
            sys.exit(f"{name} is suspiciously small ({len(text)} bytes); the split missed a block")


def find_chromium() -> str | None:
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    candidates = []
    if root:
        candidates += glob.glob(f"{root}/chromium-*/chrome-linux*/chrome")
        candidates += glob.glob(f"{root}/chromium_headless_shell-*/chrome-linux*/headless_shell")
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        if p := shutil.which(name):
            candidates.append(p)
    return candidates[0] if candidates else None


def verify(outdir: Path) -> None:
    chrome = find_chromium()
    if not chrome:
        print("verify: no Chromium found; skipped", file=sys.stderr)
        return
    # Emulate the Artifact wrapper: a document shell around the page body.
    body = (outdir / "index.html").read_text(encoding="utf-8")
    probe = outdir / "_verify.html"
    # After the app mounts, record the computed font of the first rendered element:
    # the LikeC4 stylesheet sets IBM Plex Sans, so its absence means the CSS did not apply.
    sniff = (
        "<script>setTimeout(()=>{const el=document.querySelector('#likec4-root *');"
        "document.documentElement.dataset.verifyFont=el?getComputedStyle(el).fontFamily:'';"
        "document.documentElement.dataset.verifyChildren=String(document.querySelector('#likec4-root').childElementCount);"
        "},4000)</script>"
    )
    probe.write_text(
        f'<!doctype html><html><head><meta charset="utf-8"></head><body>{body}{sniff}</body></html>'
    )
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *a, **k: None  # type: ignore[assignment]
    with socketserver.TCPServer(("127.0.0.1", 0), lambda *a: handler(*a, directory=str(outdir))) as srv:
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        r = subprocess.run(
            [chrome, "--headless", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=8000",
             "--dump-dom", f"http://127.0.0.1:{port}/_verify.html"],
            capture_output=True, text=True, timeout=90,
        )
        srv.shutdown()
    probe.unlink()
    dom = r.stdout
    children = re.search(r'data-verify-children="(\d+)"', dom)
    font = re.search(r'data-verify-font="([^"]*)"', dom)
    if not children or children.group(1) == "0":
        sys.exit("verify: #likec4-root is empty; the module script did not run")
    if not font or "IBM Plex" not in font.group(1):
        sys.exit(f"verify: app mounted but the stylesheet did not apply (font={font and font.group(1)!r})")
    print("verify: LikeC4 app mounted and styled")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("-o", "--outdir", type=Path, default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    project = a.project.resolve()
    if not project.is_dir():
        sys.exit(f"not a directory: {project}")
    title = a.title or f"{project.name} C4"
    outdir = (a.outdir or project / "artifact").resolve()
    split(build(project, title), outdir, title)
    if a.verify:
        verify(outdir)
    sizes = {n: (outdir / n).stat().st_size // 1024 for n in ("index.html", "app.css", "app.js")}
    print(f"built {outdir} ({sizes['app.js']} KB js, {sizes['app.css']} KB css)")
    print("publish with the Artifact tool:")
    print(f'  file_path: {outdir / "index.html"}')
    print(f'  files: {{"app.js": "{outdir / "app.js"}", "app.css": "{outdir / "app.css"}"}}')


if __name__ == "__main__":
    main()
