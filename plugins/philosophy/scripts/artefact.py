"""Check that the work loop's artefacts have the shape the next stage reads.

An intent lives at `intent/<slug>/` as `intent.md`, `spec.md`, and one
`plans/NN-<change>.md` per change. The core (`parse` and the `check_*` functions) takes
text and returns findings. `load_findings` at the bottom is the only code that reads
files, and `artefact-check` and the write hook are thin commands over both. Written for
Python 3.9 and the standard library, like the hooks, so it runs under whatever
`python3` is on PATH.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple, Optional

INTENT_SECTIONS = (
    "Problem",
    "Proposed outcome",
    "Affected users and systems",
    "Constraints",
    "Open questions",
)
SPEC_SECTIONS = (
    "Requirements",
    "Design",
    "Constraint mapping",
    "Open questions",
    "Areas of concern",
)
PLAN_SECTIONS = ("Files that change", "Order of work", "Risks", "Proof")

HEADING = re.compile(r"^## +(.+?)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
CHECKBOX = re.compile(r"^[-*]\s+\[([ xX])\]\s*(.*)$")
BULLET = re.compile(r"^[-*]\s+(.*)$")
NUMBERED = re.compile(r"^\d+\.\s+(.*)$")
DEFINED = re.compile(r"^[-*]\s+\*\*R(\d+)\.\*\*")
CITED = re.compile(r"\bR(\d+)\b")
LISTED_PATH = re.compile(r"^[-*]\s+`([^`]+)`")
PLAN_NAME = re.compile(r"^\d{2}-[a-z0-9][a-z0-9-]*\.md$")
CARRIED = re.compile(r"carried forward:\s*\S", re.I)  # with its reason
OWNER = re.compile(r"\bOwner:\s*\S", re.I)
APPLIED = re.compile(r"^Applied:\s*\S", re.M)


class Finding(NamedTuple):
    path: str
    check: str
    message: str


class Item(NamedTuple):
    """One list item, with its wrapped continuation lines joined on."""

    ticked: bool
    text: str


class Doc(NamedTuple):
    path: str
    title: str
    header: str
    sections: tuple[tuple[str, str], ...]


class ArtefactError(ValueError):
    """An artefact that could not be read."""


# --- the logic: plain data in, plain data out ---------------------------------------


def parse(text: str, path: str) -> Doc:
    """Split a markdown artefact into its title, the header before the first `##`, and
    its `##` sections. A `###` heading stays inside its section, and a heading inside a
    code fence is text, not a heading."""
    title = ""
    header: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        heading = None if fenced else HEADING.match(line)
        if heading:
            sections.append((heading.group(1), []))
        elif sections:
            sections[-1][1].append(line)
        elif not title and not fenced and line.startswith("# "):
            title = line[2:].strip()
        else:
            header.append(line)
    return Doc(
        path,
        title,
        "\n".join(header).strip(),
        tuple((name, "\n".join(body).strip()) for name, body in sections),
    )


def section(doc: Doc, name: str) -> Optional[str]:
    return next((body for heading, body in doc.sections if heading == name), None)


def items(body: str, start: re.Pattern[str]) -> tuple[str, ...]:
    """The top-level list items in a body that start with `start`, each with its
    indented continuation lines joined on."""
    found: list[list[str]] = []
    current: Optional[list[str]] = None
    for line in body.splitlines():
        if not line.strip():
            continue
        if start.match(line):
            current = [line.strip()]
            found.append(current)
        elif current is not None and line[0] in " \t":
            current.append(line.strip())
        else:
            current = None
    return tuple(" ".join(lines) for lines in found)


def checkboxes(body: str) -> tuple[Item, ...]:
    out = []
    for text in items(body, CHECKBOX):
        box = CHECKBOX.match(text)
        if box:
            out.append(Item(box.group(1) != " ", box.group(2)))
    return tuple(out)


def settled(question: Item) -> bool:
    return question.ticked or bool(CARRIED.search(question.text))


def table_rows(body: str) -> tuple[str, ...]:
    """A table's data rows: every `|` line but the header and its separator."""
    rows = [line for line in body.splitlines() if line.strip().startswith("|")]
    return tuple(rows[2:]) if len(rows) >= 2 else ()


