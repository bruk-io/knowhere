"""Consistency guard: every fact has one home, and the plugin obeys its own advice.

"If you could write an assertion for it, write code" and "one source of truth"
are only claims until something fails when they stop being true. These tests
read the real plugin tree (no fixtures) and fail when:

- a prose file states a numeric limit the linter owns (`claude-lint rules`);
- a fact with one owner is restated in a second prose file, or one of the
  plugin's own two lessons is argued again outside its home;
- a rule file grows past judgement plus a pointer, or the kind -> rule file /
  skill map stops matching the tree;
- a rule file, skill or agent shows a command that cannot be run as written
  (a `<plugin>` placeholder path, or the linter by bare name);
- a SessionStart hook that prints to every session comes back;
- a description keys its trigger on a file touch, or grows past its budget;
- a version stamp, a review checklist or a second injection comes back;
- a pointer names a section that no longer exists;
- the plugin no longer lints clean, or its hooks.json no longer validates;
- a Skill(...) cross-reference or an agent's `skills:` preload points nowhere;
- a top-level bin/ comes back, or the human-facing docs still describe one;
- a relative link in the human-facing docs is dead;
- the hooks reference contradicts `hooktool events`;
- the README or CHANGELOG states a version other than plugin.json's.

Nothing here assumes a command is on PATH: the linter and hooktool are run by
path with the current interpreter, and the linter's own frontmatter parser is
loaded from that path. The plugin's name is read from plugin.json.

Run from the plugin root:  python3 -m unittest discover -s tests -v
"""

import dataclasses
import functools
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

_ROOT = Path(__file__).resolve().parent.parent
_LINT = _ROOT / "scripts" / "claude-lint"
_HOOKTOOL = _ROOT / "skills" / "authoring-hooks" / "scripts" / "hooktool.py"
_HOOKS_REFERENCE = _ROOT / "skills" / "authoring-hooks" / "references" / "hooks-reference.md"
_PLUGIN_JSON = _ROOT / ".claude-plugin" / "plugin.json"
_README = _ROOT / "README.md"
_PHILOSOPHY = _ROOT / "PHILOSOPHY.md"
_CHANGELOG = _ROOT / "CHANGELOG.md"
# The pages a person reads. They are not linted as artifacts, so they are
# checked here instead.
_LINKED_DOCS = (_README, _PHILOSOPHY, _CHANGELOG)

_loader = importlib.machinery.SourceFileLoader("claude_lint", str(_LINT.with_name("claude_lint.py")))
_spec = importlib.util.spec_from_loader("claude_lint", _loader)
assert _spec is not None
_cl: Any = importlib.util.module_from_spec(_spec)
_loader.exec_module(_cl)

_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
_QUOTE_PREFIX_RE = re.compile(r"^\s*>\s?")
_SOLO_BLOCK_RE = re.compile(r"^(?:#{1,6}\s|\|)")           # a heading or a table row stands alone
_ITEM_RE = re.compile(r"^(?:[-*+]\s|\d+[.)]\s)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*$")
_BOLD_RE = re.compile(r"\*\*([^*\n]+)\*\*")
_SKILL_REF_RE = re.compile(r"\bSkill\(([^)]*)\)")
_MD_LINK_RE = re.compile(r"\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?[^)]*\)")
_CODE_SPAN_RE = re.compile(r"`[^`\n]*`")

# ---- limits the linter owns ------------------------------------------------

# The words that turn a bare number into a statement of each limit. A number
# with none of them beside it ("exit 2", "200 OK", "2.1.200") is not a limit.
_LIMIT_UNITS: Mapping[str, str] = {
    "DESC_CAP": r"char(?:acter)?s?",
    "SKILL_BODY_MAX_LINES": r"lines?",
    "RULE_MAX_LINES": r"lines?",
    "MEMORY_MAX_LINES": r"lines?",
    "IMPORT_MAX_HOPS": r"hops?",
    "AGENT_NAME_MAX": r"char(?:acter)?s?",
    "AGENT_SKILLS_MAX": r"(?:skills?|names?|preloads?)",
    "PATHS_EXPANSION_MAX": r"(?:expanded\s+)?patterns?",
}
_NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
                 "nine", "ten", "eleven", "twelve")
_CAP_WORDS = (r"(?:cap(?:ped)?|limit(?:ed)?|max(?:imum)?|at most|up to|under|over|exceed\w*"
              r"|truncat\w*)")
_LIMIT_FIX = "delete it; `claude-lint rules` states this limit and why"

# ---- the design that 0.4.0 removed -----------------------------------------

_STAMP_COMMAND_RE = re.compile(r"claude-lint\"?\s+stamp\b")
_WRITTEN_FOR_RE = re.compile(r"Written for\s+Claude Code\s+v?\d", re.I)
_REVIEW_CHECKLIST_RE = re.compile(r"^#{1,6}\s.*\breview checklist\b", re.I)
_TASK_PER_ITEM_RE = re.compile(r"TaskCreate\W{0,4}task\s+per\s+item", re.I)

_INLINE_DIRECTIVE_RE = re.compile(r"(?:^|(?<=\s))!`([^`\n]*)`")
_FENCED_DIRECTIVE_RE = re.compile(r"^\s{0,3}(?:`{3,}|~{3,})!")
_ARGUMENTS_RE = re.compile(r"\$ARGUMENTS\b")
_SELF_DOC_RE = re.compile(r"\bhooktool(?:\.py)?\b.*\bclaudemd\b")
_SELF_DOC_SKILL = "authoring-hooks"
_ALLOWED_TOOLS_KEYS = frozenset({"allowed-tools", "allowed_tools", "allowedTools"})

_RULE_BODY_MAX_LINES = 12
_RULE_OPENING = "Applies when reading or editing"

# ---- commands that cannot be run as written ----------------------------------

# A path that starts at a placeholder for the plugin's directory. `[<plugin>]`
# as a label and `<plugin>:<name>` as a name are not paths.
_PLACEHOLDER_PATH_RE = re.compile(r"<plugin(?:[ _-]?(?:root|dir(?:ectory)?))?>/", re.I)
# The linter by bare name with a subcommand after it, as in `claude-lint rules`.
# By path it follows a slash (`.../scripts/claude-lint" rules`), and as a name
# it stands alone (`claude-lint`), so neither is matched.
_LINT_SUBCOMMANDS = ("rules", "fields", "check-injection", "drift", "classify", "hook",
                     "install-rules")
_BARE_LINT_COMMAND_RE = re.compile(
    r"(?<![\w/.\\-])claude-lint\s+(?:--all\b|(?:" + "|".join(_LINT_SUBCOMMANDS) + r")(?![\w-]))")
_CODE_SPAN_BODY_RE = re.compile(r"`([^`\n]+)`")

# ---- the plugin's own hooks ---------------------------------------------------

_HOOKS_JSON = _ROOT / "hooks" / "hooks.json"
_LITMUS_SCRIPT = _ROOT / "hooks" / "seam-punchline.sh"
_RESET_SCRIPT = "reset-rule-delivery.sh"
_DESCRIPTION_MAX_CHARS = 600
_FILE_KEYED_TRIGGER_RULES = ("SK016", "AG007")

# ---- sections that other files point at ------------------------------------

_OWNER_HEADINGS: tuple[tuple[str, str], ...] = (
    ("skills/authoring-rules/SKILL.md", "Loading and scope"),
    ("skills/authoring-memory/SKILL.md", "AGENTS.md interop"),
    ("skills/authoring-hooks/references/hooks-reference.md", "What reaches Claude"),
    ("skills/authoring-hooks/references/hooks-reference.md", "Hooks in skills and agents"),
    ("skills/authoring-hooks/references/hooks-reference.md", "Hooks in a plugin"),
    ("skills/choosing-extension-types/references/minimizing-model-work.md", "Two axes, not a ladder"),
    ("skills/choosing-extension-types/references/minimizing-model-work.md",
     "Before writing a prose rule - ask if it's a linter"),
    ("skills/choosing-extension-types/references/minimizing-model-work.md",
     "The seam - within a model-facing body, code vs prose"),
    ("skills/choosing-extension-types/references/minimizing-model-work.md",
     "Anti-patterns - context where code belongs"),
    ("skills/choosing-extension-types/references/minimizing-model-work.md",
     "Designing tools the model calls"),
)
_QUOTED_RE = re.compile(r'"([^"\n]{3,90})"')
# After "see" or "under", an italic or backticked name of several words.
_EMPHASISED_POINTER_RE = re.compile(
    r"\b(?:see|under)\s+(?:the\s+)?[*`]([A-Z][^*`\s]*\s[^*`\n]{2,80})[*`]")
