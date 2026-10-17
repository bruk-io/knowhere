"""Round 2: baseline vs reason+directive for two skills. Usage: variants2.py <skill> <variant> <plugin root>"""
import pathlib, re, sys
ADD = {
 "authoring-hooks": " Hook behaviour has traps Claude gets wrong from memory (which exit code blocks, matcher syntax, gates that fail open, plugin hook file shape), so load this before writing, reviewing or debugging any hook, even a small one.",
 "authoring-memory": " Memory loading has traps Claude gets wrong from memory (a CLAUDE.local.md can silently stop AGENTS.md loading, @imports do not save context, which files are never read), so load this before writing, reviewing or debugging any CLAUDE.md, CLAUDE.local.md or AGENTS.md, even a one-line change.",
}
skill, variant, root = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
p = root / "skills" / skill / "SKILL.md"
text = p.read_text()
m = re.search(r"^description: (>-\n(?:  .*\n)+|.*\n)", text, re.M)
raw = m.group(1)
desc = " ".join(l.strip() for l in raw[3:].splitlines()) if raw.startswith(">-") else raw.strip()
MEM_REASON = " Memory loading has traps Claude gets wrong from memory (a CLAUDE.local.md can silently stop AGENTS.md loading, @imports do not save context, which files are never read), so load this before "
VARIANTS = {
 "combined": lambda d: d + ADD[skill],
 # round 3, each one change from "combined" (memory only)
 "advise": lambda d: d + MEM_REASON + "writing, reviewing, debugging, planning or advising on changes to any CLAUDE.md, CLAUDE.local.md or AGENTS.md, even a one-line change.",
 "activity": lambda d: d + MEM_REASON + "writing, reviewing or debugging project memory, even a one-line change.",
}
if variant != "baseline":
    desc = VARIANTS[variant](desc)
text = text[:m.start()] + "description: '" + desc.replace("'", "''") + "'\n" + text[m.end():]
p.write_text(text)
print(skill, variant, len(desc))
