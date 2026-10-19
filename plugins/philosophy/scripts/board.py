"""Read a Backlog.md board and check it against the work loop's conventions.

The core (`parse_*` and `check_*`) takes text and returns data. The shell at the bottom
is the only code that reads files or runs git, and `board-check` and `close-task` are
thin commands over both. Written for Python 3.9 and the standard library, like the
hooks, so it runs under whatever `python3` is on PATH.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import NamedTuple, Optional

TYPES = ("intent", "design", "spike", "task", "bug")
SIZES = ("size-1", "size-2", "size-3", "size-5", "size-8")
FINISH_MOVED = "finish-moved"
PLAN_HEADINGS = ("Order of work", "Risks", "Proof")
SPEC_SECTIONS = (
    "Requirements",
    "Policies applied",
    "Areas of concern",
    "Open questions",
    "Design questions",
    "Out of scope",
)
DELIVERS_REQUIREMENTS = ("task", "bug")
TASK_DIRS = ("tasks", "drafts", "completed")
CITATION = re.compile(r"\bR(\d+)\b")
REQUIREMENT = re.compile(r"^\s*(?:[-*]|\d+[.)])?\s*(?:\*\*|__)?R(\d+)\b", re.M)
BLOCK_SCALAR = re.compile(r"[>|][+-]?")
KNOWN_SECTIONS = re.compile(
    r"^## (?:Acceptance Criteria|Implementation Plan|Implementation Notes|Final Summary"
    r"|Definition of Done)[ \t]*$",
    re.M | re.I,
)
CHECKBOX = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(?:#\d+\s+)?(.*?)\s*$", re.M)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", re.S)
REPRO = re.compile(r"^Repro at ([0-9a-f]{7,40}), test files: (.+?); command: ", re.M)
NO_REPRO = re.compile(r"^No repro:", re.M | re.I)
CHECKS_CHANGED = re.compile(r"^Checks changed:", re.M | re.I)
CHECKS_FILE = ".claude/checks.json"


class Route(NamedTuple):
    """Which model runs a task, at what effort, and why. `effort` None means the default."""

    model: str
    effort: Optional[str]
    why: str


# Model aliases, not versions, so the table doesn't go stale. Change the routing here.
ORCHESTRATE = Route("opus", "high", "it has children, or it is an intent, a spike or a design")
LEAF = Route("sonnet", "medium", "a leaf at size 2 to 5")
SMALL_LEAF = Route("haiku", None, "a leaf at size 1, given numbered steps")
SWEEP = Route("qwen-27b-local", None, "a sweep that has to read; one a script can do needs none")


class Item(NamedTuple):
    """A checkbox line: an acceptance criterion or an open question."""

    ticked: bool
    text: str


class Task(NamedTuple):
    id: str
    title: str
    status: str
    type: str
    labels: tuple[str, ...]
    parent: str
    documentation: tuple[str, ...]
    modified_files: tuple[str, ...]
    description: str
    criteria: tuple[Item, ...]
    plan: str
    path: str
    dependencies: tuple[str, ...] = ()
    notes: str = ""


class Doc(NamedTuple):
    id: str
    title: str
    type: str
    body: str
    path: str


class Board(NamedTuple):
    tasks: tuple[Task, ...]
    docs: tuple[Doc, ...]
    types: tuple[str, ...]
    prefix: str


class Finding(NamedTuple):
    id: str
    check: str
    message: str


# --- reading the files: text in, data out --------------------------------------------


def unquote(value: str) -> str:
    """Undo YAML quoting the way Backlog.md writes it, and drop a trailing comment."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return str(json.loads(value))
        except ValueError:
            return value[1:-1]
    return re.sub(r"\s+#.*$", "", value)