_CUE_BEFORE_RE = re.compile(r"\b(?:see|under|section|skill's|reference's)\s+(?:the\s+)?$", re.I)
_CUE_AFTER_RE = re.compile(
    r"\s+(?:section\b|in\s+(?:the|its|this|that|Skill\(|\[|`|authoring-|api-))")
_SENTENCE_BREAK_RE = re.compile(r"[.;!?](?:\s|$)")
_HERE_RE = re.compile(r"^\W{0,3}(?:below|above)\b")
_POINTERS_JUDGED_MIN = 15

# ---- facts with one owner ---------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class _Fact:
    """A fact that one file states and every other file points at.

    `allowed` maps a path to the most paragraphs in it that may state the fact
    (None for no cap); a path in `home` must state it at least once, so a
    pattern that has drifted from the prose fails instead of passing empty.
    """

    name: str
    pattern: re.Pattern[str]
    allowed: Mapping[str, int | None]
    home: tuple[str, ...]
    owner: str


_RULES_SKILL = "skills/authoring-rules/SKILL.md"
_FOUNDATIONS_SKILL = "skills/choosing-extension-types/SKILL.md"
_MEMORY_SKILL = "skills/authoring-memory/SKILL.md"
_SKILLS_SKILL = "skills/authoring-skills/SKILL.md"
_AGENTS_SKILL = "skills/authoring-agents/SKILL.md"
_HOOKS_REFERENCE_REL = "skills/authoring-hooks/references/hooks-reference.md"
_MODEL_WORK_REFERENCE = "skills/choosing-extension-types/references/minimizing-model-work.md"
_AUDITOR = "agents/authoring-auditor.md"

# The plugin's two lessons are facts too: each is argued in one file, and the
# files listed beside it keep one sentence.
_INTENT = r"(?:\bmatch(?:es)?\s+intent\b|\b(?:carr(?:y|ies)|keeps?)\s+(?:only\s+)?intent\b|\bintent\s+only\b)"
_DESCRIPTION = r"\bdescriptions?\b"

_SINGLE_OWNER_FACTS: tuple[_Fact, ...] = (
    _Fact(
        name="a path-scoped rule loads on Read, Write or Edit",
        pattern=re.compile(
            r"\brules?\b(?:(?!\bhooks?\b)[^.]){0,160}?"
            r"(?:`?\bRead`?,\s+`?Write`?,?\s+(?:and\s+|or\s+)?`?Edit\b"
            r"|\breads?,\s+writes?,?\s+(?:and|or)\s+edits?\b)", re.I),
        allowed={_RULES_SKILL: 1, _FOUNDATIONS_SKILL: 1},
        home=(_RULES_SKILL,),
        owner=f'"Loading and scope" in {_RULES_SKILL}, once (the loading table in '
              f"{_FOUNDATIONS_SKILL} may summarise it once)"),
    _Fact(
        name="claude.ai and Cowork do not install a plugin that has bin/",
        pattern=re.compile(
            r"claude\.ai\b.{0,40}\bCowork\b(?=.{0,240}\bbin/)"
            r"|\bbin/.{0,240}?claude\.ai\b.{0,40}\bCowork\b", re.I),
        allowed={_SKILLS_SKILL: None, "README.md": None},
        home=("README.md",),
        owner=f"README.md and {_SKILLS_SKILL} (the linter states the reason: PL007)"),
    _Fact(
        name="the list of frontmatter fields a plugin agent ignores",
        pattern=re.compile(
            r"^(?=.*\bplugin)(?=.*\bignor)(?=.*\bmcpServers\b)(?=.*\bpermissionMode\b)"
            r"(?=.*\binitialPrompt\b)", re.I),
        allowed={},
        home=(),
        owner="no prose file: `claude-lint fields agent` marks the fields and AG005 flags them"),
    _Fact(
        name="a subagent's Stop hook becomes SubagentStop",
        pattern=re.compile(
            r"`?\bStop\b`?[^.]{0,60}\b(?:convert|becom|turn|rewrit|renam|map|translat|treat)\w*"
            r"[^.]{0,40}`?SubagentStop\b"),
        allowed={_HOOKS_REFERENCE_REL: None},
        home=(_HOOKS_REFERENCE_REL,),
        owner=f'"Hooks in skills and agents" in {_HOOKS_REFERENCE_REL}'),
    _Fact(
        name="AGENTS.md is read only when no CLAUDE.md exists",
        pattern=re.compile(
            r"AGENTS\.md.{0,200}?\b(?:only|stand-in)\b.{0,120}?"
            r"\b(?:no|without|absent|lacks?|isn't|is not)\b.{0,60}?CLAUDE(?:\.local)?\.md"
            r"|\b(?:no|without)\b.{0,30}CLAUDE(?:\.local)?\.md.{0,120}?"
            r"\b(?:reads?|loads?|falls? back)\b.{0,60}?AGENTS\.md", re.I),
        allowed={_MEMORY_SKILL: None, _FOUNDATIONS_SKILL: 1},
        home=(_MEMORY_SKILL,),
        owner=f'"AGENTS.md interop" in {_MEMORY_SKILL} (the linter states it too: CM004)'),
    _Fact(
        name="a forked guideline returns nothing useful",
        pattern=re.compile(
            r"\b(?:guideline|conventions|reference knowledge)\b[^.]{0,120}"
            r"\b(?:nothing useful|nothing to do|no actionable)\b", re.I),
        allowed={_SKILLS_SKILL: 1, "rules/skill-invariants.md": 1},
        home=(_SKILLS_SKILL,),
        owner=f'the `context: fork` bullet in {_SKILLS_SKILL} (one clause in rules/skill-invariants.md)'),
    _Fact(
        name="a forked skill cannot see the conversation",
        pattern=re.compile(r"\bfork\b[^.]{0,40}\bcannot (?:see|apply)\b[^.]{0,60}\bconversation\b", re.I),
        allowed={_SKILLS_SKILL: 1},
        home=(_SKILLS_SKILL,),
        owner=f"the `context: fork` bullet in {_SKILLS_SKILL} (the tool's skill notes say how to fork with history)"),
    _Fact(
        name="lesson 1: a description matches intent, file-keyed delivery is a rule's or a "
             "hook's",
        pattern=re.compile(
            rf"{_DESCRIPTION}.{{0,160}}?{_INTENT}|{_INTENT}.{{0,160}}?{_DESCRIPTION}", re.I),
        allowed={_FOUNDATIONS_SKILL: None, _SKILLS_SKILL: 1, _AGENTS_SKILL: 1,
                 "rules/skill-invariants.md": 1, "rules/subagent-invariants.md": 1, _AUDITOR: 1,
                 "README.md": 1, "PHILOSOPHY.md": 1},
        home=(_FOUNDATIONS_SKILL,),
        owner=f'"Loading semantics" in {_FOUNDATIONS_SKILL} (one sentence each in the skills '
              f"and agents skills' `description` bullets, the two rule files, the auditor, "
              f"README.md and PHILOSOPHY.md)"),
    _Fact(
        name="lesson 2: a bullet a program could check is a lint rule",
        pattern=re.compile(r"\b(?:program|linter)\s+(?:could|can)\s+(?:check|assert)\b", re.I),
        allowed={_MODEL_WORK_REFERENCE: None, _FOUNDATIONS_SKILL: 1, _RULES_SKILL: 1,
                 _MEMORY_SKILL: 1, "rules/rule-invariants.md": 1, _AUDITOR: 1,
                 "README.md": 1, "PHILOSOPHY.md": 1},
        home=(_MODEL_WORK_REFERENCE,),
        owner=f'"Before writing a prose rule - ask if it\'s a linter" in {_MODEL_WORK_REFERENCE} '
              f"(one line each in choosing-extension-types' anti-patterns, authoring-rules' body "
              f"conventions, authoring-memory, rules/rule-invariants.md, the auditor, README.md "
              f"and PHILOSOPHY.md)"),
)

