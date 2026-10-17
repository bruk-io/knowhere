import re, sys, pathlib
BASE = '''Use when the user wants something to happen on every tool call or lifecycle event without relying on the model - "block rm -rf", "stop Claude from ever running X", "run prettier after every edit", "lint after edits", "gate commits on tests", "inject context at session start", "back up before compaction" - or when a hook is not firing or not blocking. Also on any mention of PreToolUse / PostToolUse / Stop / SessionStart / PreCompact hooks, matchers, `if` filters or exit-code gating. Scaffolds and validates the config with a bundled tool.'''
V = {
 "v0-baseline": BASE,
 # 1. generalise: intent categories instead of a list of quoted example phrases
 "v1-categories": '''Use when the user wants something to happen on every tool call or lifecycle event without relying on the model - blocking or guarding commands, formatting or linting after edits, gating on tests, injecting context, or acting at session start, stop or compaction - or when a hook is not firing or not blocking. Also on any mention of PreToolUse / PostToolUse / Stop / SessionStart / PreCompact hooks, matchers, `if` filters or exit-code gating. Scaffolds and validates the config with a bundled tool.''',
 # 2. third person opening instead of "Use when"
 "v2-third-person": '''Builds and debugs Claude Code hooks: things that happen on every tool call or lifecycle event without relying on the model - "block rm -rf", "stop Claude from ever running X", "run prettier after every edit", "lint after edits", "gate commits on tests", "inject context at session start", "back up before compaction" - and hooks that are not firing or not blocking. Also on any mention of PreToolUse / PostToolUse / Stop / SessionStart / PreCompact hooks, matchers, `if` filters or exit-code gating. Scaffolds and validates the config with a bundled tool.''',
 # 3. say why to load it: what Claude gets wrong from memory
 "v3-why-load": BASE + ''' Hook behaviour has traps Claude gets wrong from memory (which exit code blocks, matcher syntax, gates that fail open, plugin hook file shape), so load this before writing, reviewing or debugging any hook, even a small one.''',
 # 4. drop the implementation tail
 "v3a-reason-only": BASE + ''' Hook behaviour has traps Claude gets wrong from memory (which exit code blocks, matcher syntax, gates that fail open, plugin hook file shape).''',
 "v3b-directive-only": BASE + ''' Load this before writing, reviewing or debugging any hook, even a small one.''',
 "v4-no-impl": BASE.replace(" Scaffolds and validates the config with a bundled tool.", ""),
}
name, root = sys.argv[1], pathlib.Path(sys.argv[2])
p = root / "skills/authoring-hooks/SKILL.md"
t = p.read_text()
t = re.sub(r"description: >-\n(  .*\n)+?(?=allowed-tools)", "description: '" + V[name].replace("'", "''") + "'\n", t, count=1)
p.write_text(t)
print(name, len(V[name]))
