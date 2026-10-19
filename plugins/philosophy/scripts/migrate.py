"""Move one piece of work from the old board layout to named intent, spec and plan files.

The old layout holds the intent as a task (`type: intent`), the spec as a doc linked by an
`Intent:` line and the intent's `documentation:` key, and the plan as a doc under
`backlog/docs/plans/`. The new layout holds them as `backlog/intents/<name>.md`,
`backlog/specs/<name>.md` and `backlog/plans/<name>.md`, and ties the tasks to the work with
a `<name>` label. `migrate-layout` is the command over this; the core takes the text of the
files and returns the changes, so it can be tested without a board on disk.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional

import board as b

TASK_FOLDERS = ("backlog/tasks/", "backlog/drafts/", "backlog/completed/")
DOCS = "backlog/docs/"


class Change(NamedTuple):
    """Write `text` to `path`, or delete `path` when `text` is None."""

    path: str
    text: Optional[str]


class Migration(NamedTuple):
    changes: tuple[Change, ...]
    notes: tuple[str, ...]
    todo: tuple[str, ...]


def quoted(value: str) -> str:
    return "'%s'" % value.replace("'", "''")


def add_to_list(head: str, key: str, value: str) -> str:
    """Add `value` to the YAML list `key` in frontmatter text, creating it if absent."""
    lines = head.split("\n")
    start = next(
        (i for i, line in enumerate(lines) if re.match(r"^%s:" % re.escape(key), line)), None
    )
    if start is None:
        return head + "\n%s:\n  - %s" % (key, value)
    rest = lines[start].split(":", 1)[1].strip()
    if rest == "[]":
        lines[start : start + 1] = ["%s:" % key, "  - %s" % value]
    elif rest.startswith("[") and rest.endswith("]"):
        lines[start] = "%s: [%s, %s]" % (key, rest[1:-1], value)
    else:
        end = start + 1
        while end < len(lines) and re.match(r"^\s+\S", lines[end]):
            end += 1
        lines.insert(end, "  - %s" % value)
    return "\n".join(lines)


def without_key(head: str, key: str) -> str:
    return re.sub(r"^%s:.*\n?" % re.escape(key), "", head + "\n", flags=re.M).rstrip("\n")


def edited_frontmatter(text: str, edit) -> str:
    found = b.FRONTMATTER.match(text.replace("\r\n", "\n"))
    if not found:
        raise ValueError("no frontmatter")
    return "---\n%s\n---\n%s" % (edit(found.group(1)), found.group(2))


def intent_text(task: b.Task, text: str) -> str:
    """The intent file for an intent task: its frontmatter, description, criteria and notes."""
    data, _ = b.parse_frontmatter(text)
    head = ["title: %s" % quoted(task.title), "status: %s" % (task.status or "Draft")]
    assignees = b.strings(data, "assignee")
    if assignees:
        head += ["assignee:"] + ["  - %s" % quoted(a) for a in assignees]
    if task.labels:
        head += ["labels:"] + ["  - %s" % label for label in task.labels]
    parts = ["---\n%s\n---\n" % "\n".join(head), task.description.strip("\n")]
    if task.criteria:
        done = "\n".join("- [%s] %s" % ("x" if c.ticked else " ", c.text) for c in task.criteria)
        parts.append("## Done when\n%s" % done)
    if task.notes.strip():
        parts.append("## Notes\n%s" % task.notes.strip())
    return "\n\n".join(parts).replace("\n\n\n", "\n\n") + "\n"


def named_text(doc: b.Doc, name: str, text: str) -> str:
    """A spec or plan doc as a plain file: a title, and no `Intent:` line."""
    data, body = b.parse_frontmatter(text)
    body = re.sub(r"\A\s*Intent:[ \t]*\S+[ \t]*\n", "", body, count=1)
    title = b.scalar(data, "title") or name
    return "---\ntitle: %s\n---\n%s\n" % (quoted(title), body.strip("\n"))


def migrate(
    files: dict[str, str],
    name: str,
    intent: Optional[str] = None,
    spec: Optional[str] = None,
    plan: Optional[str] = None,
) -> Migration:
    """The changes that move one piece of work to the new layout.

    `files` maps each task and doc path (relative to the repository, `backlog/...`) to its
    text. Raises LookupError when the intent, spec or plan cannot be told apart, because
    a guess here would move the wrong file.
    """
    if not b.NAME.match(name):
        raise LookupError(
            "%r is not a usable name: use lowercase words joined by hyphens, not starting like "
            "an id or a size or slice label, because it becomes a label on every task" % name
        )
    tasks = {
        path: b.parse_task(text, path)
        for path, text in files.items()
        if path.startswith(TASK_FOLDERS)
    }
    docs = {path: b.parse_doc(text, path) for path, text in files.items() if path.startswith(DOCS)}
    found = {p: t for p, t in tasks.items() if t.type == "intent"}
    if intent is not None:
        found = {p: t for p, t in tasks.items() if b.same_id(t.id, intent)}
    if len(found) != 1:
        raise LookupError(
            "found %d intent tasks (%s): name the one to move with --intent"
            % (len(found), ", ".join(t.id for t in found.values()) or "none")
        )
    ((intent_path, anchor),) = found.items()

    notes = ["intent %s -> backlog/intents/%s.md" % (anchor.id, name)]
    todo: list[str] = []
    changes = [Change("backlog/intents/%s.md" % name, intent_text(anchor, files[intent_path]))]

    linked = {
        p
        for p, d in docs.items()
        if any(b.links(d, entry) for entry in anchor.documentation)
        or re.search(r"^Intent:[ \t]*%s\b" % re.escape(anchor.id), d.body, re.M | re.I)
    }
    specs = [p for p in linked if "/plans/" not in p]
    if spec is not None:
        specs = [p for p, d in docs.items() if p == spec or b.same_id(d.id, spec)]
    if len(specs) > 1:
        raise LookupError(
            "%d docs look like the spec (%s): name it with --spec"
            % (len(specs), ", ".join(sorted(specs)))
        )
    plans = (
        [p for p in docs if "/plans/" in p]
        if plan is None
        else [p for p, d in docs.items() if p == plan or b.same_id(d.id, plan)]
    )
    if len(plans) > 1:
        raise LookupError(
            "%d docs under backlog/docs/plans (%s): name it with --plan"
            % (len(plans), ", ".join(sorted(plans)))
        )

    changes.append(Change(intent_path, None))
    if specs:
        changes += [
            Change("backlog/specs/%s.md" % name, named_text(docs[specs[0]], name, files[specs[0]])),
            Change(specs[0], None),
        ]
        notes.append("spec %s -> backlog/specs/%s.md" % (specs[0], name))
        if b.SPEC_APPROVED.search(anchor.notes) is None and any(
            not b.is_draft(t) and b.same_id(t.parent, anchor.id) for t in tasks.values()
        ):
            todo.append(
                "backlog/intents/%s.md has no 'Spec approved by @name' under '## Notes': add it "
                "if product approved the spec, since the check asks for the record" % name
            )
    else:
        todo.append("no spec found for %s: none moved" % anchor.id)
    if plans:
        text = named_text(docs[plans[0]], name, files[plans[0]])
        changes += [Change("backlog/plans/%s.md" % name, text), Change(plans[0], None)]
        notes.append("plan %s -> backlog/plans/%s.md" % (plans[0], name))
        if not b.slices(b.parse_named(text, "backlog/plans/%s.md" % name)):
            todo.append(
                "backlog/plans/%s.md has no numbered '## Slices' (each with 'Tester sees:'): "
                "reshape it, then label each task slice-n" % name
            )
    else:
        todo.append("no plan under backlog/docs/plans: write backlog/plans/%s.md" % name)

    pointer = "backlog/intents/%s.md" % name
    for path, task in tasks.items():
        if path == intent_path:
            continue
        if b.same_id(task.parent, anchor.id):

            def tie(head: str) -> str:
                head = without_key(head, "parent_task_id")
                head = add_to_list(head, "labels", name)
                return add_to_list(head, "references", pointer)

            changes.append(Change(path, edited_frontmatter(files[path], tie)))
            notes.append("%s: label %s, parent_task_id removed" % (task.id, name))
            if not task.labels or not any(b.SLICE_LABEL.match(label) for label in task.labels):
                todo.append("%s: add the slice-n label for the slice it comes from" % task.id)
        elif any(b.same_id(d, anchor.id) for d in task.dependencies):
            todo.append(
                "%s depends on %s, which no longer exists: point it at a task"
                % (task.id, anchor.id)
            )
    return Migration(tuple(changes), tuple(notes), tuple(todo))