# ---- human-facing docs ------------------------------------------------------

_BIN_PATH_RE = re.compile(r"(?<![\w/.$-])bin/")           # not /usr/bin/, /bin/sh
_BIN_ABSENT_RE = re.compile(
    r"\bno\b|\bnot\b|n't\b|\bnever\b|\bwithout\b|\bmoved\b|\binstead of\b", re.I)
_BIN_DOCS_REASON = ('the plugin docs say of bin/: "claude.ai and Cowork don\'t install a '
                    'plugin that has this directory"')
_OLD_NAME = "claude-authoring"
_OLD_NAME_CONTEXT_RE = re.compile(r"upgrading|renamed|formerly", re.I)

_EVENT_TOKEN_RE = re.compile(r"`([A-Z][A-Za-z]+)`")
_CONFIG_KEY_RE = re.compile(r'"([A-Z][A-Za-z]+)"\s*:\s*\[')
_CAMEL_PIECE_RE = re.compile(r"[A-Z][a-z]+")
_COUNT = r"(\d+|" + "|".join(_NUMBER_WORDS) + r")"
_ALL_EVENTS_COUNT_RE = re.compile(r"\ball\s+" + _COUNT + r"\s+(?:hook\s+)?events\b", re.I)
_COLUMN_COUNT_RE = re.compile(
    r"\b" + _COUNT + r"\s+events\s+`hooktool events`\s+marks\s+([A-Z][A-Z>-]+)", re.I)
_EVENT_COLUMNS: Mapping[str, str] = {"STDOUT->CTX": "inject", "ADDL-CONTEXT": "context"}
# Backticked names in the hooks reference that are built from event words but
# are something else (a tool, say). Empty until one turns up.
_NOT_EVENTS: frozenset[str] = frozenset()


# ---- reading the tree (the only I/O) ---------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(_ROOT).as_posix()


def _md(*patterns: str) -> tuple[Path, ...]:
    return tuple(sorted({p for pattern in patterns for p in _ROOT.glob(pattern)}))


def _skill_files() -> tuple[Path, ...]:
    return _md("skills/*/SKILL.md")


def _model_facing() -> tuple[Path, ...]:
    return _md("skills/**/*.md", "rules/*.md", "agents/*.md")


def _prose() -> tuple[Path, ...]:
    """Every file that states how things are today. CHANGELOG is history."""
    return _model_facing() + _md("tools/claude-lint/*.md") + (_README, _PHILOSOPHY)


def _human_docs() -> tuple[Path, ...]:
    return tuple(p for p in _LINKED_DOCS if p.exists()) + _md("tools/claude-lint/*.md")


def _skill_names() -> frozenset[str]:
    return frozenset(p.parent.name for p in _skill_files())


def _plugin() -> Mapping[str, Any]:
    manifest: Mapping[str, Any] = json.loads(_read(_PLUGIN_JSON))
    return manifest


def _run(*argv: str | Path) -> "subprocess.CompletedProcess[str]":
    return subprocess.run([sys.executable, *map(str, argv)], capture_output=True, text=True,
                          cwd=_ROOT, check=False)


@functools.cache
def _rules_table() -> Mapping[str, Any]:
    done = _run(_LINT, "rules", "--json")
    if done.returncode != 0:
        raise AssertionError(f"claude-lint rules --json failed: {done.stderr}")
    table: Mapping[str, Any] = json.loads(done.stdout)
    return table


@functools.cache
def _lint_report() -> Mapping[str, Any]:
    done = _run(_LINT, "--all", _ROOT, "--json")
    if done.returncode not in (0, 1) or not done.stdout.strip():
        raise AssertionError(f"claude-lint --all --json failed: {done.stderr}")
    report: Mapping[str, Any] = json.loads(done.stdout)
    return report


@functools.cache
def _hook_events() -> tuple[Mapping[str, Any], ...]:
    done = _run(_HOOKTOOL, "events", "--json")
    if done.returncode != 0:
        raise AssertionError(f"hooktool events --json failed: {done.stderr}")
    return tuple(json.loads(done.stdout))


# ---- pure helpers: text in, findings out -----------------------------------

@dataclasses.dataclass(frozen=True, slots=True)
class _Paragraph:
    """Source lines that read as one sentence run, joined with single spaces."""

    text: str
    starts: tuple[tuple[int, int], ...]    # (offset into text, 1-based source line)
    fenced: bool


def _paragraph(lines: Iterable[tuple[int, str]], *, fenced: bool = False) -> _Paragraph:
    starts, parts, offset = [], [], 0
    for n, line in lines:
        starts.append((offset, n))
        parts.append(line)
        offset += len(line) + 1
    return _Paragraph(" ".join(parts), tuple(starts), fenced)


def _paragraphs(text: str, first_line: int = 1) -> Iterator[_Paragraph]:
    """Split markdown into paragraphs, so a pattern can match across a wrap.

    A heading, a table row and each line inside a code fence stand alone; a
    list item starts a new paragraph; a blockquote marker is dropped.
    """
    block: list[tuple[int, str]] = []
    fence = ""
    for n, raw in enumerate(text.splitlines(), first_line):
        mark = _FENCE_RE.match(raw)
        if fence or mark:
            if block:
                yield _paragraph(block)
                block = []
            if not fence and mark:
                fence = mark.group(1)
            elif mark and mark.group(1).startswith(fence) and not mark.group(2).strip():
                fence = ""
            else:
                yield _paragraph([(n, raw.strip())], fenced=True)
            continue
        line = _QUOTE_PREFIX_RE.sub("", raw).strip()
        if block and (not line or _SOLO_BLOCK_RE.match(line) or _ITEM_RE.match(line)):
            yield _paragraph(block)
            block = []
        if _SOLO_BLOCK_RE.match(line):
            yield _paragraph([(n, line)])
        elif line:
            block.append((n, line))
    if block:
        yield _paragraph(block)


def _line_at(paragraph: _Paragraph, offset: int) -> int:
    return max(n for start, n in paragraph.starts if start <= offset)


def _number_forms(value: int, *, words: bool = True) -> str:
    forms = [str(value)]
    if value >= 1000:
        forms.append(f"{value:,}")
    if words and value < len(_NUMBER_WORDS):
        forms.append(_NUMBER_WORDS[value])
    return "(?:" + "|".join(forms) + ")"


def _limit_patterns(value: int, unit: str) -> tuple[re.Pattern[str], ...]:
    """What stating this limit looks like: the number with its unit ("500
    lines", "four hops", "1,536 listing characters"), or - for a number big
    enough to be distinctive - the number after a capping word."""
    number = _number_forms(value)
    with_unit = rf"(?<![\w.,$/-]){number}(?:[ -][\w@`]+)?[ -]{unit}\b"
    if value < 100:
        return (re.compile(with_unit, re.I),)
    capped = rf"\b{_CAP_WORDS}\b(?:\W+\w+){{0,3}}?\W+~?{number}(?![\w,]|\.\d)"
    return (re.compile(with_unit, re.I), re.compile(capped, re.I))


def _limit_statements(text: str, limits: Mapping[str, int]) -> Iterator[tuple[int, str, str]]:
    """Yield (line, the words that state it, limit key), once per statement."""
    for paragraph in _paragraphs(text):
        seen: set[int] = set()
        for key, value in limits.items():
            for pattern in _limit_patterns(value, _LIMIT_UNITS[key]):
                for m in pattern.finditer(paragraph.text):
                    if m.start() not in seen:      # two limits can share a number and a unit
                        seen.add(m.start())
                        yield _line_at(paragraph, m.start()), m.group(0), key