def defined(spec: Doc) -> tuple[int, ...]:
    """The requirement numbers a spec defines, in the order it lists them."""
    body = section(spec, "Requirements") or ""
    return tuple(
        int(found.group(1))
        for line in body.splitlines()
        for found in [DEFINED.match(line.strip())]
        if found
    )


def cited(text: str) -> frozenset[int]:
    return frozenset(int(number) for number in CITED.findall(text))


def listed_paths(plan: Doc) -> tuple[str, ...]:
    """The paths a plan's Files that change lists, one backticked path per bullet."""
    body = section(plan, "Files that change") or ""
    return tuple(
        found.group(1).strip()
        for line in body.splitlines()
        for found in [LISTED_PATH.match(line.strip())]
        if found
    )


def check_title(doc: Doc, kind: str) -> list[Finding]:
    if doc.title.startswith(kind + ":") and doc.title[len(kind) + 1 :].strip():
        return []
    return [Finding(doc.path, "title", "the first line should read '# %s: <title>'" % kind)]


def check_sections(doc: Doc, names: tuple[str, ...]) -> list[Finding]:
    out = []
    for name in names:
        body = section(doc, name)
        if body is None:
            out.append(Finding(doc.path, "sections", "has no '## %s' section: add it" % name))
        elif not body:
            out.append(Finding(doc.path, "sections", "its '## %s' section is empty" % name))
    return out


def check_questions(doc: Doc) -> list[Finding]:
    return [
        Finding(
            doc.path,
            "questions",
            'open question is neither ticked nor carried forward: "%s". Tick it when it '
            'is settled, or add "Carried forward:" and why it can wait' % question.text,
        )
        for question in checkboxes(section(doc, "Open questions") or "")
        if not settled(question)
    ]


def check_intent(doc: Doc) -> list[Finding]:
    out = check_title(doc, "Intent") + check_sections(doc, INTENT_SECTIONS)
    for field in ("Author:", "Status:"):
        if field not in doc.header:
            out.append(Finding(doc.path, "header", "the line under the title needs '%s'" % field))
    return out + check_questions(doc)


def check_requirements(spec: Doc) -> list[Finding]:
    numbers = defined(spec)
    if not numbers:
        return [
            Finding(
                spec.path,
                "requirements",
                "defines no requirements: list each as '- **R1.** <requirement>'",
            )
        ]
    out = [
        Finding(spec.path, "requirements", "R%d is defined more than once" % number)
        for number in sorted({n for n in numbers if numbers.count(n) > 1})
    ]
    missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
    if missing:
        out.append(
            Finding(
                spec.path,
                "requirements",
                "requirements skip %s: number them R1 to R%d with no gaps"
                % (", ".join("R%d" % n for n in missing), max(numbers)),
            )
        )
    return out


def check_mapping(spec: Doc, intent: Optional[Doc]) -> list[Finding]:
    if intent is None:
        return []
    constraints = items(section(intent, "Constraints") or "", BULLET)
    rows = table_rows(section(spec, "Constraint mapping") or "")
    if len(rows) == len(constraints):
        return []
    return [
        Finding(
            spec.path,
            "mapping",
            "the intent has %d constraints and the constraint mapping has %d rows: give "
            "each constraint one row. The check counts rows; it can't compare wording"
            % (len(constraints), len(rows)),
        )
    ]


def check_concerns(spec: Doc) -> list[Finding]:
    return [
        Finding(
            spec.path,
            "concerns",
            'area of concern names no owner: "%s". Add "Owner: <who resolves it>"' % concern[:80],
        )
        for concern in items(section(spec, "Areas of concern") or "", NUMBERED)
        if not OWNER.search(concern)
    ]