def parse_yaml(text: str) -> dict:
    """Read the YAML subset Backlog.md writes.

    That is scalars, `- item` lists, `[a, b]` lists, and the folded (`>-`) or literal
    (`|`) blocks it uses for a value longer than about 80 characters.
    """
    data: dict = {}
    key = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        keyed = re.match(r"^([A-Za-z_][\w-]*):(?:[ \t]+(.*))?$", line)
        listed = re.match(r"^(\s*)-[ \t]+(.*)$", line)
        if keyed:
            raw = (keyed.group(2) or "").strip()
        elif listed and key is not None and isinstance(data.get(key), list):
            raw = listed.group(2).strip()
        else:
            continue
        if BLOCK_SCALAR.fullmatch(raw):
            indent = len(line) - len(line.lstrip())
            block = []
            while i < len(lines) and (
                not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent
            ):
                block.append(lines[i].strip())
                i += 1
            value = ("\n" if raw[0] == "|" else " ").join(part for part in block if part)
        elif raw.startswith("[") and raw.endswith("]"):
            found = re.findall(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^']|'')*'|[^,\s][^,]*", raw[1:-1])
            value = [unquote(item) for item in found]
        else:
            value = unquote(raw) if raw else []
        if keyed:
            key = keyed.group(1)
            data[key] = value
        else:
            data[key].append(value)
    return data


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a Backlog.md file into its frontmatter and its body."""
    found = FRONTMATTER.match(text.lstrip("\ufeff").replace("\r\n", "\n"))
    if not found:
        return {}, text
    return parse_yaml(found.group(1)), found.group(2)


def scalar(data: dict, key: str) -> str:
    value = data.get(key, "")
    return value if isinstance(value, str) else ""


def strings(data: dict, key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if isinstance(value, list):
        return tuple(value)
    return (value,) if value else ()


def marked(body: str, name: str) -> Optional[str]:
    """The text between Backlog.md's `<!-- NAME:BEGIN -->` and `<!-- NAME:END -->` markers."""
    found = re.search(
        r"<!-- %s:BEGIN -->\n?(.*?)\n?<!-- %s:END -->" % (re.escape(name), re.escape(name)),
        body,
        re.S,
    )
    return found.group(1) if found else None


def subsection(text: str, heading: str, level: int) -> Optional[str]:
    """The text under a markdown heading, up to the next heading at the same level or above."""
    pattern = r"^%s[ \t]+%s[ \t]*$\n?(.*?)(?=^#{1,%d}[ \t]|\Z)" % (
        "#" * level,
        re.escape(heading),
        level,
    )
    found = re.search(pattern, text, re.M | re.S | re.I)
    return found.group(1) if found else None


def checkboxes(text: str) -> tuple[Item, ...]:
    return tuple(Item(found.group(1) != " ", found.group(2)) for found in CHECKBOX.finditer(text))


def unmarked_description(body: str) -> str:
    """A description written by hand: the body up to the first section the CLI owns."""
    text = re.sub(r"\A\s*## Description[ \t]*\n", "", body, flags=re.I)
    end = KNOWN_SECTIONS.search(text)
    return text[: end.start()] if end else text


def parse_task(text: str, path: str) -> Task:
    data, body = parse_frontmatter(text)
    description = marked(body, "SECTION:DESCRIPTION")
    criteria = marked(body, "AC")
    plan = marked(body, "SECTION:PLAN")
    return Task(
        id=scalar(data, "id"),
        title=scalar(data, "title"),
        status=scalar(data, "status"),
        type=scalar(data, "type"),
        labels=strings(data, "labels"),
        parent=scalar(data, "parent_task_id"),
        documentation=strings(data, "documentation"),
        modified_files=strings(data, "modified_files"),
        description=description if description is not None else unmarked_description(body),
        criteria=checkboxes(
            criteria if criteria is not None else subsection(body, "Acceptance Criteria", 2) or ""
        ),
        plan=plan if plan is not None else subsection(body, "Implementation Plan", 2) or "",
        path=path,
        dependencies=strings(data, "dependencies"),
        notes=marked(body, "SECTION:NOTES") or subsection(body, "Implementation Notes", 2) or "",
    )


def parse_doc(text: str, path: str) -> Doc:
    data, body = parse_frontmatter(text)
    return Doc(scalar(data, "id"), scalar(data, "title"), scalar(data, "type"), body, path)


# --- what the board says: data in, data out ------------------------------------------


def same_id(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def candidate_ids(raw: str, prefix: str) -> tuple[str, ...]:
    """The ids `raw` may mean: `5` is TASK-5 or DRAFT-5, and `task-5` is TASK-5."""
    raw = raw.strip()
    if re.fullmatch(r"\d+(?:\.\d+)*", raw):
        return ("%s-%s" % (prefix.upper(), raw), "DRAFT-%s" % raw)
    return (raw.upper(),)


def find_task(board: Board, raw: str) -> Optional[Task]:
    """The task `raw` names.

    Raises:
        LookupError: a bare number names both a task and a draft.
    """
    found = [
        t
        for wanted in candidate_ids(raw, board.prefix)
        for t in board.tasks
        if same_id(t.id, wanted)
    ]
    if len(found) > 1:
        raise LookupError(
            "%r is both %s; give the full id" % (raw, " and ".join(t.id for t in found))
        )
    return found[0] if found else None


def find_doc(board: Board, raw: str) -> Optional[Doc]:
    wanted = "doc-%s" % raw.strip() if raw.strip().isdigit() else raw
    return next(
        (
            d
            for d in board.docs
            if same_id(d.id, wanted) or d.path == raw or Path(d.path).name == raw
        ),
        None,
    )


def is_draft(task: Task) -> bool:
    return same_id(task.status, "Draft") or "/drafts/" in task.path


def is_done(task: Task) -> bool:
    return same_id(task.status, "Done")


def children(board: Board, task: Task) -> tuple[Task, ...]:
    """The accepted tasks directly under this one. Drafts under it are not yet work."""
    return tuple(
        t for t in board.tasks if same_id(t.parent, task.id) and not is_draft(t) and t != task
    )


def ancestors(board: Board, task: Task) -> tuple[Task, ...]:
    found: list[Task] = []
    current = task
    while current.parent:
        parent = next((t for t in board.tasks if same_id(t.id, current.parent)), None)
        if parent is None or parent in found:
            break
        found.append(parent)
        current = parent
    return tuple(found)


def descendants(board: Board, task: Task) -> tuple[Task, ...]:
    return tuple(t for t in board.tasks if not is_draft(t) and task in ancestors(board, t))


def open_questions(text: str) -> tuple[Item, ...]:
    section = subsection(text, "Open questions", 2)
    return checkboxes(section) if section is not None else ()


def settled(question: Item) -> bool:
    """Ticked, or carried forward on purpose with the reason on its line."""
    return question.ticked or "carried forward" in question.text.lower()


def cited(task: Task) -> frozenset[str]:
    text = "\n".join((task.title, task.description, task.plan, *(c.text for c in task.criteria)))
    return frozenset(CITATION.findall(text))


def requirements(doc: Doc) -> tuple[str, ...]:
    section = subsection(doc.body, "Requirements", 2)
    return tuple(REQUIREMENT.findall(section)) if section is not None else ()


def links(doc: Doc, entry: str) -> bool:
    return same_id(entry, doc.id) or Path(entry).name == Path(doc.path).name


# --- the checks: each finding says what is wrong and how to fix it -------------------


def check_size(task: Task, required: bool) -> list[Finding]:
    found = [label for label in task.labels if label.lower().startswith("size-")]
    out = [
        Finding(task.id, "size", "%s is not a size: sizes are 1, 2, 3, 5 and 8" % label)
        for label in found
        if label not in SIZES
    ]
    if len(found) > 1:
        out.append(
            Finding(
                task.id,
                "size",
                "has %d size labels (%s): keep one" % (len(found), ", ".join(found)),
            )
        )
    if required and not found:
        out.append(
            Finding(
                task.id,
                "size",
                "has no size label: size it before it is accepted (size-1 to size-8)",
            )
        )
    return out


def check_sizes(board: Board) -> list[Finding]:
    """Every accepted, open task has one valid size, and nothing at 8 starts unsplit."""
    out: list[Finding] = []
    for task in board.tasks:
        out += check_size(task, required=not is_draft(task) and not is_done(task))
        if (
            same_id(task.status, "In Progress")
            and "size-8" in task.labels
            and not children(board, task)
        ):
            out.append(
                Finding(
                    task.id,
                    "size",
                    "is in progress at size 8 with no children: split it before it starts",
                )
            )
    return out


def check_ready(board: Board, task: Task) -> list[Finding]:
    """Whether a draft is understood well enough to accept."""
    out: list[Finding] = []
    if not task.criteria:
        out.append(
            Finding(
                task.id,
                "ready",
                "has no acceptance criteria: add what is true when it is done with --ac",
            )
        )
    if task.type not in TYPES:
        out.append(
            Finding(
                task.id,
                "ready",
                "has type %r: set one of %s with --type" % (task.type, ", ".join(TYPES)),
            )
        )
    out += [f._replace(check="ready") for f in check_size(task, required=True)]
    out += [
        Finding(
            task.id,
            "ready",
            'open question is neither answered nor carried forward: "%s". Tick it, or add '
            '"Carried forward:" and why it can wait' % question.text,
        )
        for question in open_questions(task.description)
        if not settled(question)
    ]
    return out


def check_plan(board: Board, task: Task) -> list[Finding]:
    """Whether a leaf's plan has the shape someone else could implement from."""
    if not task.plan.strip():
        return [
            Finding(
                task.id,
                "plan",
                "has no implementation plan: write one with --plan holding "
                + ", ".join("### " + h for h in PLAN_HEADINGS),
            )
        ]
    out: list[Finding] = []
    for heading in PLAN_HEADINGS:
        body = subsection(task.plan, heading, 3)
        if body is None:
            out.append(Finding(task.id, "plan", "plan has no '### %s' section" % heading))
        elif not body.strip():
            out.append(Finding(task.id, "plan", "plan's '### %s' section is empty" % heading))
    if not task.modified_files:
        out.append(
            Finding(
                task.id, "plan", "lists no files: add each file that changes with --modified-file"
            )
        )
    holder = next((a for a in ancestors(board, task) if a.documentation), None)
    if holder is not None and task.type in DELIVERS_REQUIREMENTS and not cited(task):
        out.append(
            Finding(
                task.id,
                "plan",
                "cites no requirement from %s's spec: name the R-numbers it delivers" % holder.id,
            )
        )
    return out


def check_spec(board: Board, doc: Doc, coverage: bool) -> list[Finding]:
    """Whether a spec is linked, complete, numbered, and (with coverage) fully split."""
    out: list[Finding] = []
    if doc.type != "specification":
        out.append(
            Finding(doc.id, "spec", "has type %r: a spec is a doc of type specification" % doc.type)
        )
    named = re.search(r"^Intent:[ \t]*(\S+)", doc.body, re.M)
    intent = find_task(board, named.group(1)) if named else None
    if named is None:
        out.append(Finding(doc.id, "spec", "has no 'Intent: <id>' line"))
    elif intent is None:
        out.append(
            Finding(
                doc.id, "spec", "names %s as its intent, which is not on the board" % named.group(1)
            )
        )
    elif not any(links(doc, entry) for entry in intent.documentation):
        out.append(
            Finding(
                doc.id,
                "spec",
                '%s does not link it: backlog task edit %s --doc "%s"'
                % (intent.id, intent.id, doc.path),
            )
        )
    for section in SPEC_SECTIONS:
        if subsection(doc.body, section, 2) is None:
            out.append(Finding(doc.id, "spec", "has no '## %s' section" % section))
    numbers = requirements(doc)
    if subsection(doc.body, "Requirements", 2) is not None and not numbers:
        out.append(Finding(doc.id, "spec", "lists no numbered requirements (R1, R2, ...)"))
    out += [
        Finding(doc.id, "spec", "R%s is numbered more than once" % number)
        for number, count in sorted(Counter(numbers).items())
        if count > 1
    ]
    out += [
        Finding(
            doc.id,
            "spec",
            'open question is neither answered nor carried forward: "%s"' % question.text,
        )
        for question in open_questions(doc.body)
        if not settled(question)
    ]
    if coverage and intent is not None:
        delivered: set[str] = set()
        for task in descendants(board, intent):
            if task.type in DELIVERS_REQUIREMENTS:
                delivered |= cited(task)
        out += [
            Finding(doc.id, "spec", "R%s is not cited by any task under %s" % (number, intent.id))
            for number in dict.fromkeys(numbers)
            if number not in delivered
        ]
    return out


def check_close(board: Board, task: Task) -> list[Finding]:
    """Whether the criteria and the children let this task close."""
    out: list[Finding] = []
    if is_done(task):
        out.append(Finding(task.id, "close", "is already Done"))
    if is_draft(task):
        out.append(Finding(task.id, "close", "is a draft: it was never accepted"))
    if task.type == "bug" and not repro_records(task.notes) and not NO_REPRO.search(task.notes):
        out.append(
            Finding(
                task.id,
                "close",
                "a bug closes with its repro recorded: record-check <id> --repro -- <the test "
                "that fails>, or a note starting `No repro:` that says why it can't have one",
            )
        )
    out += check_closed(board, task)
    return out


def check_closed(board: Board, task: Task) -> list[Finding]:
    """What a Done task should already satisfy: every criterion met, every child done."""
    out: list[Finding] = []
    if not task.criteria:
        out.append(Finding(task.id, "close", "has no acceptance criteria to close against"))
    out += [
        Finding(task.id, "close", 'criterion #%d is not met: "%s"' % (number, criterion.text))
        for number, criterion in enumerate(task.criteria, 1)
        if not criterion.ticked
    ]
    out += [
        Finding(
            task.id,
            "close",
            "child %s is %s: a parent stays open while its children are. Close it, or move it "
            "to a new intent that says why it was deferred" % (child.id, child.status or "unset"),
        )
        for child in children(board, task)
        if not is_done(child)
    ]
    return out


def criteria_changes(before: tuple[Item, ...], now: tuple[Item, ...]) -> list[str]:
    """How the wording of the criteria changed. Ticks and order are not changes."""
    then = Counter(" ".join(item.text.split()) for item in before)
    current = Counter(" ".join(item.text.split()) for item in now)
    changes = ["removed %r" % text for text in (then - current)]
    return changes + ["added %r" % text for text in (current - then)]


def check_moved(task: Task, accepted: tuple[Item, ...], commit: str) -> list[Finding]:
    """Whether the criteria changed since acceptance without the finish-moved label.

    Ticking a box or reordering the list is not a change to the finish line.
    """
    if FINISH_MOVED in task.labels:
        return []
    changes = criteria_changes(accepted, task.criteria)
    if not changes:
        return []
    return [
        Finding(
            task.id,
            "moved",
            "acceptance criteria changed since it was accepted in %s (%s): add the %s label and "
            "a note saying what changed and why" % (commit[:7], "; ".join(changes), FINISH_MOVED),
        )
    ]


def check_uncommitted(task: Task, committed: Task) -> list[Finding]:
    """Whether the finish line differs from the last commit at the moment of closing.

    Ticking and unticking criteria is the review. Rewording one, or adding finish-moved,
    is a change to the finish line, and whoever makes it commits it before the review,
    so the reviewer cannot move the line it is judging.
    """
    out: list[Finding] = []
    changes = criteria_changes(committed.criteria, task.criteria)
    if changes:
        out.append(
            Finding(
                task.id,
                "close",
                "the acceptance criteria have uncommitted changes (%s). A finish line that "
                "moves is committed, with the %s label and a note, by whoever moved it, before "
                "review; a reviewer reports it as a finding instead"
                % ("; ".join(changes), FINISH_MOVED),
            )
        )
    if FINISH_MOVED in task.labels and FINISH_MOVED not in committed.labels:
        out.append(
            Finding(
                task.id,
                "close",
                "the %s label is not committed: it is committed with the change it explains, "
                "before review" % FINISH_MOVED,
            )
        )
    return out


def waits_on(board: Board, task: Task, other: Task) -> bool:
    """Whether `task` depends on `other`, directly or through other tasks."""
    seen: set[str] = set()
    queue = list(task.dependencies)
    while queue:
        wanted = queue.pop()
        if same_id(wanted, other.id):
            return True
        if wanted.lower() in seen:
            continue
        seen.add(wanted.lower())
        found = next((t for t in board.tasks if same_id(t.id, wanted)), None)
        if found is not None:
            queue.extend(found.dependencies)
    return False


def plain_path(path: str) -> str:
    return re.sub(r"^(?:\./)+", "", path.strip())


def check_parallel(board: Board, tasks: tuple[Task, ...]) -> list[Finding]:
    """Whether these tasks can run at the same time: no shared files, no waiting."""
    out = [
        Finding(task.id, "parallel", "lists no files, so overlap can't be checked: plan it first")
        for task in tasks
        if not task.modified_files
    ]
    for a, b in combinations(tasks, 2):
        shared = sorted(
            {plain_path(f) for f in a.modified_files} & {plain_path(f) for f in b.modified_files}
        )
        if shared:
            out.append(
                Finding(
                    a.id,
                    "parallel",
                    "shares %s with %s: run them one after the other" % (", ".join(shared), b.id),
                )
            )
        for first, then in ((a, b), (b, a)):
            if waits_on(board, then, first):
                out.append(
                    Finding(then.id, "parallel", "waits on %s: run them in order" % first.id)
                )
    return out


def route(board: Board, task: Task) -> tuple[Optional[Route], list[Finding]]:
    """The model and effort for a task, from its type, its size, and whether it was split."""
    if children(board, task) or task.type in ("intent", "spike", "design"):
        return ORCHESTRATE, []
    sizes = [label for label in task.labels if label in SIZES]
    if len(sizes) != 1:
        return None, [
            Finding(
                task.id, "route", "needs exactly one size label, since the size picks the model"
            )
        ]
    if sizes[0] == "size-8":
        return None, [Finding(task.id, "route", "is at size 8: split it before it starts")]
    return (SMALL_LEAF if sizes[0] == "size-1" else LEAF), []


def repro_records(notes: str) -> list[tuple[str, tuple[str, ...]]]:
    """Each repro test recorded by `record-check --repro`: its commit and its test files."""
    return [
        (found.group(1), tuple(p.strip() for p in found.group(2).split(", ")))
        for found in REPRO.finditer(notes)
    ]


def check_repro(task: Task, edited: dict[str, str]) -> list[Finding]:
    """`edited` maps each repro test file that changed since its commit to that commit."""
    return [
        Finding(
            task.id,
            "close",
            "the repro test %s changed since %s: a fix doesn't edit the test that reproduced "
            "the bug. Restore it, or record a new repro and say why" % (path, commit[:7]),
        )
        for path, commit in sorted(edited.items())
    ]


def check_declared_checks(task: Task, changed_since: Optional[str]) -> list[Finding]:
    """`changed_since` is the acceptance commit when the declared checks differ from it."""
    if changed_since is None or CHECKS_CHANGED.search(task.notes):
        return []
    return [
        Finding(
            task.id,
            "close",
            "%s changed since %s was accepted in %s, so the checks on it may not be the ones "
            "agreed. Revert it, or add a note starting `Checks changed:` that says why"
            % (CHECKS_FILE, task.id, changed_since[:7]),
        )
    ]


def check_config(board: Board) -> list[Finding]:
    missing = [t for t in TYPES if t not in board.types]
    if not missing:
        return []
    wanted = ", ".join('"%s"' % t for t in dict.fromkeys((*board.types, *TYPES)))
    return [
        Finding(
            "config",
            "config",
            "backlog/config.yml types lack %s, so the CLI rejects them. `backlog config set` "
            "cannot change types: edit the file to read types: [%s]" % (", ".join(missing), wanted),
        )
    ]


def check_board(board: Board, accepted: dict[str, tuple[str, tuple[Item, ...]]]) -> list[Finding]:
    """Everything that should hold across the whole board at any time.

    `accepted` maps a task id to the commit that accepted it and its criteria then.
    """
    out = check_config(board) + check_sizes(board)
    for task in board.tasks:
        if task.id in accepted:
            commit, criteria = accepted[task.id]
            out += check_moved(task, criteria, commit)
        if is_done(task):
            out += check_closed(board, task)
        elif (
            same_id(task.status, "In Progress")
            and task.type in DELIVERS_REQUIREMENTS
            and "size-1" not in task.labels
            and not children(board, task)
        ):
            out += check_plan(board, task)
    for doc in board.docs:
        if doc.type == "specification":
            named = re.search(r"^Intent:[ \t]*(\S+)", doc.body, re.M)
            intent = find_task(board, named.group(1)) if named else None
            out += check_spec(
                board, doc, coverage=intent is not None and bool(children(board, intent))
            )
    return out


def render(findings: list[Finding], as_json: bool, clean: str) -> str:
    if as_json:
        return json.dumps([f._asdict() for f in findings], indent=2)
    if not findings:
        return "ok: %s" % clean
    return "\n".join("%s %s: %s" % f for f in findings)


# --- the shell: files and git --------------------------------------------------------


def find_root(start: Path) -> Optional[Path]:
    """The nearest directory, from `start` upwards, that holds `backlog/config.yml`."""
    start = start.resolve()
    for directory in (start, *start.parents):
        if (directory / "backlog" / "config.yml").is_file():
            return directory
    return None


def load_board(root: Path) -> Board:
    base = root / "backlog"
    tasks = tuple(
        parse_task(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix())
        for folder in TASK_DIRS
        for path in sorted((base / folder).glob("*.md"))
        if path.is_file()
    )
    docs = tuple(
        parse_doc(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix())
        for path in sorted((base / "docs").rglob("*.md"))
        if path.is_file()
    )
    config = parse_yaml((base / "config.yml").read_text(encoding="utf-8"))
    return Board(tasks, docs, strings(config, "types"), scalar(config, "task_prefix") or "task")


def git(root: Path, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def accepted_version(root: Path, task: Task) -> Optional[tuple[str, tuple[Item, ...]]]:
    """The commit that first put the task in `backlog/tasks/`, and its criteria then.

    Found by the task's id in the file name, not by `git log --follow`: board files look
    alike, so git's rename and copy detection pairs one task with another.
    """
    log = git(
        root,
        "log",
        "--diff-filter=A",
        "--no-renames",
        "--relative",
        "--format=commit %H",
        "--name-only",
        "--",
        ":(glob)backlog/tasks/%s - *" % task.id.lower(),
    )
    if not log:
        return None
    added: list[tuple[str, str]] = []
    for line in log.splitlines():
        if line.startswith("commit "):
            added.append((line.split()[1], ""))
        elif line.strip() and added:
            added[-1] = (added[-1][0], line.strip())
    commit, path = added[-1]
    text = git(root, "show", "%s:./%s" % (commit, path))
    return (commit, parse_task(text, path).criteria) if text is not None and path else None


def committed_version(root: Path, task: Task) -> Optional[Task]:
    """The task as of the last commit, or None if its file was never committed."""
    text = git(root, "show", "HEAD:./%s" % task.path)
    return parse_task(text, task.path) if text is not None else None


def closing_findings(root: Path, board: Board, task: Task) -> list[Finding]:
    """What stops a task closing.

    Its criteria and children; a finish line changed since the last commit; and one
    moved since acceptance without the label. With no git history, only the first.
    """
    found = check_close(board, task)
    if not has_history(root):
        return found
    committed = committed_version(root, task)
    if committed is None:
        found.append(
            Finding(
                task.id,
                "close",
                "its file has never been committed: commit it before review, so the finish line "
                "it is judged against is on record",
            )
        )
        return found
    found += check_uncommitted(task, committed)
    found += check_repro(task, edited_repro_tests(root, task))
    version = accepted_version(root, task)
    if version is not None:
        commit, criteria = version
        found += check_moved(committed, criteria, commit)
        found += check_declared_checks(task, checks_changed_since(root, commit))
    return found


def repo_top(root: Path) -> Optional[Path]:
    top = (git(root, "rev-parse", "--show-toplevel") or "").strip()
    return Path(top) if top else None


def checks_changed_since(root: Path, commit: str) -> Optional[str]:
    """`commit` if the declared checks existed then and differ now, else None."""
    top = repo_top(root)
    if top is None or git(top, "cat-file", "-e", "%s:%s" % (commit, CHECKS_FILE)) is None:
        return None
    return commit if git(top, "diff", "--quiet", commit, "--", CHECKS_FILE) is None else None


def edited_repro_tests(root: Path, task: Task) -> dict[str, str]:
    """The repro test files that differ now from the commit they were last recorded at.

    A later repro of the same file replaces the earlier one.
    """
    top = (git(root, "rev-parse", "--show-toplevel") or "").strip()
    latest = {path: commit for commit, paths in repro_records(task.notes) for path in paths}
    return {
        path: commit
        for path, commit in latest.items()
        if top and git(Path(top), "diff", "--quiet", commit, "--", path) is None
    }


def has_history(root: Path) -> bool:
    return git(root, "rev-parse", "--verify", "-q", "HEAD") is not None


def accepted_versions(root: Path, board: Board) -> dict[str, tuple[str, tuple[Item, ...]]]:
    out = {}
    for task in board.tasks:
        if not is_draft(task):
            version = accepted_version(root, task)
            if version is not None:
                out[task.id] = version
    return out