def _bare_limit_numbers(text: str, limits: Mapping[str, int]) -> Iterator[tuple[int, str]]:
    """A rule file is short enough to forbid the number itself, unit or not."""
    distinctive = sorted({v for v in limits.values() if v >= 10})
    numbers = "|".join(_number_forms(v, words=False) for v in distinctive)
    pattern = re.compile(rf"(?<![\w.,$/-])(?:{numbers})(?![\w,]|\.\d)")
    for n, line in enumerate(text.splitlines(), 1):
        for m in pattern.finditer(line):
            yield n, m.group(0)


def _normalise(name: str) -> str:
    return " ".join(re.sub(r"[*_`]", "", name).split()).strip(" .:").casefold()


def _anchors(text: str) -> frozenset[str]:
    """What a pointer can land on: headings, and the bold lead-in of a bullet."""
    found = set()
    for paragraph in _paragraphs(text):
        if paragraph.fenced:
            continue
        heading = _HEADING_RE.match(paragraph.text)
        if heading:
            found.add(_normalise(heading.group(1)))
        found.update(_normalise(m.group(1)) for m in _BOLD_RE.finditer(paragraph.text))
    return frozenset(found)


def _lands(section: str, anchors: frozenset[str]) -> bool:
    """A pointer may shorten "The seam - within a body" to "The seam"."""
    wanted = _normalise(section)
    return any(a == wanted or a.startswith(wanted + " - ") for a in anchors)


def _cued_by_name(before: str, names: re.Pattern[str]) -> bool:
    """A file or skill name just before the quote, in the same sentence."""
    return any(len(before) - m.end() <= 45 and not _SENTENCE_BREAK_RE.search(before[m.end():])
               for m in names.finditer(before))


@dataclasses.dataclass(frozen=True, slots=True)
class _Pointer:
    line: int
    section: str
    targets: frozenset[str]     # the names the prose gives for where the section is
    here: bool                  # "below" / "above": the section is in the same file


def _pointers(body: str, first_line: int, names: re.Pattern[str]) -> Iterator[_Pointer]:
    """Find `see "Section" in <file>`-shaped pointers in a markdown body.

    A quoted string counts when a cue sits beside it: "see", "under", "section",
    "skill's" before it; "section" or "in the/its/[..." after it; or a file or
    skill name just before it. Italic and backticked names count after "see" or
    "under". A section named without quotes is not seen at all.
    """
    for paragraph in _paragraphs(body, first_line):
        if paragraph.fenced:
            continue
        text = paragraph.text
        spans = [(m.start(1), m.end(1), m.group(1), True) for m in _QUOTED_RE.finditer(text)]
        spans += [(m.start(1), m.end(1), m.group(1), False)
                  for m in _EMPHASISED_POINTER_RE.finditer(text)]
        for start, end, section, needs_cue in spans:
            before, after = text[max(0, start - 90):start - 1], text[end + 1:end + 110]
            if needs_cue and not (_CUE_BEFORE_RE.search(before) or _CUE_AFTER_RE.match(after)
                                  or _cued_by_name(before, names)):
                continue
            near = {m.group(0) for m in names.finditer(before + " " + after)}
            targets = near or {m.group(0) for m in names.finditer(text)}
            yield _Pointer(_line_at(paragraph, start), section, frozenset(targets),
                           bool(_HERE_RE.match(after)))


def _pointer_names(here: Path, files: Iterable[Path]) -> Mapping[str, frozenset[Path]]:
    """The names prose uses for a file, as seen from `here`."""
    names: dict[str, set[Path]] = {}
    for path in files:
        if path.name == "SKILL.md":
            names.setdefault(path.parent.name, set()).add(path)
        elif path.parent.name == "references":
            names.setdefault(path.name, set()).add(path)
            if "-" in path.stem:
                names.setdefault(path.stem, set()).add(path)
                names.setdefault(path.stem.replace("-", " "), set()).add(path)
            if here == path.parent.parent / "SKILL.md":
                names.setdefault("the reference", set()).add(path)
            if here.parent == path.parent and path.parent.parent / "SKILL.md" in files:
                names.setdefault("SKILL.md", set()).add(path.parent.parent / "SKILL.md")
    return {name: frozenset(paths) for name, paths in names.items()}


def _names_pattern(names: Iterable[str]) -> re.Pattern[str]:
    longest_first = sorted(names, key=len, reverse=True)
    return re.compile(r"(?<![\w-])(?:" + "|".join(map(re.escape, longest_first)) + r")(?![\w-])")


def _fact_lines(text: str, fact: _Fact) -> tuple[int, ...]:
    """The first line of each paragraph that states the fact."""
    return tuple(_line_at(p, m.start()) for p in _paragraphs(text)
                 for m in (fact.pattern.search(p.text),) if m)


def _bare_lint_commands(body: str, first_line: int) -> Iterator[tuple[int, str]]:
    """Yield (line, code) for each code span or fenced line that runs the
    linter by bare name. Prose outside code is not a command."""
    for paragraph in _paragraphs(body, first_line):
        if paragraph.fenced:
            codes = [(paragraph.starts[0][1], paragraph.text)]
        else:
            codes = [(_line_at(paragraph, m.start()), m.group(1))
                     for m in _CODE_SPAN_BODY_RE.finditer(paragraph.text)]
        for n, code in codes:
            if _BARE_LINT_COMMAND_RE.search(code):
                yield n, code.strip()


def _camel_pieces(name: str) -> tuple[str, ...]:
    return tuple(_CAMEL_PIECE_RE.findall(name))


def _to_int(text: str) -> int:
    text = text.lower()
    return _NUMBER_WORDS.index(text) if text in _NUMBER_WORDS else int(text)


# ---- the tests --------------------------------------------------------------

class _Case(unittest.TestCase):
    def assert_none(self, problems: Iterable[str], also: str = "") -> None:
        found = list(problems)
        self.assertEqual(found, [], "\n" + "\n".join(found) + also)


class NoProseStatesALintOwnedLimit(_Case):
    """`claude-lint rules` is the one place a numeric limit is written down."""

    def test_every_limit_has_its_unit_words(self) -> None:
        limits = _rules_table()["limits"]
        self.assertEqual(
            set(_LIMIT_UNITS), set(limits),
            "tests/test_consistency.py: _LIMIT_UNITS must name the unit words for exactly the "
            "limits `claude-lint rules --json` lists, or a new limit goes unguarded")

    def test_no_prose_file_states_a_limit(self) -> None:
        limits = _rules_table()["limits"]
        self.assert_none(
            f'{_rel(path)}:{n}: states "{said}" ({key}) - {_LIMIT_FIX}'
            for path in _prose()
            for n, said, key in _limit_statements(_read(path), limits))

    def test_the_scan_sees_a_limit_and_ignores_other_numbers(self) -> None:
        limits = _rules_table()["limits"]
        stated = ("Keep the body under 500 lines.", "truncated at 1,536 characters",
                  "a 200-line file", "imports nest four hops deep", "at most 4 `@import` hops",
                  "the cap is 1536", "only the first 32 names are preloaded",
                  "within 1,000 expanded patterns", "wrapped: at most 500\nlines in a body")
        for text in stated:
            with self.subTest(states=text):
                self.assertTrue(list(_limit_statements(text, limits)))
        unrelated = ("exit 2 blocks", "returns 200 OK", "Claude Code 2.1.200", "the four cases",
                     "4. **Validate before installing**", "about 500 ms", "the first 20 lines",
                     "capped at 10,000 characters", "skips a file over 4 MiB", "v0.4.0", "$200",
                     "differences 1, 3, 4")
        for text in unrelated:
            with self.subTest(ignores=text):
                self.assertEqual(list(_limit_statements(text, limits)), [])