def check_spec(spec: Doc, intent: Optional[Doc]) -> list[Finding]:
    out = check_title(spec, "Spec") + check_sections(spec, SPEC_SECTIONS)
    if "Intent:" not in spec.header:
        out.append(Finding(spec.path, "header", "the header needs an 'Intent:' line"))
    if not APPLIED.search(spec.header):
        out.append(
            Finding(
                spec.path,
                "header",
                "the header needs an 'Applied:' line naming each policy rule and skill in "
                "force while it was written",
            )
        )
    return (
        out
        + check_requirements(spec)
        + check_mapping(spec, intent)
        + check_questions(spec)
        + check_concerns(spec)
    )


def check_plan(plan: Doc, name: str, spec: Optional[Doc]) -> list[Finding]:
    out = check_title(plan, "Plan") + check_sections(plan, PLAN_SECTIONS)
    if not PLAN_NAME.match(name):
        out.append(Finding(plan.path, "name", "name the plan NN-<change>.md, such as 01-%s" % name))
    if section(plan, "Files that change") is not None and not listed_paths(plan):
        out.append(
            Finding(
                plan.path,
                "files",
                "Files that change lists no paths: one bullet per file, the path in backticks",
            )
        )
    if spec is None:
        return out + [Finding(plan.path, "spec", "there is no spec.md beside this plan's intent")]
    citations = cited("\n".join([plan.header] + [body for _, body in plan.sections]))
    known = frozenset(defined(spec))
    if not citations:
        out.append(
            Finding(plan.path, "citations", "cites no requirement: name the R-numbers it delivers")
        )
    out += [
        Finding(
            plan.path,
            "citations",
            "cites R%d, which %s doesn't define" % (number, spec.path),
        )
        for number in sorted(citations - known)
    ]
    return out


def check_intent_dir(
    intent: Optional[Doc], spec: Optional[Doc], plans: tuple[tuple[str, Doc], ...], where: str
) -> list[Finding]:
    """Everything that should hold for one intent directory."""
    if intent is None:
        return [Finding(where, "intent", "has no intent.md")]
    out = check_intent(intent)
    if spec is not None:
        out += check_spec(spec, intent)
    for name, plan in plans:
        out += check_plan(plan, name, spec)
    return out


def render(findings: list[Finding]) -> str:
    return "\n".join("%s %s: %s" % finding for finding in findings)


# --- the shell ----------------------------------------------------------------------


def read(path: Path) -> Optional[Doc]:
    if not path.exists():
        return None
    try:
        return parse(path.read_text(encoding="utf-8"), str(path))
    except (OSError, UnicodeDecodeError) as error:
        raise ArtefactError("could not read %s: %s" % (path, error)) from error


def intent_dirs(path: Path) -> tuple[Path, ...]:
    """The intent directories a path names: the one a file belongs to, the directory
    itself, or every directory under it. Every directory under `intent/` is an intent,
    so one with no `intent.md`, such as a stray notes folder, is reported as missing it.

    Raises:
        ArtefactError: the path does not exist.
    """
    if not path.exists():
        raise ArtefactError("%s does not exist" % path)
    if path.is_file():
        folder = path.parent.parent if path.parent.name == "plans" else path.parent
        return (folder,)
    if (path / "intent.md").exists() or (path / "spec.md").exists():
        return (path,)
    return tuple(sorted(child for child in path.iterdir() if child.is_dir()))


def load_findings(path: Path) -> list[Finding]:
    """Read every artefact under a path and check it.

    Raises:
        ArtefactError: a path or an artefact could not be read.
    """
    out: list[Finding] = []
    for folder in intent_dirs(path):
        plans_dir = folder / "plans"
        plans = (
            tuple(
                (plan.name, doc)
                for plan in sorted(plans_dir.glob("*.md"))
                for doc in [read(plan)]
                if doc is not None
            )
            if plans_dir.is_dir()
            else ()
        )
        out += check_intent_dir(
            read(folder / "intent.md"), read(folder / "spec.md"), plans, str(folder)
        )
    return out
