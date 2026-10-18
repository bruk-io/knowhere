"""Cross-file checks: every name and path the plugin's text points at exists."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = sorted(
    p
    for p in ROOT.rglob("*")
    if p.suffix in (".md", ".json") and ".git" not in p.parts and "tests" not in p.parts
)
SKILLS = {p.parent.name for p in ROOT.glob("skills/*/SKILL.md")}
AGENTS = {p.stem for p in ROOT.glob("agents/*.md")}


def test_every_philosophy_name_resolves() -> None:
    # The changelog records names that have since been removed, so it is left out.
    named = {
        (path.relative_to(ROOT).as_posix(), name)
        for path in TEXT
        if path.name != "CHANGELOG.md"
        for name in re.findall(r"philosophy:([a-z][a-z-]*)", path.read_text())
    }
    assert {(where, name) for where, name in named if name not in SKILLS | AGENTS} == set()


def test_every_plugin_path_exists() -> None:
    pattern = r"(?:\$\{CLAUDE_PLUGIN_ROOT\}|\{plugin_root\})/([\w./-]+)"
    pointed = {
        (path.relative_to(ROOT).as_posix(), target)
        for path in TEXT
        for target in re.findall(pattern, path.read_text())
    }
    assert pointed and {(w, t) for w, t in pointed if not (ROOT / t).exists()} == set()


def test_agent_preloads_resolve() -> None:
    for path in ROOT.glob("agents/*.md"):
        front = path.read_text().split("---\n")[1]
        preloads = re.findall(r"^\s+-\s+philosophy:([\w-]+)$", front, re.M)
        assert preloads and set(preloads) <= SKILLS, path.name


def test_versions_agree() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert "## %s" % plugin["version"] in changelog


def test_no_em_or_en_dashes() -> None:
    offenders = [
        p.relative_to(ROOT).as_posix() for p in TEXT if re.search("[\\u2013\\u2014]", p.read_text())
    ]
    assert offenders == []