class TheRemovedDesignStaysRemoved(_Case):
    """Version stamps, review checklists and their shared TaskCreate sentence
    went in 0.4.0: `claude-lint drift` and the lint rules replaced them."""

    def test_no_version_stamp_or_review_checklist_in_a_skill(self) -> None:
        problems = []
        for path in _skill_files():
            for n, line in enumerate(_read(path).splitlines(), 1):
                where = f"{_rel(path)}:{n}"
                if _STAMP_COMMAND_RE.search(line):
                    problems.append(f"{where}: runs `claude-lint stamp`, which no longer exists - "
                                    f"delete the line; `claude-lint drift` reports staleness")
                if _WRITTEN_FOR_RE.search(line):
                    problems.append(f"{where}: a 'Written for Claude Code vX' stamp - delete it; "
                                    f"`claude-lint drift` compares the tables with the build")
                if _REVIEW_CHECKLIST_RE.match(line):
                    problems.append(f"{where}: a review checklist heading - delete the section; "
                                    f"what a program can check is a lint rule, and the judgement "
                                    f"belongs in the body or the auditor")
        self.assert_none(problems)

    def test_no_taskcreate_per_item_instruction(self) -> None:
        self.assert_none(
            f"{_rel(path)}:{_line_at(p, m.start())}: asks for a TaskCreate task per item - "
            f"delete it; the review checklists it served are gone"
            for path in _model_facing()
            for p in _paragraphs(_read(path))
            for m in _TASK_PER_ITEM_RE.finditer(p.text))


class SkillBodiesRunOnlyOneInjection(_Case):
    """A SKILL.md body is a template: a directive in it runs at load, code
    spans included, and needs an `allowed-tools` entry that makes every
    model-initiated load of the skill ask first. The plugin keeps one."""

    def directives(self) -> Iterator[tuple[Path, int, str]]:
        for path in _skill_files():
            fm = _cl.parse_frontmatter(_read(path))
            for n, line in enumerate(fm.body.splitlines(), fm.body_line):
                for m in _INLINE_DIRECTIVE_RE.finditer(line):
                    yield path, n, m.group(1)
                if _FENCED_DIRECTIVE_RE.match(line):
                    yield path, n, "(fenced block)"

    def test_the_only_injection_is_hooktools_self_documentation(self) -> None:
        intended = []
        problems = []
        for path, n, command in self.directives():
            if path.parent.name == _SELF_DOC_SKILL and _SELF_DOC_RE.search(command):
                intended.append((path, n, command))
            else:
                problems.append(f"{_rel(path)}:{n}: unexpected injection `{command}` - the only "
                                f"one intended is the hooktool claudemd line in "
                                f"skills/{_SELF_DOC_SKILL}; "
                                f"move a literal example to a references/ file, and point at a "
                                f"command instead of injecting its output")
        self.assert_none(problems)
        self.assertEqual(len(intended), 1,
                         f"skills/{_SELF_DOC_SKILL}/SKILL.md: expected exactly one hooktool "
                         f"claudemd injection, found {len(intended)}")

    def test_the_only_allowed_tools_entry_covers_that_injection(self) -> None:
        holders = []
        for path in _skill_files() + _md("agents/*.md"):
            fm = _cl.parse_frontmatter(_read(path))
            holders += [(path, key, fm) for key in fm.data if key in _ALLOWED_TOOLS_KEYS]
        expected = f"skills/{_SELF_DOC_SKILL}/SKILL.md"
        self.assert_none(
            f"{_rel(path)}:{fm.lines.get(key, 1)}: `{key}` in frontmatter - remove it; a skill "
            f"that carries it shows a \"Use skill?\" prompt on every model-initiated load, and "
            f"only {expected} has an injection to pre-approve"
            for path, key, fm in holders if _rel(path) != expected)
        self.assertEqual([_rel(path) for path, _, _ in holders], [expected],
                         f"{expected}: must carry the one `allowed-tools` entry, for its injection")
        (_, key, fm), = holders
        (_, n, command), = [d for d in self.directives() if _rel(d[0]) == expected]
        where = f"{expected}:{n}"
        covered = _run(_LINT, "check-injection", command, "--allowed-tools", str(fm.get(key)),
                       "--plugin-skill")
        self.assertEqual(covered.returncode, 0,
                         f"{where}: the injection is not covered by `{key}`, so the skill would "
                         f"fail to load:\n{covered.stdout}")
        bare = _run(_LINT, "check-injection", command, "--plugin-skill")
        self.assertEqual(bare.returncode, 1,
                         f"{where}: the injection loads without `{key}` - remove the entry, "
                         f"it only costs a prompt")

    def test_no_literal_argument_placeholder(self) -> None:
        # A skill that declares `argument-hint` takes arguments on purpose, and
        # the placeholder is how its body receives them. Anywhere else a
        # literal one is an example that would be substituted.
        problems = []
        for path in _skill_files():
            fm = _cl.parse_frontmatter(_read(path))
            if "argument-hint" in fm.data:
                continue
            problems += [f"{_rel(path)}:{n}: literal $ARGUMENTS in a preprocessed body - move the "
                         f"example to a references/ file"
                         for n, line in enumerate(fm.body.splitlines(), fm.body_line)
                         if _ARGUMENTS_RE.search(line)]
        self.assert_none(problems)


class RuleFilesHoldJudgementAndAPointer(_Case):
    """A rule file is delivered on first touch of its kind, so every line is
    paid for by every session that touches one: a few bullets of judgement,
    the skill that has the procedure, and one line handing the rest to the
    linter."""

    def setUp(self) -> None:
        self.kinds: Mapping[str, Mapping[str, str | None]] = _rules_table()["kinds"]
        self.rule_files = _md("rules/*.md")
        self.assertTrue(self.rule_files, "no rules/*.md; the checks would pass vacuously")

    def test_kinds_map_matches_the_tree(self) -> None:
        problems = []
        for kind, entry in self.kinds.items():
            rule, skill = entry["rule"], entry["skill"]
            if rule is not None and not (_ROOT / rule).is_file():
                problems.append(f"scripts/claude-lint: kind '{kind}' maps to {rule}, which does "
                                f"not exist - fix KINDS or restore the file")
            if skill is not None and skill not in _skill_names():
                problems.append(f"scripts/claude-lint: kind '{kind}' maps to skill '{skill}', "
                                f"which has no skills/{skill}/SKILL.md")
        mapped = {entry["rule"] for entry in self.kinds.values()}
        problems += [f"{_rel(path)}:1: no kind in `claude-lint rules --json` maps to this rule "
                     f"file, so the hook never delivers it - map it or delete it"
                     for path in self.rule_files if _rel(path) not in mapped]
        self.assert_none(problems)

    def test_shape(self) -> None:
        plugin = _plugin()["name"]
        skill_for = {entry["rule"]: entry["skill"] for entry in self.kinds.values()}
        hook_rule = self.kinds["hooks"]["rule"]
        problems = []
        for path in self.rule_files:
            rel = _rel(path)
            fm = _cl.parse_frontmatter(_read(path))
            body = fm.body.strip("\n")
            at, opening = next(((n, line) for n, line in enumerate(fm.body.split("\n"), fm.body_line)
                                if line.strip() and not line.startswith("#")), (fm.body_line, ""))
            if not opening.startswith(_RULE_OPENING):
                problems.append(f"{rel}:{at}: the body opens {opening[:40]!r} - open it "
                                f"with '{_RULE_OPENING} ...': the hook delivers the rule on a "
                                f"Read as well as on a Write or Edit")
            refs = _SKILL_REF_RE.findall(body)
            wanted = f"{plugin}:{skill_for.get(rel)}"
            if refs != [wanted]:
                problems.append(f"{rel}:{fm.body_line}: must point at exactly one skill, written "
                                f"Skill({wanted}) - the skill `claude-lint rules` pairs with this "
                                f"rule file; found {refs or 'none'}")
            names_tool = "linter" in body and (rel != hook_rule or "hooktool validate" in body)
            if not names_tool:
                problems.append(f"{rel}:{fm.body_line}: never names the linter - close with the "
                                f"one line saying the linter asserts the mechanical invariants "
                                f"(`hooktool validate` in the hook rule), and no command: the "
                                f"hook appends the runnable one at delivery")
            count = len(body.split("\n"))
            if count > _RULE_BODY_MAX_LINES:
                problems.append(f"{rel}:{fm.body_line}: body is {count} lines; a rule file is at "
                                f"most {_RULE_BODY_MAX_LINES} - keep two or three bullets of "
                                f"judgement and move the rest to the skill or a lint rule")
        self.assert_none(problems)

    def test_no_number_the_linter_owns(self) -> None:
        limits = _rules_table()["limits"]
        self.assert_none(
            f"{_rel(path)}:{n}: the number {said} is a limit the linter owns - {_LIMIT_FIX}"
            for path in self.rule_files
            for n, said in _bare_limit_numbers(_read(path), limits))


class CommandsRunAsWritten(_Case):
    """A command the model is shown is one it will try to run. The plugin puts
    nothing on PATH, so the linter is written by path - in a SKILL.md body
    through the plugin-root variable, which expands at load - and a rule file,
    which is delivered as plain text, carries no command at all: the hook
    appends the runnable one."""

    def test_no_placeholder_plugin_path(self) -> None:
        self.assert_none(
            f"{_rel(path)}:{n}: `{m.group(0)}` is a placeholder, not a path - in a SKILL.md or "
            f"plugin agent body write \"${{CLAUDE_PLUGIN_ROOT}}/...\", which expands at load; in "
            f"a rule or reference file name the tool and drop the command"
            for path in _model_facing()
            for n, line in enumerate(_read(path).splitlines(), 1)
            for m in _PLACEHOLDER_PATH_RE.finditer(line))

    def test_no_bare_linter_command_in_a_skill_body_or_rule_file(self) -> None:
        problems = []
        for path in _skill_files() + _md("rules/*.md"):
            fm = _cl.parse_frontmatter(_read(path))
            for n, said in _bare_lint_commands(fm.body, fm.body_line):
                fix = ("delete the command and say \"the linter\"; the hook appends the runnable "
                       "one when it delivers the rule" if path.parent.name == "rules" else
                       "write it once as python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint\" "
                       "<subcommand>, and say \"the linter\" after that")
                problems.append(f"{_rel(path)}:{n}: `{said}` cannot be run as written, nothing "
                                f"is on PATH - {fix}")
        self.assert_none(problems)

    def test_the_scan_sees_a_bare_command_and_ignores_a_path_or_a_name(self) -> None:
        bare = ("Run `claude-lint rules` for the reasons.", "see `claude-lint fields rule`",
                "```\nclaude-lint --all .\n```", "`claude-lint check-injection '<command>'`")
        for text in bare:
            with self.subTest(sees=text):
                self.assertTrue(list(_bare_lint_commands(text, 1)))
        fine = ('run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" rules`',
                "`python3 scripts/claude-lint fields skill`", "`claude-lint` remains the check",
                "claude-lint rules, in running prose, is a name", "the linter's `rules` table",
                "```\npython3 /opt/kit/scripts/claude-lint --all .\n```")
        for text in fine:
            with self.subTest(ignores=text):
                self.assertEqual(list(_bare_lint_commands(text, 1)), [])
        for text in ("python3 <plugin>/scripts/claude-lint rules", "<plugin-root>/hooks/x.sh"):
            with self.subTest(placeholder=text):
                self.assertTrue(_PLACEHOLDER_PATH_RE.search(text))
        for text in ("headed `[<plugin>] rule <name>`", "Skill(<plugin>:<skill>)"):
            with self.subTest(not_a_path=text):
                self.assertIsNone(_PLACEHOLDER_PATH_RE.search(text))


class NoHookPrintsToEverySession(_Case):
    """The prefer-code litmus used to be injected by a SessionStart hook into
    every session, relevant or not. It now arrives once, with the first rule a
    session receives, so the only SessionStart handler left is the one that
    resets the delivery markers, and it prints nothing."""

    def test_session_start_only_resets_rule_delivery(self) -> None:
        rel = _rel(_HOOKS_JSON)
        problems = []
        if _LITMUS_SCRIPT.exists():
            problems.append(f"{_rel(_LITMUS_SCRIPT)}:1: the session-start litmus script is back - "
                            f"delete it; `claude-lint hook` delivers the litmus with the first "
                            f"rule a session receives")
        lines = _read(_HOOKS_JSON).splitlines()
        groups = json.loads(_read(_HOOKS_JSON)).get("hooks", {}).get("SessionStart", [])
        for group in groups:
            for handler in group.get("hooks", []):
                command = " ".join(map(str, [handler.get("command", ""),
                                             *handler.get("args", [])]))
                written = json.dumps(handler.get("command", ""))[1:-1]    # as the file spells it
                n = next((i for i, line in enumerate(lines, 1) if written and written in line),
                         next((i for i, line in enumerate(lines, 1)
                               if '"SessionStart"' in line), 1))
                where = f"{rel}:{n}"
                if _RESET_SCRIPT not in command:
                    problems.append(f"{where}: a SessionStart handler other than "
                                    f"{_RESET_SCRIPT} ({command[:60]!r}) - remove it; SessionStart "
                                    f"stdout is context in every session, and standing context "
                                    f"belongs with the first rule the hook delivers")
        self.assert_none(problems)


class DescriptionsCarryIntentOnly(_Case):
    """A description matches what the user asks for. Delivery keyed on which
    file is touched is the hook's job, and guaranteed there."""

    def test_linter_finds_no_file_keyed_trigger(self) -> None:
        known = {rule["id"] for rule in _rules_table()["rules"]}
        self.assertLessEqual(
            set(_FILE_KEYED_TRIGGER_RULES), known,
            "tests/test_consistency.py: _FILE_KEYED_TRIGGER_RULES names a rule id the linter no "
            "longer has; this check would pass vacuously")
        self.assert_none(
            f"{f['path']}:{f.get('line', 1)}: {f['id']} {f['message']}"
            for f in _lint_report()["findings"] if f.get("id") in _FILE_KEYED_TRIGGER_RULES)

    def test_descriptions_stay_short(self) -> None:
        files = _skill_files() + _md("agents/*.md")
        self.assertTrue(files)
        problems = []
        for path in files:
            fm = _cl.parse_frontmatter(_read(path))
            length = len(str(fm.get("description") or ""))
            where = f"{_rel(path)}:{fm.lines.get('description', 1)}"
            if not length:
                problems.append(f"{where}: no description")
            elif length > _DESCRIPTION_MAX_CHARS:
                problems.append(f"{where}: description is {length} characters; this plugin keeps "
                                f"each to {_DESCRIPTION_MAX_CHARS} - cut the field list and keep "
                                f"the phrases users say")
        self.assert_none(problems)


class PointersLand(_Case):
    """"Point, don't copy" only works while the pointer lands."""

    def test_sections_other_files_rely_on_exist(self) -> None:
        problems = []
        for rel, heading in _OWNER_HEADINGS:
            path = _ROOT / rel
            if not path.is_file():
                problems.append(f"{rel}:1: missing; other files point at its \"{heading}\" section")
            elif not _lands(heading, _anchors(_read(path))):
                problems.append(f"{rel}:1: no \"{heading}\" heading - other files point at it by "
                                f"name; restore the heading, or rename it here and in every file "
                                f"that cites it")
        self.assert_none(problems)

    def judge(self) -> tuple[list[str], list[str], int]:
        """Return (pointers that miss, pointers that name no file, pointers judged)."""
        files = _model_facing()
        anchors = {path: _anchors(_read(path)) for path in files}
        missing, unjudged, judged = [], [], 0
        for path in files:
            names = _pointer_names(path, files)
            fm = _cl.parse_frontmatter(_read(path))
            for pointer in _pointers(fm.body, fm.body_line, _names_pattern(names)):
                where = f'{_rel(path)}:{pointer.line}: "{pointer.section}"'
                targets = {t for name in pointer.targets for t in names[name]}
                if pointer.here or not targets:
                    targets.add(path)
                if any(_lands(pointer.section, anchors[t]) for t in targets):
                    judged += 1
                elif pointer.targets or pointer.here:
                    judged += 1
                    looked = ", ".join(sorted(_rel(t) for t in targets))
                    missing.append(f"{where} is not a heading (or bold lead-in) in {looked} - fix "
                                   f"the name, or restore the section it points at")
                else:
                    unjudged.append(f"{where} reads like a section name, with no file or skill "
                                    f"named beside it")
        return missing, unjudged, judged

    def test_named_sections_resolve(self) -> None:
        missing, unjudged, judged = self.judge()
        note = ("\nnot judged (no file named):\n" + "\n".join(unjudged)) if unjudged else ""
        self.assert_none(missing, also=note)
        self.assertGreaterEqual(
            judged, _POINTERS_JUDGED_MIN,
            f"only {judged} section pointers were recognised; the heuristic in _pointers has "
            f"drifted from how the prose cites sections" + note)


class EachFactHasOneOwner(_Case):
    """The point of the whole exercise: a fact written twice eventually
    disagrees with itself, so each of these is stated in one file and every
    other file points at it (or at the tool that prints it)."""

    def test_no_other_prose_file_restates_a_single_owner_fact(self) -> None:
        texts = {_rel(path): _read(path) for path in _prose()}
        problems = []
        for fact in _SINGLE_OWNER_FACTS:
            for rel, text in texts.items():
                lines = _fact_lines(text, fact)
                cap = fact.allowed.get(rel, 0)
                extra = () if cap is None else lines[cap:]
                problems += [f"{rel}:{n}: restates \"{fact.name}\" - delete it or replace it with "
                             f"a pointer; its one home is {fact.owner}" for n in extra]
            problems += [f"{rel}:1: no longer states \"{fact.name}\", and it is the fact's one "
                         f"home - restore it, or move the fact and update _SINGLE_OWNER_FACTS"
                         for rel in fact.home if not _fact_lines(texts.get(rel, ""), fact)]
        self.assert_none(problems)

    def test_each_pattern_sees_its_fact(self) -> None:
        stated = (
            "A scoped rule loads when Claude uses Read, Write, or Edit on a matching file.",
            "Nothing is in `bin/`: claude.ai and Cowork don't install a plugin that has one.",
            "A plugin agent ignores `hooks`, `mcpServers`, `permissionMode` and `initialPrompt`.",
            "A `Stop` hook there is converted to `SubagentStop`.",
            "Claude Code reads AGENTS.md only when there is no CLAUDE.md above it.",
            "Forked guideline content gives the subagent nothing useful to return.",
            "Despite the name, the fork cannot see the conversation.",
            "A `description` matches intent; delivery keyed on a file is a rule's job.",
            "A bullet a program could check is a lint rule, not a bullet.",
        )
        for fact, text in zip(_SINGLE_OWNER_FACTS, stated, strict=True):
            with self.subTest(fact=fact.name):
                self.assertEqual(_fact_lines(text, fact), (1,))
        unrelated = "A `PostToolUse` hook on `Read|Write|Edit` returns the rule text, at exit 0."
        for fact in _SINGLE_OWNER_FACTS:
            with self.subTest(fact=fact.name, ignores=unrelated):
                self.assertEqual(_fact_lines(unrelated, fact), ())


class EvalSuiteHoldsItsOwnConventions(_Case):
    """evals/ is a `claude plugin eval` suite: one folder per skill, one case per
    folder below it. These tests keep its conventions from drifting
    (evals/README.md says why each exists)."""

    _EVALS = _ROOT / "evals"
    _LINT_GRADER = re.compile(r"^lint-([A-Z]{2}\d{3})-")

    def _cases(self) -> list[Path]:
        # Folders starting with "_" hold shared scaffolds and judge calibration, not skill cases.
        return sorted(p.parent for p in self._EVALS.glob("*/*/prompt.md") if not p.parts[-3].startswith("_"))

    def test_a_lint_mirror_grader_names_a_rule_the_linter_has(self) -> None:
        # A grader that re-checks a lint rule is named after it, so a rule that is
        # renamed or removed fails here instead of leaving the grader to drift.
        ids = {r["id"] for r in json.loads(_run(_LINT, "rules", "--json").stdout)["rules"]}
        problems = [f"{g.relative_to(_ROOT)}: no lint rule {m.group(1)}"
                    for g in self._EVALS.glob("*/*/graders/*.md")
                    if (m := self._LINT_GRADER.match(g.name)) and m.group(1) not in ids]
        self.assert_none(problems)

    def test_a_case_that_writes_a_plugin_runs_in_one(self) -> None:
        # Without .claude-plugin/plugin.json the kit's hook does not classify
        # agents/ files, so the lint loop the kit relies on would not be measured.
        problems = [f"{c.relative_to(_ROOT)}: asks for a plugin layout but has no scaffold_script"
                    for c in self._cases()
                    if "This directory is a Claude Code plugin" in (c / "prompt.md").read_text(encoding="utf-8")
                    and "scaffold_script" not in ((c / "case.yaml").read_text(encoding="utf-8")
                                                  if (c / "case.yaml").exists() else "")]
        self.assert_none(problems)

    def test_each_case_is_tagged_with_its_skill_and_one_kind(self) -> None:
        problems = []
        for c in self._cases():
            m = re.search(r"^tags:\s*\[([^\]]*)\]", (c / "prompt.md").read_text(encoding="utf-8"), re.M)
            tags = {t.strip() for t in m.group(1).split(",")} if m else set()
            if c.parent.name not in tags:
                problems.append(f"{c.relative_to(_ROOT)}: tags lack the skill name {c.parent.name}")
            if len(tags & {"capability", "regression"}) != 1:
                problems.append(f"{c.relative_to(_ROOT)}: tag it capability or regression, not {sorted(tags)}")
        self.assert_none(problems)

    def test_a_judge_calibration_case_uses_its_source_rubric_verbatim(self) -> None:
        # The calibration measures the judge on the rubric the suite really uses;
        # a copy that drifts from its source would measure a different rubric.
        problems = []
        for c in sorted(self._EVALS.glob("_judges/*/")):
            m = re.search(r'Judge calibration for ([^:"]+):', (c / "prompt.md").read_text(encoding="utf-8"))
            source = self._EVALS / m.group(1) if m else None
            graders = list((c / "graders").glob("*.md"))
            if source is None or not source.exists() or len(graders) != 1:
                problems.append(f"{c.relative_to(_ROOT)}: names no existing source grader, or has more than one grader")
            elif graders[0].read_text(encoding="utf-8") != source.read_text(encoding="utf-8"):
                problems.append(f"{c.relative_to(_ROOT)}: rubric differs from {source.relative_to(_ROOT)}")
        self.assert_none(problems)

    def test_case_names_are_unique(self) -> None:
        # `--case` and the report key on the directory name alone.
        seen: dict[str, Path] = {}
        problems = []
        for c in self._cases() + sorted(self._EVALS.glob("_judges/*/")):
            if c.name in seen:
                problems.append(f"{c.relative_to(_ROOT)} and {seen[c.name].relative_to(_ROOT)} share a name")
            seen.setdefault(c.name, c)
        self.assert_none(problems)


class PluginIsCleanByItsOwnTools(_Case):
    def test_lints_clean(self) -> None:
        done = _run(_LINT, "--all", _ROOT, "--json")
        report = json.loads(done.stdout)
        shown = "\n".join(json.dumps(f) for f in report["findings"])
        self.assertEqual(report["summary"]["error"], 0, shown)
        self.assertEqual(report["summary"]["warn"], 0, shown)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_hooks_json_validates_in_plugin_mode(self) -> None:
        done = _run(_HOOKTOOL, "validate", "--plugin", "--json", _ROOT / "hooks" / "hooks.json")
        report = json.loads(done.stdout)
        self.assertEqual(report["errors"], [], done.stderr)
        self.assertEqual(report["warnings"], [], done.stderr)
        self.assertTrue(report["valid"])
        self.assertEqual(done.returncode, 0)


class CrossReferencesResolve(_Case):
    def test_skill_references_are_qualified_and_exist(self) -> None:
        prefix = _plugin()["name"] + ":"
        known = _skill_names()
        seen, problems = 0, []
        for path in _model_facing():
            for n, line in enumerate(_read(path).splitlines(), 1):
                for ref in _SKILL_REF_RE.findall(line):
                    seen += 1
                    if not ref.startswith(prefix):
                        problems.append(f"{_rel(path)}:{n}: Skill({ref}) must be written "
                                        f"Skill({prefix}<skill>), the plugin.json name")
                    elif ref.removeprefix(prefix) not in known:
                        problems.append(f"{_rel(path)}:{n}: Skill({ref}) names no skills/ "
                                        f"directory")
        self.assertTrue(seen, "no Skill(...) reference found; the check would pass vacuously")
        self.assert_none(problems)

    def test_agent_skill_preloads_exist(self) -> None:
        """An entry is a bare skill name or <plugin>:<name>; no other prefix."""
        plugin = _plugin()["name"]
        known = _skill_names()
        seen, problems = 0, []
        for path in _md("agents/*.md"):
            fm = _cl.parse_frontmatter(_read(path))
            preloads = fm.get("skills") or []
            for entry in [preloads] if isinstance(preloads, str) else preloads:
                seen += 1
                where = f"{_rel(path)}:{fm.lines.get('skills', 1)}"
                owner, _, name = str(entry).rpartition(":")
                if owner and owner != plugin:
                    problems.append(f"{where}: skills: {entry} is qualified with '{owner}'; use "
                                    f"the bare name or {plugin}:{name}")
                elif name not in known:
                    problems.append(f"{where}: skills: {entry} names no skills/ directory "
                                    f"(have: {', '.join(sorted(known))})")
        self.assertTrue(seen, "no agent preloads a skill; the check would pass vacuously")
        self.assert_none(problems)


class LayoutInstallsEverywhere(_Case):
    def test_no_top_level_bin_directory(self) -> None:
        self.assertFalse(
            (_ROOT / "bin").exists() or (_ROOT / "bin").is_symlink(),
            f"bin/ exists at the plugin root - {_BIN_DOCS_REASON}. Move its files to "
            f"scripts/ and call them by path.")


class HumanDocsDescribeTodaysPlugin(_Case):
    """README, PHILOSOPHY, CHANGELOG and the linter's design notes."""

    def test_docs_exist(self) -> None:
        self.assert_none(f"{_rel(p)}: missing" for p in _LINKED_DOCS if not p.is_file())

    def test_no_bin_path_described_as_current(self) -> None:
        """A line may mention bin/ only to say it is absent: it must also say
        no / not / n't / never / without / moved / instead of. Code fences are
        checked too (a tree diagram lives in one). CHANGELOG is history."""
        self.assert_none(
            f"{_rel(path)}:{n}: describes a bin/ path as current; the executables are in "
            f"scripts/ ({_BIN_DOCS_REASON}): {line.strip()[:100]}"
            for path in _human_docs() if path != _CHANGELOG
            for n, line in enumerate(_read(path).splitlines(), 1)
            if _BIN_PATH_RE.search(line) and not _BIN_ABSENT_RE.search(line))

    def test_old_plugin_name_only_in_upgrade_context(self) -> None:
        """Allowed: anywhere in CHANGELOG, and elsewhere on a line - or under a
        heading - that says Upgrading, renamed or formerly."""
        current = _plugin()["name"]
        if current == _OLD_NAME:
            self.skipTest("plugin.json still carries the old name")
        problems = []
        for path in _human_docs():
            if path == _CHANGELOG:
                continue
            heading = ""
            for n, line in enumerate(_read(path).splitlines(), 1):
                found = _HEADING_RE.match(line)
                if found:
                    heading = found.group(1)
                if _OLD_NAME in line and not _OLD_NAME_CONTEXT_RE.search(line + " " + heading):
                    problems.append(f"{_rel(path)}:{n}: says '{_OLD_NAME}' outside an upgrade "
                                    f"note; the plugin is '{current}': {line.strip()[:100]}")
        self.assert_none(problems)

    def test_relative_links_resolve(self) -> None:
        seen, problems = 0, []
        for path in _LINKED_DOCS:
            if not path.is_file():
                continue
            for paragraph in _paragraphs(_read(path)):
                if paragraph.fenced:
                    continue
                # Dropping code spans keeps [`text`](target) and skips `[a](b)`.
                for m in _MD_LINK_RE.finditer(_CODE_SPAN_RE.sub("", paragraph.text)):
                    target = m.group(1)
                    if re.match(r"[a-z][a-z0-9+.-]*:|#|//", target, re.I):
                        continue
                    seen += 1
                    file_part = target.split("#", 1)[0].split("?", 1)[0]
                    if not (path.parent / file_part).exists():
                        problems.append(f"{_rel(path)}:{paragraph.starts[0][1]}: link target "
                                        f"'{target}' does not exist; fix the path or remove "
                                        f"the link")
        self.assertTrue(seen, "no relative link found; the check would pass vacuously")
        self.assert_none(problems)


class HooksReferenceDoesNotContradictHooktool(_Case):
    """`hooktool events` owns the event table; the reference only cites it."""

    def test_event_names_and_counts(self) -> None:
        events = {e["event"]: e for e in _hook_events()}
        self.assertTrue(events, "hooktool events --json listed nothing")
        words = {piece for name in events for piece in _camel_pieces(name)}
        text = _read(_HOOKS_REFERENCE)
        ref = _rel(_HOOKS_REFERENCE)
        problems = []
        for paragraph in _paragraphs(text):
            where = f"{ref}:{paragraph.starts[0][1]}"
            named = _CONFIG_KEY_RE.findall(paragraph.text) if paragraph.fenced else [
                token for token in _EVENT_TOKEN_RE.findall(paragraph.text)
                if len(_camel_pieces(token)) > 1 and words.issuperset(_camel_pieces(token))
                and "".join(_camel_pieces(token)) == token]
            problems += [f"{where}: names '{name}' like a hook event, and `hooktool events` has "
                         f"none by that name - fix the name, add the event to hooktool, or list "
                         f"it in _NOT_EVENTS in this test if it is not an event"
                         for name in named if name not in events and name not in _NOT_EVENTS]
            for m in _ALL_EVENTS_COUNT_RE.finditer(paragraph.text):
                if _to_int(m.group(1)) != len(events):
                    problems.append(f"{where}: says '{m.group(0)}' but `hooktool events` lists "
                                    f"{len(events)} - drop the count and cite the command")
            for m in _COLUMN_COUNT_RE.finditer(paragraph.text):
                field = _EVENT_COLUMNS.get(m.group(2).upper())
                marked = sum(1 for e in events.values() if field and e[field])
                if field and _to_int(m.group(1)) != marked:
                    problems.append(f"{where}: says {m.group(1)} events are marked {m.group(2)} "
                                    f"but `hooktool events` marks {marked} - fix or drop the count")
        self.assert_none(problems)


class VersionIsStatedOnce(_Case):
    def test_readme_status_version_matches_plugin_json(self) -> None:
        version = _plugin()["version"]
        section = re.search(r"^## Status\b.*?$(.*?)(?=^## |\Z)", _read(_README), re.M | re.S)
        self.assertIsNotNone(section, "README.md has no '## Status' section")
        assert section is not None
        # The plugin's own version is the backticked `vX.Y.Z` that opens the
        # section; Claude Code versions mentioned later are not it.
        stated = re.match(r"\s*`v?(\d+\.\d+\.\d+)`", section.group(1))
        self.assertIsNotNone(stated, "README.md: the '## Status' section must open with "
                                     "the plugin version in backticks, e.g. `v1.2.3`")
        assert stated is not None
        self.assertEqual(stated.group(1), version,
                         f"README.md status says {stated.group(1)}, plugin.json says "
                         f"{version}; change the README")

    def test_changelog_newest_entry_matches_plugin_json(self) -> None:
        version = _plugin()["version"]
        for n, line in enumerate(_read(_CHANGELOG).splitlines(), 1):
            m = re.match(r"^##\s+\[?v?(\d+\.\d+\.\d+)", line)
            if m:
                self.assertEqual(m.group(1), version,
                                 f"CHANGELOG.md:{n}: newest entry is {m.group(1)}, "
                                 f"plugin.json says {version}; add an entry for {version}")
                return
        self.fail("CHANGELOG.md has no '## X.Y.Z' entry")


if __name__ == "__main__":
    unittest.main()
