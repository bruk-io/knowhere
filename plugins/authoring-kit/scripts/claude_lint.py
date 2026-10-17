"""claude-lint - mechanical checks and reference data for Claude Code authoring artifacts.

Usage:
  claude-lint [--json] <path>...        lint files or directories (directories are walked)
  claude-lint [--json] --all [ROOT]     lint the whole tree at ROOT (default: cwd)
  claude-lint rules [--json]            list every rule with its reason, the numeric limits and
                                        the kind -> rule file / skill map (source of truth)
  claude-lint fields <skill|agent|rule> [FIELD] [--full] [--json]
                                        the frontmatter reference for one kind: a line per field
                                        (type or values, default, effect cut short), then notes;
                                        FIELD prints one field in full, --full the whole table
  claude-lint check-injection '<command>' [--allowed-tools '<value>'] [--plugin-skill] [--json]
                                        would this injection load? prints `loads` or `aborts`, which
                                        part fails and why, and the `Bash(...)` entry to add
                                        (exit 0 loads, 1 aborts)
  claude-lint drift [--json]            compare the tables above with the installed Claude Code
                                        (exit 0 no drift or not checkable, 1 drift)
  claude-lint classify <path>           print the artifact kind, or exit 1 if not an artifact
  claude-lint classify --extensions     print the file-name suffixes an artifact can have
  claude-lint hook                      hook mode: event JSON on stdin (PostToolUse on Read, Write
                                        and Edit; SessionStart resets rule delivery; PreToolUse
                                        on Bash holds the plugin's auditor agent to this linter)
  claude-lint install-rules [--target DIR] [--dry-run] [--check]
                                        copy the plugin's rules/*.md into DIR/.claude/rules/
                                        (always a copy: a symlinked rule is not loaded;
                                        --check only reports, exit 1 if a copy is missing
                                        or out of date)

Lint output: one finding per line on stdout as `path:line: SEV ID message`, or with
--json a single object {"findings": [...], "summary": {"error": n, "warn": n, "info": n}}.
Every message says what is wrong, why the rule exists and what to do.
Silent when clean. Exit 1 if any finding is an error, else 0; exit 2 on usage errors.
Diagnostics go to stderr.

Artifact kinds: skill (SKILL.md, commands), rule, agent, memory (CLAUDE.md,
CLAUDE.local.md, AGENTS.md), hooks, plugin. Anything else is skipped, as are .git
and node_modules. A path literally named like a subcommand must be written as
./rules, ./hook and so on.

A markdown artifact can opt out of specific rules with an HTML comment:
  <!-- claude-lint-disable SK012 RU005 -->

Python 3 standard library only; run through the claude-lint launcher. It is not on PATH: it ships in a
plugin's scripts/ directory, so run it by path with python3 -
  python3 "<plugin root>/scripts/claude-lint" --all .
and from inside one of that plugin's skills, agents or hooks -
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/claude-lint" ...
"""

import os
import sys

# Classification and the hook's payload gate live in claude_lint_gate.py,
# which the launcher can import alone (see that module).
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from claude_lint_gate import (  # noqa: E402
    KINDS,
    MEMORY_NAMES,
    ARTIFACT_SUFFIXES,
    _is_plugin_root,
    in_claude_dir,
    classify,
    HOOK_PEEK_BYTES,
    AUDITOR_AGENT,
    _AUDITOR_TAIL,
    _PRE_TOOL_LEADS,
    _FILE_PATH_LEADS,
    peek_file_path,
    read_hook_payload,
    hook_target,
)

_NOT_READ = object()         # the launcher did not read the payload (in-process use, tests)
_HOOK_STEP = _NOT_READ

import json  # noqa: E402
import re    # noqa: E402
from bisect import bisect_left  # noqa: E402
from dataclasses import dataclass  # noqa: E402

# ---- limits (the one place the numbers live; exposed by `rules --json`) -----

DESC_CAP = 1536              # description + when_to_use, characters
SKILL_BODY_MAX_LINES = 500   # SKILL.md body, excluding frontmatter
RULE_MAX_LINES = 200         # a rule file, whole file
MEMORY_MAX_LINES = 200       # CLAUDE.md / CLAUDE.local.md / AGENTS.md, whole file
IMPORT_MAX_HOPS = 4          # @import chain depth in memory files
AGENT_NAME_MAX = 256         # an agent `name`, characters
AGENT_SKILLS_MAX = 32        # preloaded `skills` names that load
PATHS_EXPANSION_MAX = 1000   # brace-expanded patterns over one rule's whole `paths` list

LIMITS = {
    "DESC_CAP": DESC_CAP,
    "SKILL_BODY_MAX_LINES": SKILL_BODY_MAX_LINES,
    "RULE_MAX_LINES": RULE_MAX_LINES,
    "MEMORY_MAX_LINES": MEMORY_MAX_LINES,
    "IMPORT_MAX_HOPS": IMPORT_MAX_HOPS,
    "AGENT_NAME_MAX": AGENT_NAME_MAX,
    "AGENT_SKILLS_MAX": AGENT_SKILLS_MAX,
    "PATHS_EXPANSION_MAX": PATHS_EXPANSION_MAX,
}

HOOK_MAX_FINDINGS = 20       # hook mode: findings shown before the "(+N more)" tail
HOOK_MAX_BYTES = 1024 * 1024 # hook mode: a larger file is not linted at write time (the hook has a 30 s timeout)
VERSION_TIMEOUT_S = 5
HOOKTOOL_TIMEOUT_S = 20

SKIP_DIRS = {".git", "node_modules"}
SEVERITIES = ("error", "warn", "info")
FALLBACK_PLUGIN_NAME = "claude-lint"   # used only when no plugin.json sits above this script


# The launcher users and hooks run. This module holds the code so that Python
# caches its bytecode; compiling it fresh on every hook call cost about 50 ms.
LAUNCHER = os.path.join(os.path.dirname(os.path.realpath(__file__)), "claude-lint")


def own_plugin_root():
    """The plugin this script ships in, found from the script's real path."""
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def self_command(*words):
    """A form of this linter's own command line that can be pasted into a
    shell: the script is not on PATH, so it is python3 plus its real path."""
    return " ".join(('python3', '"' + LAUNCHER + '"') + words)


def own_plugin_name(plugin_root=None):
    """The plugin's name as its own .claude-plugin/plugin.json states it, so a
    rename needs no change here. Falls back to FALLBACK_PLUGIN_NAME when the
    manifest is missing, unreadable or names nothing usable as a file prefix."""
    manifest = os.path.join(plugin_root or own_plugin_root(), ".claude-plugin", "plugin.json")
    try:
        with open(manifest, encoding="utf-8") as f:
            name = json.load(f).get("name")
    except (OSError, ValueError, AttributeError):
        name = None
    if isinstance(name, str) and re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", name):
        return name
    return FALLBACK_PLUGIN_NAME


# ---- rule table (listed by `claude-lint rules`) -----------------------------
#
# (id, severity, kind, check, why). `why` is the one-clause reason the rule
# exists; every finding message carries it, so a finding can be acted on
# without opening a rule file or a skill. The reasons come from the Claude
# Code docs and from what was observed (the tests record the observations).

RULES = [
    ("SK001", "error", "skill", "`name`, if present, matches ^[a-z0-9-]+$",
     "`name` is the command the user types, and the Agent Skills spec, which a claude.ai upload is validated "
     "against, allows only lowercase letters, digits and hyphens"),
    ("SK002", "warn", "skill", "`name`, if present, equals the skill's directory name",
     "`name` replaces the directory name as the command while the directory name keeps working, so the skill "
     "answers to two names; the Agent Skills spec requires the two to match"),
    ("SK003", "error", "skill", f"`description` + `when_to_use` combined is at most {DESC_CAP} characters",
     f"the skill listing truncates the pair at {DESC_CAP:,} characters, so trigger text past the cap is never seen"),
    ("SK004", "error", "skill", "not both `disable-model-invocation: true` and `user-invocable: false`",
     "one hides the skill from the model and the other from the user, so it can never run"),
    ("SK005", "error", "skill", "every injection directive survives its own failure (`|| echo ...`, or a pipe into "
                                "`head`); a non-zero exit aborts the skill load and `2>/dev/null` alone does not prevent that",
     "a command that exits non-zero aborts the whole skill load: Claude sees \"Shell command failed\", never the body"),
    ("SK006", "warn", "skill", "injected output looks bounded (no bare cat/find/git log/git diff without head or a limit)",
     "injected output is prompt content, and past the Bash tool's inline ceiling the body gets a file path and a "
     "preview instead of the data"),
    ("SK007", "warn", "skill", "no secret-looking literal (*KEY=, *TOKEN=, *SECRET=, PASSWORD=) on or next to an injection line",
     "injected output enters the prompt"),
    ("SK008", "warn", "skill", f"body is at most {SKILL_BODY_MAX_LINES} lines",
     "the rendered body stays in context for the whole session, and after compaction only the first 5,000 "
     "tokens of each skill are re-attached, most recently invoked first, within a 25,000-token budget shared "
     "by all skills, so an older skill can drop out entirely"),
    ("SK009", "error", "skill", "relative links, references/ and scripts/ paths, and @file references resolve on disk",
     "the body sends Claude to a file that is not there"),
    ("SK010", "error", "skill, rule, agent", "`Skill(<name>)` references resolve (bare or plugin-qualified)",
     "the reference names a skill that cannot be invoked"),
    ("SK012", "warn", "skill", "no documentation-looking grammar that the preprocessor will consume at load: a "
                               "placeholder injection (`command`, `<your-command>` and the like behind the `!`, or "
                               "a directive quoted inside a longer code span), or a substitution token that is being described (in a bolded code span, "
                               "or alone in a code span outside a value position - `$ARGUMENTS`, `$ARGUMENTS[N]`, a "
                               "`${CLAUDE_...}` variable, or `$0`/`$1` where the line is about arguments) rather than used. A real command "
                               "with no fallback is SK005 alone",
     "a skill body is a template: a directive or placeholder in it is executed or substituted at load, code "
     "spans included, so the reader gets its output instead of the syntax"),
    ("SK013", "warn", "skill", "every injection command passes the pre-load permission check: each part is read-only "
                               "or matched by a `Bash(...)` entry in `allowed-tools` (anything else aborts the skill "
                               "load). A read-only command stops being one with an option that writes or runs something "
                               "(`sort -o`, `git diff --output=`), and a path with a `..` component is not approved",
     "injections never prompt: every part is checked against the permission rules before the skill loads, and "
     "anything short of an allow aborts the load"),
    ("SK015", "warn", "skill", "no documentation-looking `@path` that is attached as a file at load: outside an inline "
                               "code span that it opens, an at-sign path after whitespace is attached, fenced blocks "
                               "included, if a file or directory of that name exists in the session's working "
                               "directory then (a `#L<n>` or `#L<n>-<m>` suffix attaches those lines). A warn when the "
                               "path resolves from the project root, the plugin root or beside the skill; an info when "
                               "it only has the shape of a file name and the linter cannot see the working directory",
     "an at-sign path attaches that file from the session's working directory when the skill loads, so an "
     "example can attach whatever happens to match in the user's project"),
    ("SK016", "info", "skill", "`description` / `when_to_use` does not key the trigger on which file is being touched "
                               "(a file-action verb beside a path-like token: \"when editing any SKILL.md\"); a file "
                               "the user mentions or provides is a request, not a file key",
     "whether this loads when that file is touched is left to the model's judgement; a path-scoped rule or a "
     "hook is guaranteed"),
    ("SK017", "warn", "skill", "every frontmatter field is one Claude Code reads for a skill (`claude-lint fields skill`); "
                               "in a `.claude/commands/` file, also not `name` or `paths`",
     "an unrecognised field is ignored without an error, so a typo fails silently"),
    ("SK018", "warn", "skill", "`effort`, `context` and `shell` hold a value from their documented set "
                               "(`effort` may also be an integer)",
     "a value outside the set is not applied: the field behaves as if it were unset, and at most a debug-log "
     "line says so"),
    ("RU001", "warn", "rule", f"file is at most {RULE_MAX_LINES} lines",
     "a rule is paid in full on every load, and files over 200 lines consume more context and reduce adherence"),
    ("RU002", "error", "rule", "no live skill-body grammar outside code spans (injection directives, $ARGUMENTS, ${...})",
     "none of the skill-body grammar applies in a rule: it arrives as literal text, without warning"),
    ("RU003", "warn", "rule", "no numbered procedure steps - rules are declarative",
     "a rule states constraints; one that has grown numbered steps is a skill waiting to be extracted"),
    ("RU004", "warn", "rule", "first body line after the H1 is an \"Applies when/to ...\" sentence",
     "one opening line saying when the rule applies serves both Claude and reviewers"),
    ("RU005", "warn", "rule", "has `paths:` frontmatter (opt out for a deliberately global rule with claude-lint-disable)",
     "without `paths` a rule loads at launch in every session, so an unscoped rule taxes all of them"),
    ("RU006", "error", "rule", "`paths:` is a glob or a well-formed YAML list of globs, quoted or plain; a glob that "
                               "starts with `*`, `[`, `{`, `!` or `&` is quoted (it is not valid YAML otherwise); every "
                               "`[` is closed (a warn); and brace expansion over the whole list stays within "
                               f"{PATHS_EXPANSION_MAX:,} patterns (a warn)",
     "frontmatter that fails to parse is dropped and the rule then loads in every session, silently; a glob "
     f"with an unbalanced `[` matches nothing; and a rule's whole list shares a budget of {PATHS_EXPANSION_MAX:,} "
     "expanded patterns"),
    ("RU007", "warn", "rule", "no at-sign import outside a code span: it expands, relative to the rule file "
                              "(one that does not resolve imports nothing)",
     "an import pulls the whole target in on every load of the rule"),
    ("AG001", "error", "agent", f"`name` and `description` present; `name` is at most {AGENT_NAME_MAX} characters, has "
                                "no `:` and no leading `-`; `name` matches ^[a-z0-9-]+$ (a warn: convention only)",
     "Claude Code skips an agent file silently when `name` or `description` is missing, and with a debug-log "
     f"error when `name` starts with `-`, contains `:` (reserved for plugin namespacing) or is over {AGENT_NAME_MAX} "
     "characters"),
    ("AG002", "error", "agent", "body has no skill-body grammar outside code spans (agents are not preprocessed; a "
                                "plugin-distributed agent's body expands only ${CLAUDE_PLUGIN_ROOT}, "
                                "${CLAUDE_PLUGIN_DATA} and ${CLAUDE_PROJECT_DIR}, which are allowed there)",
     "an agent body is a static system prompt: injection directives and placeholders written into one arrive as "
     "literal text"),
    ("AG003", "warn", "agent", "`background: true` implies `maxTurns` is set",
     "`maxTurns` is the runaway guard for an agent nobody is watching"),
    ("AG004", "warn", "agent", f"preloaded `skills:` resolve, none is `disable-model-invocation: true`, and there are at "
                               f"most {AGENT_SKILLS_MAX}",
     "a missing or disabled skill is skipped with only a debug-log warning, and only the first "
     f"{AGENT_SKILLS_MAX} names are preloaded"),
    ("AG005", "warn", "agent", "a plugin-distributed agent declares no `hooks`, `mcpServers`, `permissionMode` or "
                               "`initialPrompt` (all four are ignored there)",
     "Claude Code ignores these fields on a plugin-distributed agent, so a role that depends on them does not get them"),
    ("AG006", "warn", "agent", "no permission specifier on a `tools` entry, such as `Bash(git log *)`: it grants the "
                               "whole tool and restricts nothing (`Agent(type, ...)` is the one documented form); and none "
                               "on a `disallowedTools` entry, such as `Bash(git push *)`: it removes the whole tool, not "
                               "only the matching calls",
     "both fields are tool-level, not command-level: a specifier neither narrows a grant nor narrows a removal"),
    ("AG007", "info", "agent", "`description` does not key delegation on which file is being touched (a file-action "
                               "verb beside a path-like token); a file the user mentions or provides is a request, "
                               "not a file key",
     "whether this loads when that file is touched is left to the model's judgement; a path-scoped rule or a "
     "hook is guaranteed"),
    ("AG008", "warn", "agent", "every frontmatter field is one Claude Code reads for an agent (`claude-lint fields agent`)",
     "an unrecognised field is ignored without an error, so a typo fails silently"),
    ("AG009", "warn", "agent", "`color`, `effort`, `permissionMode`, `memory`, `isolation` and a `model` alias hold a "
                               "value from their documented set (`effort` may be an integer; a full model id and "
                               "`inherit` pass)",
     "a value outside the set is not applied: the field behaves as if it were unset (an unknown `model` word "
     "is taken as a full model id), and at most a debug-log line says so"),
    ("AG010", "warn", "agent", "no two agent files in one scope directory declare the same `name`",
     "Claude Code loads only one of them, picked by filesystem read order, and silently discards the other"),
    ("CM001", "warn", "memory", f"file is at most {MEMORY_MAX_LINES} lines",
     "it is paid on every session and longer files dilute adherence (Claude Code skips an instruction file "
     "over 4 MiB outright)"),
    ("CM002", "error", "memory", f"@import paths resolve and the chain is at most {IMPORT_MAX_HOPS} hops deep "
                                 "(punctuation directly after a path is read as part of it, so `@a.md.` imports nothing; "
                                 "a quoted path is not imported - an info)",
     "an import that does not resolve imports nothing and nothing says so, and Claude Code follows imports only "
     f"{IMPORT_MAX_HOPS} hops deep"),
    ("CM003", "warn", "memory", "no numbered procedure steps - memory is declarative (not applied to AGENTS.md, "
                                "which is shared with other tools)",
     "project memory holds facts and standing instructions; a multi-step procedure is a skill"),
    ("CM004", "warn", "memory", "an AGENTS.md is not silently unread: a non-empty CLAUDE.md, .claude/CLAUDE.md or "
                                "CLAUDE.local.md beside or above it imports it or is a symlink to it, or a "
                                ".claude/rules/ file there imports it",
     "Claude Code reads AGENTS.md only when there is no CLAUDE.md in the working directory or above it"),
    ("HK001", "error", "hooks", "hook config passes `hooktool.py validate` (its errors are errors, its warnings are warns)",
     "a malformed hook is ignored or never fires, and nothing says so at run time; each hooktool message gives "
     "its own reason"),
    ("PL001", "error", "plugin", "`.claude-plugin/plugin.json` is valid JSON with a `name`",
     "`name` is the one required manifest field: it is the plugin's identity and the prefix of every skill "
     "and agent it ships"),
    ("PL002", "warn", "plugin", "each `skills/*/` directory has a SKILL.md (name/dir agreement is SK002)",
     "a skill is discovered by its SKILL.md, so a directory without one ships nothing"),
    ("PL003", "warn", "plugin", "no dead relative markdown links in the plugin's .md files (SKILL.md links are SK009)",
     "the link sends the reader to a file that is not there"),
    ("PL004", "error", "plugin", "`name` is not reserved: it does not start with claude-, anthropic-, anthropics- or "
                                 "cc-plugin-, is not claude, anthropic, anthropics, claude-code or claude-mods, and does "
                                 "not put \"official\" beside claude or anthropic (a warn when claude, anthropic or "
                                 "anthropics is a whole word elsewhere in it)",
     "`claude plugin validate` fails on a reserved name"),
    ("PL005", "warn", "plugin", "`name` is kebab-case (lowercase letters, digits, single hyphens) with no spaces",
     "`claude plugin validate` rejects whitespace in a name, and marketplace sync requires kebab-case"),
    ("PL006", "error", "plugin", "`version` is a string, `author` an object and `keywords` an array, when present",
     "`claude plugin validate` rejects any other type"),
    ("PL007", "warn", "plugin", "the plugin root has no top-level `bin/` directory (claude.ai and Cowork do not "
                                "install a plugin that has one)",
     "claude.ai and Cowork do not install a plugin that has a `bin/` directory"),
]
RULE_SEVERITY = {r[0]: r[1] for r in RULES}
RULE_WHY = {r[0]: r[4] for r in RULES}

NAME_RE = re.compile(r"^[a-z0-9-]+$")

# The two patterns Claude Code itself uses to find injection directives in a
# skill body (read out of the 2.1.295 binary). Inline directives need start of
# line or whitespace before the `!`, so `\!` is never a directive.
FENCED_DIRECTIVE_RE = re.compile(r"```!\s*\n?([\s\S]*?)\n?```")
INLINE_DIRECTIVE_RE = re.compile(r"(?:^|(?<=\s))!`([^`]+)`", re.M)

PLACEHOLDER_WORDS = {"command", "cmd", "...", "…", "your-command", "some-command"}
ANGLE_PLACEHOLDER_RE = re.compile(r"<[a-z][a-z0-9 _-]*>")
UNBOUNDED_RE = re.compile(
    r"(?:^|[\s;&|(])(cat|find|tree|git\s+log|git\s+diff|ls\s+-[A-Za-z]*R|grep\s+-[A-Za-z]*r)(?=\s|$)")
BOUNDED_RE = re.compile(
    r"\b(?:head|tail|wc|cut)\b|--max-count|-maxdepth|--stat\b|--name-only|--shortstat|"
    r"(?:^|\s)-n\s*\d+|(?:^|\s)-m\s*\d+|(?:^|\s)-\d+\b|sed\s+-n")
SECRET_RE = re.compile(
    r"\b[A-Za-z0-9_]{0,64}(?:KEY|TOKEN|SECRET|PASSWORD)\s*=\s*[\"']?(?![$\s\"'<]|\{\{)[^\s]")

# What the skill preprocessor substitutes in a body (all observed on 2.1.295).
SUBSTITUTED_VARS = ("CLAUDE_SESSION_ID", "CLAUDE_EFFORT", "CLAUDE_SKILL_DIR", "CLAUDE_PLUGIN_ROOT",
                    "CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR")
BRACED_TOKEN = r"\$\{(?:" + "|".join(SUBSTITUTED_VARS) + r")\}"
ARG_TOKEN = r"\$ARGUMENTS(?:\[\w+\])?|\$\d+\b"
SUBSTITUTION_TOKEN = ARG_TOKEN + "|" + BRACED_TOKEN
# SK012 heuristics - a token that is being talked about rather than used:
DOC_TOKEN_RE = re.compile(r"\*\*`[^`\n]*?(" + SUBSTITUTION_TOKEN + r")[^`\n]*`")       # bolded code span
# The token alone in a code span. OBSERVED on 2.1.295: "Use `$ARGUMENTS` to
# pass" loaded with no arguments as "Use `` to pass"; `$ARGUMENTS[0]` and `$0`
# in spans stayed literal on that run (they are replaced when arguments are
# given) and `${CLAUDE_SESSION_ID}` in a span was replaced.
BARE_TOKEN_SPAN_RE = re.compile(r"(?<!`)`(\$ARGUMENTS(?:\[\w+\])?|" + BRACED_TOKEN + r")`(?!`)")
# OBSERVED on 2.1.296 (one run, invoked with "alpha beta"): "The placeholder
# `$1` expands to the second argument and `$0` to the first" loaded as "The
# placeholder `beta` expands ... and `alpha` to the first".
# `$0` or `$1` alone in a span is as often awk or shell as it is a placeholder,
# so it counts only where the same line is talking about arguments in words
# (a `$ARGUMENTS` beside it is a use: "Fix $ARGUMENTS on the branch `$1`").
BARE_INDEX_SPAN_RE = re.compile(r"(?<!`)`(\$\d)`(?!`)")
ARGUMENT_TALK_RE = re.compile(r"(?<!\$)\b(?:arguments?|placeholders?|positional|substitut\w+|expands?|"
                              r"expanded|replaced)\b", re.I)
ARG_ALTERNATIVES_RE = re.compile(r"(?<!`)`(" + ARG_TOKEN + r")`\s*/\s*`(?:" + ARG_TOKEN + r")`(?!`)")
NEGATED_ARG_RE = re.compile(r"\b[Nn]o\s+`(" + ARG_TOKEN + r")`(?!`)")
ESCAPED_EXAMPLE_RE = re.compile(r"\\!`[^`\n]*?(" + SUBSTITUTION_TOKEN + r")[^`\n]*`")
VALUE_LEAD_RE = re.compile(r"(?::|\b(?:at|in|under|inside|from|into|to|is))\s*$")
GLOSS_FOLLOWS_RE = re.compile(r"\s*(?:\(|-\s|\u2014|\u2013)")

LIVE_TOKEN_RE = re.compile(r"\$ARGUMENTS\b|\$\{[A-Za-z_][A-Za-z0-9_]*\}")
SKILL_REF_RE = re.compile(r"\bSkill\(([A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?)\)")
SKILL_REF_PLACEHOLDERS = {"name", "skill", "skill-name", "plugin:name", "plugin:skill"}
# Link text is capped so a line of thousands of unclosed brackets stays linear.
# A link whose target has a space renders as plain text, not a link, so the
# main pattern skips it; a spaced target naming a file is still a broken link.
MD_SPACED_LINK_RE = re.compile(r"\[[^\]\n]{0,400}\]\(\s*([^()<>\"'\n]*?\s[^()<>\"'\n]*?\.[A-Za-z0-9]{1,8})\s*\)")
MD_LINK_RE = re.compile(r"\[[^\]\n]{0,400}\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"'\n]*[\"'])?\s*\)")
BUNDLED_PATH_RE = re.compile(r"(?<![\w./-])(\$\{CLAUDE_SKILL_DIR\}/)?((?:references|scripts)/[\w./-]*\w)")
AT_REF_RE = re.compile(r"(?:^|(?<=\s))@((?:\./|references/|scripts/)[\w./-]*\w)")
# SK015 - what the skill loader treats as a file reference. OBSERVED on Claude
# Code 2.1.295 (2026-10-09) with probe skills whose body named marker files in
# the session's working directory, 38 shapes, each run twice with the same
# result (the rows are AT_OBSERVED in the tests):
#   * an `@` at the start of a line or after whitespace starts a reference; it
#     runs to the next whitespace, less any trailing punctuation. `@"a b.txt"`
#     is the quoted form. The file's content (a directory's listing) is
#     attached when the skill loads.
#   * markdown does not protect it: a fenced block (backtick or tilde), an
#     indented block, an HTML comment, a list item, a heading and a blockquote
#     were all live, as was a code span in which the `@` follows a word or a
#     space (`cat @x.txt`).
#   * an `@` directly after anything else is inert: a backtick (so a code span
#     that the `@` opens is safe), `(`, `[`, `"`, `:`, `*` or a letter - which
#     is why e-mail addresses, `import x from "@/lib"` and `**@x**` are not
#     references.
#   * the path resolves against the session's working directory, never the
#     skill's own directory; an absolute path works, and ${CLAUDE_SKILL_DIR}
#     is substituted first, so `@${CLAUDE_SKILL_DIR}/references/x.md` attached
#     the bundled file. A path that does not exist attaches nothing.
#   * the shape of the name is irrelevant: `@README`, `@scope/pkg`, `@octocat`
#     and a `@dataclass` line in a python fence each attached the file of that
#     name when one existed. `@app.route('/x')` did not (no such file).
# Re-probed the same day (15 more shapes, twice each, asking the model to list
# every token it could see):
#   * nothing is attached when nothing of that name exists: `@README` with no
#     README (a README.md beside it does not count - the name is taken
#     exactly) and `@nonexistent-file.md` both loaded with nothing added.
#   * a `#L<n>` or `#L<n>-<m>` suffix is part of the reference and attaches
#     only those lines: `@notes.md#L1-2` gave lines 1 and 2, `#L2` line 2,
#     `#L2-3.` lines 2 and 3 (the full stop is dropped), in a fenced block too;
#     `#L9` on a three-line file attached nothing. Any other fragment
#     (`#heading`, and `#L2-L3` in two runs of four) attached the whole file.
#   * a directory name, `@docs` or `@docs/`, attached the directory's listing
#     (file names, not their content).
AT_FILE_RE = re.compile(r"(?:^|(?<=\s))@(?:\"([^\"\n]+)\"|(\S*\w))", re.M)
AT_FRAGMENT_RE = re.compile(r"(?<=.)#[\w-]*$")
AT_PATHISH_RE = re.compile(r"^[\w./~ -]+$")
# The linter cannot see the session's working directory, so outside a project
# it looks where it can - the plugin root and beside the skill - and warns
# when the name resolves there. A name that resolves nowhere is an `info`, and
# only when it has the shape of a file: an explicit ./ or ../, or one of these
# extensions. Decorators, handles and npm scopes have none of them, and a bare
# name with no extension (`@README`, `@Makefile`) is reported only when
# something of exactly that name exists.
AT_KNOWN_EXT = frozenset("""
    md mdx txt rst json jsonl yaml yml toml ini cfg conf lock csv tsv xml html htm css scss js jsx mjs cjs
    ts tsx py rb go rs java kt swift c h cc cpp hpp cs php sh bash zsh sql graphql proto tf log pdf png jpg
    jpeg gif svg ipynb
""".split())
# Agent `tools` entries: a permission specifier in parentheses. OBSERVED on
# 2.1.295: `Bash(some-command *)` in an agent's tools grants all of Bash and
# pre-approves nothing. `Agent(type, ...)` is documented and does restrict
# (which subagent types may be spawned); Task is that tool's earlier name.
# `disallowedTools` is DOCUMENTED (https://code.claude.com/docs/en/sub-agents,
# "Available tools", read 2026-10-09): "A `disallowedTools` entry with a
# specifier, such as `Bash(git push *)`, still removes the whole tool from the
# subagent, not only the matching commands."
DISALLOWED_DOC_QUOTE = "still removes the whole tool from the subagent, not only the matching commands"
TOOL_SPECIFIER_RE = re.compile(r"(?<![\w-])([A-Za-z_][\w-]*)\(([^()]*)\)")
TOOLS_WITH_REAL_SPECIFIERS = frozenset({"Agent", "Task"})
# What a plugin-distributed agent's body has expanded (documented; a project
# or user agent's body showed the literals when probed).
PLUGIN_AGENT_VARS = frozenset({"${CLAUDE_PLUGIN_ROOT}", "${CLAUDE_PLUGIN_DATA}", "${CLAUDE_PROJECT_DIR}"})
PLUGIN_AGENT_IGNORED = ("hooks", "mcpServers", "permissionMode", "initialPrompt")
CLAUDE_MD_PLACES = ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md"), "CLAUDE.local.md")
BIN_DOC_QUOTE = "claude.ai and Cowork don't install a plugin that has this directory"
# Memory imports (CM002, CM004). OBSERVED on Claude Code 2.1.295, 2026-10-09:
# a project with an AGENTS.md holding a random passphrase and a CLAUDE.md of
# "# Project / Use tabs." plus one line, asked headless for the passphrase; 36
# shapes, two or three runs each, every run of a shape agreeing (the rows are
# IMPORT_OBSERVED in the tests).
#   * an `@path` imports at the start of a line, after whitespace (mid-
#     sentence, list item, nested and numbered list items, blockquote,
#     heading, table cell, after a tab) and directly inside bold, italic or a
#     link's text (`**@AGENTS.md**`, `*@AGENTS.md*`, `[@AGENTS.md](url)`).
#   * the path runs to the next whitespace and is taken literally: trailing
#     punctuation belongs to it, so `See @AGENTS.md.`, `@AGENTS.md,`, `:`, `;`
#     and `(see @AGENTS.md)` import nothing - silently. A `#fragment` is the
#     exception: `@AGENTS.md#intro` imported the file.
#   * nothing is imported from an inline code span, a fenced or indented code
#     block, an HTML comment (alone on a line, across lines or inside a
#     sentence) or straight after a double quote.
#   * a relative path resolves against the importing file's own directory -
#     so a rule in .claude/rules/ imports the project's AGENTS.md as
#     `@../../AGENTS.md`, not `@AGENTS.md` - and rules do expand imports, a
#     path-scoped rule's included.
IMPORT_RE = re.compile(r"(?:^|(?<=[\s*\[]))@([^\s*\]]+)", re.M)
IMPORT_TRAILING = ".,;:!?)\"'"
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
LIST_ITEM_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s")
NUMBERED_RE = re.compile(r"^\s{0,3}\d+\.\s")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
DISABLE_RE = re.compile(r"<!--\s*claude-lint-disable\s+([A-Z0-9,\s]+?)\s*-->")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def eprint(*args):
    print(*args, file=sys.stderr)


# ---- findings ---------------------------------------------------------------

class Finding:
    __slots__ = ("path", "line", "id", "severity", "message")

    def __init__(self, path, line, rule_id, message, severity=None):
        self.path = path
        self.line = line if isinstance(line, int) and line > 0 else 1
        self.id = rule_id
        self.severity = severity or RULE_SEVERITY[rule_id]
        self.message = message

    def as_dict(self):
        return {"path": self.path, "line": self.line, "id": self.id,
                "severity": self.severity, "message": self.message}

    def as_line(self):
        return f"{self.path}:{self.line}: {self.severity} {self.id} {self.message}"

    def key(self):
        return (self.path, self.line, self.id, self.severity, self.message)


def display_path(abspath):
    """Path as shown in findings: relative to cwd when underneath it."""
    cwd = os.getcwd()
    try:
        rel = os.path.relpath(abspath, cwd)
    except ValueError:
        return abspath
    return abspath if rel == ".." or rel.startswith(".." + os.sep) else rel


# ---- frontmatter (small tolerant YAML subset) -------------------------------

class Frontmatter:
    def __init__(self):
        self.present = False
        self.data = {}        # key -> str | bool | int | None | list | dict
        self.lines = {}       # key -> 1-based line number of the key
        self.raw = {}         # key -> raw scalar text, or list of raw item texts
        self.rest = {}        # key -> the text after `key:` on the key's own line
        self.errors = []      # (line, message)
        self.body = ""
        self.body_line = 1    # 1-based line number of the first body line

    def get(self, key, default=None):
        return self.data.get(key, default)

    def line(self, key):
        return self.lines.get(key, 1)


def _strip_comment(s):
    """Drop a trailing YAML comment: a `#` at the start or after whitespace,
    outside quotes."""
    quote, escaped, prev = None, False, " "
    for i, c in enumerate(s):
        if quote:
            if escaped:
                escaped = False
            elif c == "\\" and quote == '"':
                escaped = True
            elif c == quote:
                quote = None
        elif c in "\"'" and prev in " \t[,{:":
            quote = c
        elif c == "#" and prev in " \t":
            return s[:i].rstrip()
        prev = c
    return s


def _is_quoted(raw):
    return len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'"


def _scalar(raw):
    """Parse one YAML scalar. Returns (value, cleaned_raw)."""
    s = raw.strip()
    if s[:1] in ("\"", "'"):
        q = s[0]
        i, out = 1, []
        while i < len(s):
            c = s[i]
            if q == "\"" and c == "\\" and i + 1 < len(s):
                out.append({"n": "\n", "t": "\t"}.get(s[i + 1], s[i + 1]))
                i += 2
                continue
            if c == q:
                if q == "'" and s[i + 1:i + 2] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out), s[:i + 1]
            out.append(c)
            i += 1
        return s[1:], s  # unterminated quote: be tolerant
    s = _strip_comment(s)
    low = s.lower()
    if low in ("true", "false"):
        return low == "true", s
    if low in ("null", "~", ""):
        return None, s
    if re.match(r"^-?\d+$", s):
        return int(s), s
    return s, s


def _split_flow(inner):
    items, cur, quote, escaped = [], [], None, False
    for c in inner:
        if quote:
            cur.append(c)
            if escaped:
                escaped = False
            elif c == "\\" and quote == '"':
                escaped = True
            elif c == quote:
                quote = None
        elif c in "\"'":
            quote = c
            cur.append(c)
        elif c == ",":
            items.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    tail = "".join(cur).strip()
    if tail:
        items.append(tail)
    return items


def _block_scalar(indicator, children):
    lines = [c.rstrip() for c in children]
    indents = [len(c) - len(c.lstrip()) for c in lines if c.strip()]
    cut = min(indents) if indents else 0
    lines = [c[cut:] if c.strip() else "" for c in lines]
    while lines and not lines[-1]:
        lines.pop()
    if indicator.startswith("|"):
        text = "\n".join(lines)
    else:
        out, prev_blank = [], True
        for ln in lines:
            if not ln:
                out.append("\n")
                prev_blank = True
            else:
                if not prev_blank:
                    out.append(" ")
                out.append(ln)
                prev_blank = False
        text = "".join(out)
    if "-" not in indicator and text:
        text += "\n"
    return text


def parse_frontmatter(text):
    fm = Frontmatter()
    text = text.lstrip("\ufeff")
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        fm.body = text
        return fm
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() in ("---", "...")), None)
    if end is None:
        fm.errors.append((1, "frontmatter opened with --- but never closed"))
        fm.body = text
        return fm
    fm.present = True
    fm.body = "\n".join(lines[end + 1:])
    fm.body_line = end + 2
    block = lines[1:end]
    i = 0
    while i < len(block):
        line = block[i]
        lineno = i + 2
        if not line.strip() or line.lstrip().startswith("#") or line[0] in " \t":
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?:\s+(.*))?$", line.rstrip())
        if not m:
            fm.errors.append((lineno, f"cannot parse frontmatter line: {line.strip()[:60]}"))
            i += 1
            continue
        key, rest = m.group(1), (m.group(2) or "").strip()
        if not rest.startswith(("\"", "'")):
            rest = _strip_comment(rest)
        fm.rest[key] = rest
        j = i + 1
        children = []
        while j < len(block):
            nxt = block[j]
            if not nxt.strip() or nxt[0] in " \t" or (not rest and re.match(r"^-(\s|$)", nxt)):
                children.append(nxt)
                j += 1
            else:
                break
        if rest.startswith("[") and "]" not in rest + "".join(children):
            # a flow list whose closing bracket sits at column 0 on a later line
            while j < len(block) and "]" not in "".join(children):
                children.append(block[j])
                j += 1
        while children and not children[-1].strip():
            children.pop()
            j -= 1
        fm.lines[key] = lineno
        if re.match(r"^[>|][+-]?\d*$", rest):
            fm.data[key] = _block_scalar(rest, children)
            fm.raw[key] = rest
        elif rest.startswith("["):
            flow = rest + " " + " ".join(c.strip() for c in children)
            flow = flow.strip()
            if not flow.endswith("]"):
                fm.errors.append((lineno, f"`{key}`: inline list is not closed with ]"))
                inner = flow[1:]
            else:
                inner = flow[1:-1]
            raws = _split_flow(inner)
            fm.data[key] = [_scalar(r)[0] for r in raws]
            fm.raw[key] = [_scalar(r)[1] for r in raws]
        elif rest.startswith("{"):
            fm.data[key] = {"_inline": rest}
            fm.raw[key] = rest
        elif rest:
            joined = " ".join([rest] + [c.strip() for c in children if c.strip()])
            fm.data[key], fm.raw[key] = _scalar(joined)
        else:
            kids = [c for c in children if c.strip() and not c.lstrip().startswith("#")]
            if not kids:
                fm.data[key], fm.raw[key] = None, ""
            elif re.match(r"^-(\s|$)", kids[0].lstrip()):
                base = len(kids[0]) - len(kids[0].lstrip())
                raws = [k.strip()[1:].strip() for k in kids
                        if len(k) - len(k.lstrip()) == base and re.match(r"^-(\s|$)", k.lstrip())]
                fm.data[key] = [_scalar(r)[0] for r in raws]
                fm.raw[key] = [_scalar(r)[1] for r in raws]
            else:
                base = min(len(k) - len(k.lstrip()) for k in kids)
                nested = {}
                for k in kids:
                    km = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", k.strip())
                    if km and len(k) - len(k.lstrip()) == base:
                        nested[km.group(1)] = _scalar(km.group(2))[0] if km.group(2) else True
                fm.data[key] = nested or {"_nested": True}
                fm.raw[key] = ""
        i = j
    return fm


# ---- text helpers -----------------------------------------------------------

def mask_fences(text):
    """Blank out fenced code blocks (fence lines included), keeping line count."""
    out, fence = [], None
    for line in text.split("\n"):
        m = FENCE_RE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
                out.append("")
            else:
                out.append(line)
        else:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                    and not line.strip()[len(m.group(1)):].strip():
                fence = None
            out.append("")
    return "\n".join(out)


def mask_spans(text, min_ticks=1):
    """Replace inline code spans delimited by at least min_ticks backticks with spaces."""
    def repl(m):
        return " " * len(m.group(0)) if len(m.group(1)) >= min_ticks else m.group(0)
    return "\n".join(SPAN_RE.sub(repl, ln) for ln in text.split("\n"))


_NEWLINES = {}       # id(text) -> (text, offsets of its newlines); a handful of entries


def line_of(text, offset, first_line=1):
    """The line `offset` is on. The newline offsets of a text are found once
    and searched after that: counting from the start for every hit made a
    file with many directives quadratic."""
    hit = _NEWLINES.get(id(text))
    if hit is None or hit[0] is not text:
        if len(_NEWLINES) >= 8:
            _NEWLINES.clear()
        offsets, at = [], text.find("\n")
        while at >= 0:
            offsets.append(at)
            at = text.find("\n", at + 1)
        hit = _NEWLINES[id(text)] = (text, offsets)
    return first_line + bisect_left(hit[1], offset)


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def disabled_ids(text):
    ids = set()
    for m in DISABLE_RE.finditer(text):
        ids.update(x for x in re.split(r"[,\s]+", m.group(1)) if x)
    return ids


# ---- injection permission model (SK005, SK013) -------------------------------
#
# OBSERVED, not documented. Everything in this section encodes what happened
# when probe skills were loaded headless on Claude Code 2.1.295 on 2026-10-09
# (`claude -p ... --plugin-dir <probe> --allowedTools Skill`, default
# permission mode, no Bash allow rules in any settings file; 583 probes, 100
# of them held out and predicted in advance - 93 of those matched, and the
# seven that did not are folded in below).
# Re-run the probes before trusting it on a much newer version.
#
# The check, as observed:
#   * Before a skill body loads, each injection command is split into its
#     operations (at ||, &&, ;, |, newlines) and every operation is checked.
#     One operation that needs approval aborts the whole load ("Shell command
#     permission check failed"). A pipeline needs every stage to pass.
#   * An operation passes with NO entry when it is one of Claude Code's
#     read-only commands (AUTO_ALLOWED and friends below). echo and printf are
#     only two of many: date, pwd, ls, cat, head, grep, find, most read-only
#     git subcommands and more pass too. `claude --version`, `gh`, `npm`,
#     `jq --version`, `env`, `:`, and anything that writes do not.
#   * A read-only command still fails when it reads a path outside the
#     session's working directories (an absolute path, ~, or a plugin's own
#     ${CLAUDE_SKILL_DIR}/${CLAUDE_PLUGIN_ROOT}), and a matching entry such as
#     Bash(cat *) does not rescue it. test/[ are exempt.
#   * The same goes for a relative path with a `..` component (a second round,
#     235 more probes the same day, each in its own directory with a sibling
#     `../other`): `head -3 ../other/README.md` fails, and so do `ls ..`,
#     `cat ./a/../b` and `head -3 sub/../README.md`, which never leave the
#     directory - a `..` after a directory name is not resolved. `Bash(head *)`
#     rescued none of them. `..proj`, `b..` and `x/..y` are ordinary names.
#     The one form that passed is `../<the working directory's own name>/x`,
#     which climbs out and straight back in; the linter cannot know that name
#     and reports it like the rest (OBSERVED_UNMODELLED in the tests).
#     du, realpath, tree and date are not path-checked at all (`du -s ..` and
#     `du -s /etc/hostname` passed); of the git subcommands only diff and grep
#     were (`git log -1 -- ../other`, `git status ..`, `git blame ../x` passed).
#   * "Read-only" is decided per command from a list of safe options, not from
#     the command name: `sort README.md` passes and `sort -o out.txt README.md`,
#     `sort --output=out.txt`, `sort --compress-program=gzip`, `sort -T .` and
#     even `sort -k1,1` and `sort -t: -k2` (a value glued to a short option) do
#     not, while `sort -k 1,1` and `sort --key=1` do. Likewise `git diff
#     --output=x` (and --output on log, show, blame, shortlog), `git diff
#     --ext-diff`, `git grep -O`, `git reflog expire|delete`, `git ls-remote
#     <remote>`, `tree -o f`, `date -s`, `hostname <name>`, `hostname -F f`,
#     `ps -o pid` and `ps e`. A matching entry rescues these (`Bash(sort *)`
#     let `sort -o` write its file) - which is also why `date -s` and
#     `hostname <name>` must not be re-probed with an entry: they ran, and
#     set the clock and the host name of the machine.
#   * `find` with an action that writes or runs something (-exec, -delete,
#     -fprint, -fls) failed with `Bash(find *)` and with `Bash(find:*)`; only
#     blanket `Bash` let it through.
#   * Otherwise the operation must match a Bash(...) entry of the skill's own
#     allowed-tools. Redirections are dropped before matching. `Bash(cmd *)`
#     matches `cmd` and `cmd <anything>`; a `*` elsewhere is a glob; legacy
#     `Bash(cmd:*)` is a word-boundary prefix; no `*` means exact. Matching is
#     textual and quote-sensitive; ${CLAUDE_*} variables are substituted in
#     both the entry and the command first. `Bash` alone and `Bash(*)` cover
#     everything. The tool name is case-sensitive.
#   * time, nice, nohup, command and `timeout N` in front of a command are
#     ignored for entry matching (but make a read-only command need an entry).
#     A VAR=value prefix is part of the text to match, except a few known
#     harmless variables (SAFE_ENV_VARS), which are ignored.
#   * Subshell parentheses, brace groups, a trailing & and output redirection
#     to a real file fail whatever specific entry is present; only blanket
#     Bash passes. So do most expansions: any ${VAR} form, any unquoted
#     $(...) or backticks, and any $VAR other than $HOME - except inside an
#     `echo` argument that is a double-quoted string with other text in it
#     (`echo "branch: $(git branch --show-current)"` passes when the inner
#     command is one read-only command with no pipe; `echo "$USER"` and
#     `echo $USER` do not).
#   * Separately from permissions, a command that exits non-zero aborts the
#     load ("Shell command failed"), with or without `2>/dev/null`. `|| echo`,
#     `|| true`, `; true` and a pipe into another command all prevent that.

AUTO_ALLOWED = frozenset("""
    echo printf true false date pwd whoami which type test [ sleep basename dirname realpath
    hostname uname id groups arch nproc free ps uptime locale df du seq expr tr cut paste rev
    fold comm cmp diff file stat md5sum sha256sum nl tac od strings sort cat head tail wc grep
    ls cd tree cal column
""".split())
# git subcommands observed to pass with no entry (with ordinary read-only flags).
GIT_AUTO_ALLOWED = frozenset("""
    status log diff show ls-files describe rev-parse blame shortlog reflog merge-base rev-list
    cat-file grep for-each-ref ls-remote
""".split())
NOT_PATH_CHECKED = frozenset({"echo", "printf", "test", "[", "basename", "dirname",
                              "du", "realpath", "tree", "date"})  # observed exempt
GIT_PATH_CHECKED = frozenset({"diff", "grep"})   # the git subcommands whose `..` operands were rejected
PATTERN_FIRST = frozenset({"grep", "tr", "expr", "seq", "sed", "jq", "rg"})  # first operand is not a path
# -exec, -delete, -fls, -fprint and -fprintf observed; the rest assumed alike
FIND_ACTIONS = frozenset({"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fls"})
FIND_NAME_TESTS = frozenset({"-name", "-iname"})  # their value is a pattern: `find . -name ..` passed

# sort's safe options, read out of the 2.1.295 binary (its `safeFlags` table)
# and confirmed by 40 probes. An option that is not here needs approval: -o and
# --output write a file, --compress-program runs one, -T and --files0-from
# name paths. A short option takes its value as the next word, never glued.
SORT_FLAGS = frozenset("""
    --ignore-leading-blanks -b --dictionary-order -d --ignore-case -f --general-numeric-sort -g
    --human-numeric-sort -h --ignore-nonprinting -i --month-sort -M --numeric-sort -n --random-sort -R
    --reverse -r --stable -s --unique -u --version-sort -V --zero-terminated -z --check -c
    --check-char-order -C --merge -m --help --version
""".split())
SORT_VALUE_FLAGS = frozenset("--sort --key -k --field-separator -t --buffer-size -S --parallel --batch-size".split())
# date and hostname, from the same table. `date -s`, `date --set=`, `hostname
# <name>`, `hostname -F f` and `hostname -b` were probed and need approval. A
# bare operand to date that is not a +FORMAT sets the clock; that one is from
# the binary alone - it was not probed, for the obvious reason.
DATE_FLAGS = frozenset("-u --utc --universal -I --iso-8601 -R --rfc-email --debug --help --version".split())
DATE_VALUE_FLAGS = frozenset("-d --date -r --reference --rfc-3339".split())
HOSTNAME_FLAGS = frozenset("""
    -f --fqdn --long -s --short -i --ip-address -I --all-ip-addresses -a --alias -d --domain -A
    --all-fqdns -v --verbose -h --help -V --version
""".split())
SAFE_ENV_VARS = frozenset({"NODE_ENV", "LC_ALL", "LANG", "TZ", "NO_COLOR", "PYTHONUNBUFFERED", "CI"})
WRAPPERS = frozenset({"time", "nice", "nohup", "command"})
FALLBACK_WORDS = frozenset({"echo", "printf", "true"})
OUTSIDE_VARS = ("${CLAUDE_PLUGIN_ROOT}", "${CLAUDE_PLUGIN_DATA}")
ENV_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")
DURATION_RE = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")
VERSIONISH_RE = re.compile(r"^v?\d+(?:\.\d+)*$")

HAZARD_TEXT = {
    "find_action": "a `find` action that writes or runs something (`-exec`, `-delete`, `-fprint`, `-fls`)",
    "subshell": "a subshell `( ... )`",
    "group": "a `{ ...; }` group",
    "substitution": "command substitution (`$(...)` or backticks) outside a quoted `echo` sentence",
    "background": "the `&` background operator",
    "redirect": "output redirection to a file",
    "expansion": "a shell variable expansion the permission check cannot resolve",
}
HAZARD_HINT = {
    "find_action": "list the files with `find ... | head` and let the model act on them, or call an approved script",
    "subshell": "drop the parentheses - a pipe into `head` already keeps the exit status zero",
    "group": "drop the braces - a pipe into `head` already keeps the exit status zero",
    "substitution": "run the inner command as its own injection, or put it inside `echo \"text $(cmd)\"`",
    "background": "remove the `&`",
    "redirect": "redirect only to /dev/null",
    "expansion": "only `$HOME`, or a variable inside a quoted `echo \"text $VAR\"`, passes; "
                 "otherwise have an approved script read it",
}


def _unquote(word):
    """A shell word with its quoting removed (enough to read the command name
    and to look at operands; not a full shell unquote)."""
    out, quote, i = [], None, 0
    while i < len(word):
        c = word[i]
        if quote:
            if c == quote:
                quote = None
            elif c == "\\" and quote == '"' and i + 1 < len(word):
                i += 1
                out.append(word[i])
            else:
                out.append(c)
        elif c in "\"'":
            quote = c
        elif c == "\\" and i + 1 < len(word):
            i += 1
            out.append(word[i])
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _skip_balanced(s, i):
    """Index just past the `)` that closes the `(` at s[i]; len(s) if unclosed."""
    depth = 0
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(s)


def lex_command(command):
    """Quote-aware shell tokens for an injection command.

    Returns (tokens, hazards). A token is ("word", raw_text), ("op", operator)
    or ("redir", operator); raw_text keeps its quotes. hazards is the set of
    HAZARD_TEXT keys the scan saw. Never raises on malformed input."""
    s, n = command, len(command)
    tokens, hazards, cur = [], set(), []
    i = 0

    def flush():
        if cur:
            tokens.append(("word", "".join(cur)))
            del cur[:]

    def at_word_start():
        return not cur

    while i < n:
        c = s[i]
        nxt = s[i + 1] if i + 1 < n else ""
        if c == "\\":
            if nxt == "\n":
                i += 2
                continue
            cur.append(s[i:i + 2])
            i += 2
        elif c == "'":
            j = s.find("'", i + 1)
            j = n - 1 if j < 0 else j
            cur.append(s[i:j + 1])
            i = j + 1
        elif c == '"':
            j = i + 1
            while j < n and s[j] != '"':
                if s[j] == "\\":
                    j += 1
                j += 1
            cur.append(s[i:j + 1])
            i = j + 1
        elif c == "`":
            j = s.find("`", i + 1)
            j = n - 1 if j < 0 else j
            cur.append(s[i:j + 1])
            i = j + 1
        elif c == "$" and nxt == "(":
            j = _skip_balanced(s, i + 1)
            cur.append(s[i:j])
            i = j
        elif c == "#" and at_word_start():
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif c in " \t\r":
            flush()
            i += 1
        elif c == "\n":
            flush()
            tokens.append(("op", "\n"))
            i += 1
        elif c == ";":
            flush()
            tokens.append(("op", ";"))
            i += 2 if nxt == ";" else 1
        elif c == "|":
            flush()
            if nxt == "|":
                tokens.append(("op", "||"))
                i += 2
            else:
                tokens.append(("op", "|"))
                i += 2 if nxt == "&" else 1
        elif c == "&":
            if nxt == "&":
                flush()
                tokens.append(("op", "&&"))
                i += 2
            elif nxt == ">":
                flush()
                i += 3 if s[i + 2:i + 3] == ">" else 2
                tokens.append(("redir", "&>"))
            else:
                flush()
                hazards.add("background")
                tokens.append(("op", "&"))
                i += 1
        elif c in "<>":
            if cur and "".join(cur).isdigit():
                del cur[:]              # an fd number belongs to the redirection
            else:
                flush()
            op = next(o for o in ("<<<", "<<", "<&", "<", ">>", ">&", ">|", ">") if s.startswith(o, i))
            tokens.append(("redir", op))
            i += len(op)
        elif c == "(":
            flush()
            hazards.add("subshell")
            tokens.append(("op", "("))
            i += 1
        elif c == ")":
            flush()
            tokens.append(("op", ")"))
            i += 1
        elif c == "{" and at_word_start() and (nxt in " \t\n" or not nxt):
            hazards.add("group")
            i += 1
        elif c == "}" and at_word_start() and (nxt in " \t\n;|&)" or not nxt):
            i += 1
        else:
            cur.append(c)
            i += 1
    flush()
    return tokens, hazards


class Operation:
    """One simple command of an injection: its words (raw, redirections
    removed), the operator that precedes it and what it redirects."""
    __slots__ = ("words", "sep", "reads", "writes")

    def __init__(self, sep):
        self.words, self.sep, self.reads, self.writes = [], sep, [], []

    @property
    def text(self):
        return " ".join(self.words)


def split_operations(command):
    """(operations, hazards) for an injection command."""
    tokens, hazards = lex_command(command)
    ops, cur = [], Operation("")
    i = 0
    while i < len(tokens):
        kind, value = tokens[i]
        if kind == "op":
            if cur.words:
                ops.append(cur)
            cur = Operation(value)
        elif kind == "redir":
            target = tokens[i + 1][1] if i + 1 < len(tokens) and tokens[i + 1][0] == "word" else ""
            if target:
                i += 1
            plain = _unquote(target)
            if value == "<<":
                break                    # a here-document: its body is data, stop reading commands
            if value in ("<", "<&") and not plain.isdigit():
                cur.reads.append(plain)
            elif value in (">", ">>", ">|", "&>", ">&") and not (
                    value == ">&" and (plain.isdigit() or plain == "-")):
                if plain != "/dev/null":
                    cur.writes.append(plain)
        else:
            cur.words.append(value)
        i += 1
    if cur.words:
        ops.append(cur)
    if any(op.writes for op in ops):
        hazards.add("redirect")
    return ops, hazards


def has_failure_fallback(command):
    """True when the injection cannot end with a non-zero exit status in the
    ordinary failure case: an `|| echo/printf/true` alternative, a final
    `; echo/true`, or a pipe into a last stage (a pipeline's status is its last
    command's). `2>/dev/null` alone is not one - observed to still abort."""
    ops, _ = split_operations(command)
    if not ops:
        return False
    for op in ops:
        if op.sep == "||" and _unquote(op.words[0]) in FALLBACK_WORDS:
            return True
    last = ops[-1]
    if last.sep == "|":
        return True
    return last.sep in (";", "\n") and _unquote(last.words[0]) in FALLBACK_WORDS


def bash_entries(allowed_tools):
    """(blanket, patterns) from an `allowed-tools` value: a string (entries
    separated by commas and/or spaces), an inline list or a block list.
    blanket is True for `Bash` and `Bash(*)`."""
    if isinstance(allowed_tools, (list, tuple)):
        chunks = [x for x in allowed_tools if isinstance(x, str)]
    elif isinstance(allowed_tools, str):
        chunks = [allowed_tools]
    else:
        chunks = []
    entries = []
    for chunk in chunks:
        for quotes in (True, False):
            found, cur, depth, quote = [], [], 0, None
            for c in chunk:
                if quote:
                    cur.append(c)
                    if c == quote:
                        quote = None
                elif quotes and depth and c in "\"'":
                    quote = c
                    cur.append(c)
                elif c == "(":
                    depth += 1
                    cur.append(c)
                elif c == ")":
                    depth = max(depth - 1, 0)
                    cur.append(c)
                elif depth == 0 and (c == "," or c.isspace()):
                    if cur:
                        found.append("".join(cur))
                    cur = []
                else:
                    cur.append(c)
            if cur:
                found.append("".join(cur))
            if not quote:
                break                    # an unterminated quote: re-read without quote tracking
        entries.extend(found)
    blanket, patterns = False, []
    for entry in entries:
        if entry == "Bash":
            blanket = True
        elif entry.startswith("Bash("):
            inner = entry[5:-1] if entry.endswith(")") else entry[5:]
            inner = " ".join(inner.split())
            if inner in ("", "*"):
                blanket = True
            else:
                patterns.append(inner)
    return blanket, patterns


def _glob_match(pattern, text):
    """`*` matches any run of characters; everything else is literal. Linear."""
    pieces = pattern.split("*")
    if len(pieces) == 1:
        return pattern == text
    if not text.startswith(pieces[0]):
        return False
    pos = len(pieces[0])
    for piece in pieces[1:-1]:
        found = text.find(piece, pos)
        if found < 0:
            return False
        pos = found + len(piece)
    return len(text) - pos >= len(pieces[-1]) and text.endswith(pieces[-1])


def entry_covers(pattern, text):
    """Does the Bash(...) entry content `pattern` match the operation `text`?
    Both are compared with runs of whitespace collapsed."""
    pattern, text = " ".join(pattern.split()), " ".join(text.split())
    if pattern in ("", "*"):
        return True
    if pattern.endswith(":*"):                       # legacy prefix form
        prefix = pattern[:-2].rstrip()
        return text == prefix or text.startswith(prefix + " ")
    if "*" not in pattern:
        return text == pattern
    if pattern.endswith(" *"):
        head = pattern[:-2]
        if "(" in head or ")" in head:
            # Observed quirk: `Bash(python3 -c 'print(1)' *)` matched neither
            # `python3 -c 'print(1)'` nor that plus arguments, while the same
            # text ending `'*` or `':*` did. Cause unknown; encoded as seen.
            return False
        if _glob_match(head, text):
            return True
    return _glob_match(pattern, text)


def suggest_entry(words):
    """A narrow `Bash(...)` entry that covers the operation made of `words`
    (raw shell words, wrappers and harmless env prefixes already removed)."""
    lead = []
    while words and ENV_ASSIGN_RE.match(words[0]):
        lead.append(words[0])
        words = words[1:]
    if len(words) <= 2:
        return "Bash(" + " ".join(lead + words) + ")"
    head = [words[0]]
    for w in words[1:3]:
        if w.startswith("-") or VERSIONISH_RE.match(_unquote(w)):
            break
        head.append(w)
    if len(head) == 1:
        head.append(words[1])
    text = " ".join(lead + head)
    if len(head) == len(words):
        return f"Bash({text})"
    if "(" in text or ")" in text:
        return f"Bash({text}:*)"
    return f"Bash({text} *)"


GIT_BRANCH_FLAGS = frozenset({"-a", "-r", "-vv", "--show-current", "--list", "--contains", "--merged"})
GIT_TAG_FLAGS = frozenset({"-l", "--contains"})
GIT_TAKES_VALUE = frozenset({"--contains", "--merged", "-l", "--list"})


def _git_listing(rest, flags):
    """`git branch` / `git tag` pass only in the listing forms that were seen
    to pass; `git tag -n1`, `git tag <name>` and `git branch -d` did not."""
    value_next = False
    for a in rest:
        if value_next and not a.startswith("-"):
            value_next = False
        elif a in flags or a.startswith("--sort="):
            value_next = a in GIT_TAKES_VALUE
        else:
            return False
    return True


def _git_writes_or_runs(sub, rest):
    """Options that stop a read-only git subcommand being one. Observed:
    --output (diff, log, show, blame, shortlog) writes a file, --ext-diff and
    `grep -O` run a program, `reflog expire|delete` rewrites the reflog."""
    options = rest[:rest.index("--")] if "--" in rest else rest
    for a in options:
        if a == "--output" or a.startswith("--output=") or a == "--ext-diff":
            return True
        if sub == "grep" and (a.startswith("-O") or a.startswith("--open-files-in-pager")):
            return True
    return sub == "reflog" and rest[:1] in (["expire"], ["delete"])


def _git_auto_allowed(args):
    """Observed: read-only subcommands pass; any option before the subcommand
    (-C, -c, --no-pager, --version) needs approval."""
    if not args or args[0].startswith("-"):
        return False
    sub, rest = args[0], args[1:]
    if sub == "ls-remote":
        return all(a.startswith("-") for a in rest)      # naming a remote needs approval
    if sub in GIT_AUTO_ALLOWED:
        return not _git_writes_or_runs(sub, rest)
    if sub == "branch":
        return _git_listing(rest, GIT_BRANCH_FLAGS)
    if sub == "tag":
        return _git_listing(rest, GIT_TAG_FLAGS)
    if sub == "remote":
        return rest in ([], ["-v"])
    if sub == "stash":
        return rest[:1] in (["list"], ["show"])
    if sub == "worktree":
        return rest[:1] == ["list"]
    if sub == "config":
        return rest[:1] == ["--get"]
    return False


def _sed_auto_allowed(rest):
    """Observed: `sed -n 'Np'` / `sed -n 'N,Mp'` on a file, and a lone
    `s/../../` filtering stdin, pass. An s command on a file, `/re/p`, `$p`,
    `/re/d`, -e and -i all need approval."""
    if rest[:1] == ["-n"] and len(rest) >= 2:
        return bool(re.match(r"^\d+(?:,\d+)?p$", rest[1])) and not any(a.startswith("-") for a in rest[2:])
    return len(rest) == 1 and rest[0].startswith("s") and len(rest[0]) > 1 and not rest[0][1].isalnum()


def _flags_allowed(rest, flags, value_flags, bundles=True, operand=None):
    """Are these arguments all safe options (and operands `operand` accepts)?
    A long option may carry its value after `=`; a short one takes the next
    word. Several valueless short options may share one dash when `bundles`."""
    i = 0
    while i < len(rest):
        a = rest[i]
        i += 1
        if a == "--":
            return operand is None or all(operand(x) for x in rest[i:])
        if not a.startswith("-") or a == "-":
            if operand is not None and not operand(a):
                return False
        elif a.startswith("--") and "=" in a:
            if a.split("=", 1)[0] not in value_flags:
                return False
        elif a in value_flags:
            i += 1                                       # its value
        elif a in flags:
            pass
        elif not (bundles and not a.startswith("--") and all("-" + c in flags for c in a[1:])):
            return False
    return True


def _ps_auto_allowed(rest):
    """Observed: `ps`, `ps aux`, `ps axo pid`, `ps -ef`, `ps -p 1`, `ps -u root`,
    `ps -C sh` and `ps --forest` pass; `ps -o pid`, `ps -eo pid` and `ps e`
    (BSD: show the environment) need approval."""
    if rest and not rest[0].startswith("-") and "e" in rest[0]:
        return False
    return not any(re.match(r"^-[A-Za-z]*o", a) for a in rest)


def auto_allowed(args):
    """True when the command (unquoted words, env prefixes removed) was
    observed to pass the permission check with no allowed-tools entry."""
    if not args:
        return True
    cmd, rest = args[0], args[1:]
    if cmd == "git":
        return _git_auto_allowed(rest)
    if cmd == "sort":
        return _flags_allowed(rest, SORT_FLAGS, SORT_VALUE_FLAGS)
    if cmd == "date":
        return _flags_allowed(rest, DATE_FLAGS, DATE_VALUE_FLAGS, operand=lambda a: a.startswith("+"))
    if cmd == "hostname":
        return _flags_allowed(rest, HOSTNAME_FLAGS, frozenset(), operand=lambda a: False)
    if cmd == "tree":
        return not any(a.startswith("-o") for a in rest)     # -o FILE writes the listing
    if cmd == "ps":
        return _ps_auto_allowed(rest)
    if cmd in ("python3", "python"):
        return rest == ["--version"]
    if cmd == "node":
        return rest in (["--version"], ["-v"])
    if cmd == "docker":
        return rest == ["ps"]
    if cmd == "sed":
        return _sed_auto_allowed(rest)
    if cmd == "find":
        return not any(a in FIND_ACTIONS or a.startswith("-fprint") for a in rest)
    if cmd == "uniq":
        return all(a.startswith("-") for a in rest)          # stdin only; a file operand needs approval
    if cmd == "xargs":
        return rest[:1] == ["echo"]
    if cmd == "jq":
        return "--version" not in rest
    if cmd == "rg":
        return "--files" not in rest
    return cmd in AUTO_ALLOWED


def has_dotdot(path):
    """Does the path have a `..` component? (`..proj`, `b..` and `x/..y` do not.)"""
    return ".." in path.split("/")


def _outside_operand(cmd, raw_words, reads, skill_dir_outside):
    """The first operand of a read-only command that the permission check
    treats as outside the session's working directories, or None. Judged from
    the text alone: an absolute path, ~, the plugin variables, and any path
    with a `..` component (see the section notes - `sub/../x` is rejected
    although it never leaves)."""
    if cmd in NOT_PATH_CHECKED:
        return None
    outside_vars = OUTSIDE_VARS + (("${CLAUDE_SKILL_DIR}",) if skill_dir_outside else ())
    operands, first, skip = [], cmd in PATTERN_FIRST, False
    dotdot = cmd != "git" or _unquote("".join(raw_words[1:2])) in GIT_PATH_CHECKED
    for raw in raw_words[1:]:
        if skip:
            skip = False                 # the value of find's -name: a pattern
        elif raw.startswith("-"):
            skip = cmd == "find" and raw in FIND_NAME_TESTS
            if raw == "-f" and cmd in ("grep", "rg"):
                first = False            # the patterns come from a file: every operand is a path
        elif first:
            first = False                # the pattern or expression, not a path
        else:
            operands.append(raw)
    for raw in operands + list(reads):
        plain = _unquote(raw)
        if any(v in plain for v in outside_vars):
            return plain
        if plain.startswith(("~", "$HOME")) or (plain.startswith("/") and plain != "/dev/null"):
            return plain
        if dotdot and has_dotdot(plain):
            return plain
    return None


def _expansions(raw_word, argument_names=()):
    """The shell expansions in one raw word, as (kind, payload, context):
    kind 'var' (payload: the name), 'brace' (a ${...} form) or 'subst' (payload:
    the inner command); context 'bare', 'alone' (a double-quoted string that is
    nothing but expansions) or 'text' (double-quoted, with other text beside it).
    What the skill preprocessor replaces before the shell runs is not listed:
    ${CLAUDE_*}, $ARGUMENTS, $0..$9 and the skill's declared argument names."""
    found, i, n = [], 0, len(raw_word)

    def scan(text, context):
        """Expansions in text; returns the text with them removed."""
        out, j, m = [], 0, len(text)
        while j < m:
            c = text[j]
            if c == "\\":
                out.append(text[j:j + 2])
                j += 2
            elif c == "`":
                end = text.find("`", j + 1)
                end = m if end < 0 else end
                found.append(["subst", text[j + 1:end], context])
                j = end + 1
            elif c == "$" and text.startswith("((", j + 1):
                j = _skip_balanced(text, j + 1)             # arithmetic: observed harmless
            elif c == "$" and text.startswith("(", j + 1):
                end = _skip_balanced(text, j + 1)
                found.append(["subst", text[j + 2:end - 1], context])
                j = end
            elif c == "$" and text.startswith("{", j + 1):
                end = text.find("}", j)
                end = m - 1 if end < 0 else end
                if text[j + 2:end] not in SUBSTITUTED_VARS:
                    found.append(["brace", text[j:end + 1], context])
                j = end + 1
            elif c == "$":
                name = re.match(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]|[?$!@*#]", text[j + 1:])
                if name and not (name.group(0).isdigit() or name.group(0) == "ARGUMENTS"
                                 or name.group(0) in argument_names):
                    found.append(["var", name.group(0), context])
                if name and name.group(0) == "ARGUMENTS":
                    out.append("x")                          # replaced by the arguments: counts as text
                j += 1 + (len(name.group(0)) if name else 0)
            else:
                out.append(c)
                j += 1
        return "".join(out)

    while i < n:
        c = raw_word[i]
        if c == "'":
            end = raw_word.find("'", i + 1)
            i = n if end < 0 else end + 1
        elif c == '"':
            end = i + 1
            while end < n and raw_word[end] != '"':
                end += 2 if raw_word[end] == "\\" else 1
            start = len(found)
            rest = scan(raw_word[i + 1:end], "text")
            if not rest.strip():
                for item in found[start:]:
                    item[2] = "alone"
            i = end + 1
        else:
            end = i
            while end < n and raw_word[end] not in "'\"":
                end += 2 if raw_word[end] == "\\" else 1
            scan(raw_word[i:end], "bare")
            i = end
    return [tuple(item) for item in found]


def _expansion_hazards(ops, argument_names, skill_dir_outside):
    """Which expansions in these operations the permission check rejects.
    Observed (see the section notes): $HOME passes anywhere; inside an `echo`
    argument that is a double-quoted string with other text, any $VAR passes
    and so does $(cmd) when cmd is a single read-only command. Everything
    else is rejected."""
    hazards = set()
    for op in ops:
        words = list(op.words)
        while words and ENV_ASSIGN_RE.match(words[0]) and ENV_ASSIGN_RE.match(words[0]).group(1) in SAFE_ENV_VARS:
            words = words[1:]
        is_echo = bool(words) and _unquote(words[0]) == "echo"
        for word in words:
            for kind, payload, context in _expansions(word, argument_names):
                in_sentence = is_echo and context == "text"
                if kind == "brace":
                    hazards.add("expansion")
                elif kind == "var":
                    if payload != "HOME" and not in_sentence:
                        hazards.add("expansion")
                elif not in_sentence or len(split_operations(payload)[0]) != 1 \
                        or injection_problems(payload, None, skill_dir_outside, argument_names):
                    hazards.add("substitution")       # the inner command must be one read-only command
    return hazards


class InjectionProblem:
    """kind is 'uncovered' (add `entry`), 'outside' (a read-only command
    reaching outside the working directories) or 'hazard' (a construct only
    blanket Bash covers)."""
    __slots__ = ("kind", "text", "entry", "detail")

    def __init__(self, kind, text, entry="", detail=""):
        self.kind, self.text, self.entry, self.detail = kind, text, entry, detail

    def message(self):
        if self.kind == "uncovered":
            return (f"injection runs `{self.text[:60]}`, which needs approval, and an injection that needs "
                    f"approval aborts the skill load - add `{self.entry}` to allowed-tools")
        if self.kind == "outside":
            if has_dotdot(self.detail) and not self.detail.startswith(("/", "~", "$")):
                return (f"injection runs `{self.text[:60]}` on a path with a `..` component ({self.detail[:50]}); "
                        "the permission check treats any such path as outside the session's working directories, "
                        "even one that stays inside, and a matching entry such as "
                        f"`Bash({self.text.split()[0]} *)` does not help - write the path without `..` if it is "
                        "inside the project; otherwise have the model Read the file, or call a script through an "
                        "approved entry")
            return (f"injection runs `{self.text[:60]}` on a path outside the session's working directories "
                    f"({self.detail[:50]}); read-only commands are blocked there and a matching entry such as "
                    f"`Bash({self.text.split()[0]} *)` does not help - have the model Read the file, or call a "
                    "script through an approved entry")
        return (f"injection uses {HAZARD_TEXT[self.detail]}, which aborts the skill load whatever specific "
                f"`Bash(...)` entry is present (only blanket `Bash` passes) - {HAZARD_HINT[self.detail]}")


def injection_problems(command, allowed_tools, skill_dir_outside=False, argument_names=()):
    """Everything about an injection command that the pre-load permission
    check will reject, given the skill's allowed-tools. See the notes at the
    top of this section for what that check was observed to do."""
    blanket, patterns = bash_entries(allowed_tools)
    if blanket:
        return []
    ops, hazards = split_operations(command)
    hazards |= _expansion_hazards(ops, argument_names, skill_dir_outside)
    problems = [InjectionProblem("hazard", command, detail=h) for h in HAZARD_TEXT if h in hazards]
    seen = set()
    for op in ops:
        words = list(op.words)
        while words and ENV_ASSIGN_RE.match(words[0]) and ENV_ASSIGN_RE.match(words[0]).group(1) in SAFE_ENV_VARS:
            words = words[1:]
        if not words:
            continue
        text = " ".join(words)
        if text in seen:
            continue
        seen.add(text)
        args = [_unquote(w) for w in words]
        has_env = bool(ENV_ASSIGN_RE.match(words[0]))
        auto = not has_env and auto_allowed(args)
        if auto or (not has_env and args[0] in AUTO_ALLOWED):
            # The path check belongs to the command, not to how it was approved:
            # `sort -o ../x f` failed with `Bash(sort *)` present.
            outside = _outside_operand(args[0], words, op.reads, skill_dir_outside)
            if outside:
                problems.append(InjectionProblem("outside", text, detail=outside))
                continue
        if auto:
            continue
        if args[0] == "find" and not has_env:
            if "find_action" not in hazards:              # no specific entry covers it
                hazards.add("find_action")
                problems.append(InjectionProblem("hazard", command, detail="find_action"))
            continue
        # entries match the operation as written, and again with wrappers removed
        inner = list(words)
        lead = []
        while inner and ENV_ASSIGN_RE.match(inner[0]):
            lead.append(inner.pop(0))
        while inner:
            if _unquote(inner[0]) in WRAPPERS and len(inner) > 1:
                inner = inner[1:]
            elif _unquote(inner[0]) == "timeout" and len(inner) > 2 and DURATION_RE.match(_unquote(inner[1])):
                inner = inner[2:]
            else:
                break
        candidates = {text, " ".join(lead + inner)}
        if any(entry_covers(p, cand) for p in patterns for cand in candidates):
            continue
        problems.append(InjectionProblem("uncovered", text, entry=suggest_entry(lead + inner)))
    return problems


def uncovered_injection_parts(command, allowed_tools):
    """The operations of an injection command that no `Bash(...)` entry in
    allowed-tools pre-approves and that are not read-only (text only)."""
    return [p.text for p in injection_problems(command, allowed_tools) if p.kind == "uncovered"]


class Directive:
    """quoted: the directive sits inside a longer code span (two or more
    backticks, then the `!`), which is how markdown shows one literally."""
    __slots__ = ("command", "line", "end_line", "fenced", "quoted")

    def __init__(self, command, line, end_line, fenced, quoted=False):
        self.command, self.line, self.end_line, self.fenced, self.quoted = command, line, end_line, fenced, quoted


QUOTED_LEAD_RE = re.compile(r"``+ ?$")


def _blank(m):
    return re.sub(r"[^\n]", " ", m.group(0))


def mask_directives(body):
    """The body with every injection directive blanked out, line count kept."""
    return INLINE_DIRECTIVE_RE.sub(_blank, FENCED_DIRECTIVE_RE.sub(_blank, body))


def find_directives(body, first_line=1):
    """Injection directives exactly as the skill preprocessor finds them: over
    the raw body, with no regard for markdown code spans or ordinary fences."""
    found = []

    def fenced(m):
        found.append(Directive(m.group(1).strip(), line_of(body, m.start(), first_line),
                               line_of(body, m.end(), first_line), True))
        return _blank(m)

    # One pass builds the masked copy; rebuilding it per directive was quadratic.
    masked = FENCED_DIRECTIVE_RE.sub(fenced, body)
    for m in INLINE_DIRECTIVE_RE.finditer(masked):
        quoted = bool(QUOTED_LEAD_RE.search(masked, max(m.start() - 8, 0), m.start()))
        found.append(Directive(m.group(1).strip(), line_of(body, m.start(), first_line),
                               line_of(body, m.end(), first_line), False, quoted))
    found.sort(key=lambda d: d.line)
    return found


def live_grammar(body, first_line=1):
    """Skill-body grammar outside code spans, for files that are NOT
    preprocessed (rules, agent bodies). Yields (line, description)."""
    hits = []
    lines = body.split("\n")
    in_fence = None
    for idx, line in enumerate(lines):
        m = FENCE_RE.match(line)
        if in_fence is None and m:
            if line.strip()[len(m.group(1)):].startswith("!"):
                hits.append((first_line + idx, "a ```! injection block"))
            in_fence = m.group(1)
        elif in_fence is not None and m and m.group(1)[0] == in_fence[0] \
                and len(m.group(1)) >= len(in_fence):
            in_fence = None
    prose = mask_spans(mask_fences(body), min_ticks=2)
    for m in INLINE_DIRECTIVE_RE.finditer(prose):
        hits.append((line_of(prose, m.start(), first_line), f"injection directive !`{m.group(1).strip()[:40]}`"))
    prose = mask_spans(INLINE_DIRECTIVE_RE.sub(lambda m: " " * len(m.group(0)), prose))
    for m in LIVE_TOKEN_RE.finditer(prose):
        hits.append((line_of(prose, m.start(), first_line), m.group(0)))
    return sorted(hits)


# ---- skill resolution -------------------------------------------------------

class SkillIndex:
    def __init__(self, root, plugin_name):
        self.root = root
        self.plugin = plugin_name     # None for a project .claude/skills root
        self.skills = {}              # name -> SKILL.md (or command file) path

    def resolve(self, ref):
        """True / False, or None when the reference cannot be judged from here."""
        if ":" in ref:
            plug, name = ref.split(":", 1)
            if self.plugin is None or plug != self.plugin:
                return None
            return name in self.skills
        return ref in self.skills

    def disables_model_invocation(self, ref):
        path = self.skills.get(ref.split(":", 1)[-1])
        if not path:
            return False
        try:
            return parse_frontmatter(read_text(path)).get("disable-model-invocation") is True
        except OSError:
            return False


_INDEX_CACHE = {}


def _add_skills_dir(index, directory):
    if not os.path.isdir(directory):
        return
    for entry in sorted(os.listdir(directory)):
        skill_md = os.path.join(directory, entry, "SKILL.md")
        if os.path.isfile(skill_md):
            index.skills.setdefault(entry, skill_md)
            try:
                name = parse_frontmatter(read_text(skill_md)).get("name")
            except OSError:
                name = None
            if isinstance(name, str) and name:
                index.skills.setdefault(name, skill_md)


def skill_dir_is_outside(path):
    """Is this skill's own directory outside the session's working directories
    when it runs? Yes for a plugin skill (it runs from the plugin cache) and a
    personal skill under ~/.claude; no for a project skill, which sits inside
    the project. Decided by the nearest marker above the file."""
    d = os.path.dirname(os.path.abspath(path))
    home_claude = os.path.join(os.path.expanduser("~"), ".claude")
    while True:
        if os.path.basename(d) == ".claude":
            return d == home_claude
        if os.path.isfile(os.path.join(d, ".claude-plugin", "plugin.json")):
            return True
        up = os.path.dirname(d)
        if up == d:
            return False
        d = up


def skill_scope(path):
    """('project', project root), ('personal', None), ('plugin', plugin root)
    or (None, None) for a skill or command file, by the nearest marker above."""
    d = os.path.dirname(os.path.abspath(path))
    home_claude = os.path.join(os.path.expanduser("~"), ".claude")
    while True:
        if os.path.basename(d) == ".claude":
            return ("personal", None) if d == home_claude else ("project", os.path.dirname(d))
        if os.path.isfile(os.path.join(d, ".claude-plugin", "plugin.json")):
            return "plugin", d
        up = os.path.dirname(d)
        if up == d:
            return None, None
        d = up


def at_file_refs(body, first_line=1):
    """SK015: (line, path, context) for each `@path` the skill loader will
    treat as a file reference - see AT_FILE_RE. A `#L2-5` or other fragment is
    part of the reference and is left off the path. context is 'fence', 'span'
    or 'prose'. Injection directives are left out (their text is a command)."""
    lines = mask_directives(body).split("\n")
    fenced = [not kept and bool(raw) for kept, raw in zip(mask_fences("\n".join(lines)).split("\n"), lines)]
    out = []
    for idx, line in enumerate(lines):
        if "@" not in line:
            continue
        spans = [(m.start(), m.end()) for m in SPAN_RE.finditer(line)] if "`" in line and not fenced[idx] else []
        for m in AT_FILE_RE.finditer(line):
            token = AT_FRAGMENT_RE.sub("", m.group(1) or m.group(2))
            context = "fence" if fenced[idx] else "span" if any(a < m.start() < b for a, b in spans) else "prose"
            out.append((first_line + idx, token, context))
    return out


def looks_like_a_file(token):
    if token.startswith(("./", "../")):
        return True
    return os.path.splitext(os.path.basename(token))[1][1:].lower() in AT_KNOWN_EXT


def skill_index_for(path):
    """Skills visible from the nearest plugin root or .claude/skills, or None."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if d in _INDEX_CACHE:
            return _INDEX_CACHE[d]
        manifest = os.path.join(d, ".claude-plugin", "plugin.json")
        index = None
        if os.path.isfile(manifest):
            try:
                meta = json.loads(read_text(manifest))
            except (OSError, ValueError):
                meta = {}
            meta = meta if isinstance(meta, dict) else {}
            name = meta.get("name") if isinstance(meta.get("name"), str) else os.path.basename(d)
            index = SkillIndex(d, name)
            _add_skills_dir(index, os.path.join(d, "skills"))
            extra = meta.get("skills")
            for sub in ([extra] if isinstance(extra, str) else extra if isinstance(extra, list) else []):
                if isinstance(sub, str):
                    _add_skills_dir(index, os.path.normpath(os.path.join(d, sub)))
            if os.path.isfile(os.path.join(d, "SKILL.md")):
                index.skills.setdefault(name, os.path.join(d, "SKILL.md"))
        elif os.path.isdir(os.path.join(d, ".claude", "skills")):
            index = SkillIndex(d, None)
            _add_skills_dir(index, os.path.join(d, ".claude", "skills"))
            commands = os.path.join(d, ".claude", "commands")
            for base, dirnames, files in os.walk(commands) if os.path.isdir(commands) else []:
                for f in files:
                    if f.endswith(".md"):
                        index.skills.setdefault(f[:-3], os.path.join(base, f))
        if index is not None:
            _INDEX_CACHE[d] = index
            return index
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def check_skill_refs(ctx):
    """SK010 - shared by skills, rules and agents."""
    index = skill_index_for(ctx.abspath)
    if index is None:
        return
    prose = mask_fences(ctx.fm.body)
    seen = set()
    for m in SKILL_REF_RE.finditer(prose):
        ref = m.group(1)
        if ref in SKILL_REF_PLACEHOLDERS or ref in seen:
            continue
        seen.add(ref)
        if index.resolve(ref) is False:
            ctx.add(line_of(prose, m.start(), ctx.fm.body_line), "SK010",
                    f"Skill({ref}) does not resolve to a skill under {display_path(index.root)} - "
                    f"{RULE_WHY['SK010']}. Fix the name (a plugin skill is `plugin:name`) or remove the reference")


# ---- frontmatter reference (`claude-lint fields`; drives SK017/SK018, AG008/AG009) ----
#
# One table per kind, and the only place this plugin states what a field is:
# the skills point here instead of repeating it. Verified against
# https://code.claude.com/docs/en/skills, /sub-agents and /memory and against
# the frontmatter schemas inside the Claude Code build named by
# TABLES_VERIFIED_AGAINST; `claude-lint drift` repeats the second comparison
# against whatever build is installed.

TABLES_VERIFIED_AGAINST = "2.1.296"

EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
MODEL_ALIASES = ("haiku", "sonnet", "opus", "fable")
# Values the build also takes and the docs' field tables do not list: they are
# not reported, and not offered either.
UNLISTED_VALUES = {
    "model": ("best", "opusplan", "sonnet[1m]", "opus[1m]", "fable[1m]"),
    "isolation": ("remote",),
}
PERMISSION_MODES = ("default", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan")
BOOL = "boolean"
TOOL_LIST = "comma-separated string or YAML list"


@dataclass(frozen=True)
class Field:
    """One frontmatter field. `values` is the closed set when the field is an
    enum, `open_values` says other values are legitimate too (a model id, an
    integer effort), `since` the Claude Code version the docs give, and
    `plugin_ignored` that a plugin-distributed agent's copy is not read."""
    name: str
    type: str
    default: str
    effect: str
    values: tuple = ()
    open_values: str = ""
    since: str = ""
    plugin_ignored: bool = False


@dataclass(frozen=True)
class Reference:
    """Everything `claude-lint fields <kind>` prints. `unlisted` names fields
    the build's schema accepts and the docs do not document: they are not
    typos, so the unknown-field rules stay quiet about them."""
    kind: str
    source: str
    fields: tuple
    notes: tuple
    unlisted: tuple = ()
    aliases: tuple = ()          # (misspelling, the field that was meant)


SKILL_REFERENCE = Reference(
    kind="skill",
    source="https://code.claude.com/docs/en/skills",
    fields=(
        Field("name", "string", "the directory name",
              "the command the `/` menu shows and the user types; the directory name keeps working as a second "
              "way in. In a plugin skill it sets only the last segment (`plugin:name`); a plugin-root SKILL.md "
              "takes its whole final segment from it. Lowercase letters, digits and hyphens"),
        Field("description", "string", "the first non-empty body line",
              "the trigger: what the skill does and when to use it. With `when_to_use`, truncated at 1,536 "
              "characters in the skill listing"),
        Field("when_to_use", "string", "-",
              "extra trigger phrases, appended to `description` in the listing and counted toward the same cap"),
        Field("argument-hint", "string", "-", "autocomplete hint for the arguments, such as `[issue-number]`"),
        Field("arguments", "YAML list or space-separated string", "-",
              "names the positional arguments in order, so the body can use each as `$name`"),
        Field("disable-model-invocation", BOOL, "false",
              "true makes the skill manual-only (`/name`): its description leaves the listing, it cannot be "
              "preloaded into a subagent's `skills`, and a scheduled task cannot fire it"),
        Field("user-invocable", BOOL, "true",
              "false hides the skill from the `/` menu, and typing `/name` does not run it"),
        Field("allowed-tools", "space- or " + TOOL_LIST, "-",
              "tools pre-approved for the turn that invokes the skill; the grant clears on the user's next "
              "message. Not a sandbox: every other tool stays callable. Workspace trust does not gate it; deny "
              "and ask rules still win"),
        Field("disallowed-tools", "space- or " + TOOL_LIST, "-",
              "tools removed from the pool while the skill is active; clears on the user's next message. "
              "Cannot remove EndConversation while any other tool remains"),
        Field("model", "alias, full model id or `inherit`", "the session model",
              "model for the rest of the current turn (the session model resumes on the next prompt); with "
              "`context: fork` it is the forked subagent's model instead",
              values=MODEL_ALIASES + ("inherit",), open_values="a full model id"),
        Field("effort", "enum", "the session effort",
              "effort level while the skill is active; the levels available depend on the model",
              values=EFFORT_LEVELS, open_values="an integer"),
        Field("context", "enum", "inline",
              "`fork` runs the body as the prompt of a fresh subagent, which does not inherit the conversation"
              , values=("fork", "inline")),
        Field("agent", "string", "general-purpose",
              "with `context: fork`, the subagent type that hosts the fork: `Explore`, `Plan`, "
              "`general-purpose` or a custom subagent. `Explore` is read-only and skips CLAUDE.md and git status"),
        Field("background", BOOL, "true",
              "with `context: fork` only: false makes the turn wait for the fork's result. A background fork "
              "gets the narrower background tool set and its edits sit outside `/rewind` checkpoints; headless "
              "and scheduled runs always wait", since="2.1.218"),
        Field("hooks", "map", "-",
              "hooks registered when the skill is first invoked and kept until the session ends; `once: true` "
              "on a handler (honoured only here) drops it after its first successful run"),
        Field("paths", "YAML list or comma-separated string of globs", "-",
              "gates automatic activation to work on matching files; a manual `/name` is not gated. Same glob "
              "format as a rule's `paths`"),
        Field("shell", "enum", "bash", "shell that runs the body's injected commands", values=("bash", "powershell")),
        Field("metadata", "map", "-",
              "free-form data for your own tooling; accepted, not acted on, and a value that is not a map is dropped"),
        Field("license", "string", "-", "licence covering the skill (Agent Skills spec); accepted, not acted on"),
        Field("compatibility", "string, at most 500 characters", "-",
              "environment requirements (Agent Skills spec); accepted, not acted on"),
    ),
    notes=(
        "An unrecognised field is ignored without an error. The docs say a name must match this table exactly; "
        "the build verified here also accepts a known name spelt with different case, hyphens or underscores.",
        "Frontmatter is read only when `---` is the file's first line; YAML that does not parse leaves the "
        "skill loaded with no fields set.",
        "Booleans also accept yes/no/on/off/1/0 in any case (2.1.218 and later).",
        "A `.claude/commands/` file takes the same fields except `name` and `paths`: there the file name is "
        "the command.",
        "claude.ai uploads, the Skills API and `package_skill.py` allow only `name`, `description`, `license`, "
        "`compatibility`, `metadata` and `allowed-tools`; any other field fails the upload with \"Unexpected "
        "key(s) in SKILL.md frontmatter\", and the body grammar does nothing there.",
        "Listing budget: `description` + `when_to_use` are cut at 1,536 characters per skill (the "
        "`skillListingMaxDescChars` setting moves the cap).",
        "The whole skill listing gets 1% of the context window (`skillListingBudgetFraction`); over budget, "
        "names stay while descriptions are dropped starting with the least-invoked skills.",
        "`allowed-tools` Bash rules: `Bash(cmd *)` and `Bash(cmd:*)` match with a wildcard, `Bash(cmd)` only "
        "the bare word; a lowercase `bash(...)` matches nothing; a quoted path must be quoted the same way in "
        "the rule and the command. `claude-lint check-injection` answers whether a given command is covered.",
        "In an `allowed-tools` rule the skill-dir and project-dir variables (and in a plugin skill the "
        "plugin-root and plugin-data ones) expand as they do in the body. `allowManagedPermissionRulesOnly` "
        "ignores the field for project and personal skills.",
        "A fork that needs the conversation history cannot get it from `context: fork`: the user forks the "
        "conversation instead (`/subtask`; `/fork` before 2.1.212).",
    ),
    unlisted=("version", "disallowedTools", "fallback", "created_by", "improved_by", "mcpServers", "lspServers",
              "agents", "outputStyles", "themes", "workflows", "channels", "monitors", "settings", "userConfig",
              "defaultEnabled", "experimental", "dependencies", "displayName", "author", "homepage", "repository",
              "keywords"),
)

AGENT_REFERENCE = Reference(
    kind="agent",
    source="https://code.claude.com/docs/en/sub-agents",
    fields=(
        Field("name", "string", "required",
              "the identifier: at most 256 characters, no `:`, no leading `-`; lowercase letters and hyphens by "
              "convention. In a project or user directory identity comes only from this field, not the file "
              "name or subfolder. A plugin agent is addressed as `plugin:name`, with `agents/` subfolder names "
              "joined in between, and falls back to its file name. Hooks receive it as `agent_type`"),
        Field("description", "string", "required", "the delegation trigger: when Claude should hand work to this agent"),
        Field("tools", TOOL_LIST, "every tool available to subagents, MCP included",
              "allowlist. `mcp__<server>` grants a whole MCP server; if no entry resolves to a tool the agent "
              "refuses to launch; listing `Skill` does not preload skills. Tool-level: `Bash(x *)` grants all "
              "of Bash and pre-approves nothing"),
        Field("disallowedTools", TOOL_LIST, "-",
              "denylist. Applied first, then `tools` resolves against what is left, so a tool in both is "
              "removed. Tool-level: `Bash(git push *)` removes all of Bash"),
        Field("model", "alias, full model id or `inherit`", "see the model resolution note",
              "model the agent runs on", values=MODEL_ALIASES + ("inherit",), open_values="a full model id"),
        Field("permissionMode", "enum", "the main conversation's mode",
              "permission mode the agent runs in (`manual` is an alias for `default`); `dontAsk` auto-denies "
              "anything that would prompt; `bypassPermissions` skips permission prompts, including for writes "
              "to protected paths such as `.git` and `.claude`. See the permission-mode note for when it is "
              "overridden",
              values=PERMISSION_MODES + ("manual",), plugin_ignored=True),
        Field("maxTurns", "positive integer", "-",
              "hard cap on agentic turns; at the limit the agent stops and its output comes back marked partial "
              "and resumable (the marking needs 2.1.246)"),
        Field("skills", "YAML list or comma-separated string", "-",
              "skills preloaded in full at startup, first 32 distinct names. Controls preloading, not access: "
              "unlisted skills stay invocable through the Skill tool. A skill with "
              "`disable-model-invocation: true` cannot be preloaded, and a missing or disabled one is skipped "
              "with only a debug-log warning"),
        Field("mcpServers", "YAML list", "-",
              "an inline definition is scoped to this agent (connected at its start, disconnected at its "
              "finish, never in the main conversation); a string names a session-configured server and shares "
              "its connection. Inline servers in a project agent load only once the folder is trusted",
              plugin_ignored=True),
        Field("hooks", "map", "-",
              "hooks that run only while this agent is active; a `Stop` hook here fires as `SubagentStop`, and "
              "`once` is ignored. A project agent's hooks are skipped until the folder is trusted (a `-p` run "
              "does not count as trust)", plugin_ignored=True),
        Field("memory", "enum", "-",
              "persistent directory across conversations: `user` is ~/.claude/agent-memory/<name>/, `project` "
              ".claude/agent-memory/<name>/, `local` .claude/agent-memory-local/<name>/. Enables Read, Write "
              "and Edit and injects the head of MEMORY.md (200 lines or 25KB). No effect when auto memory is off",
              values=("user", "project", "local")),
        Field("background", BOOL, "false",
              "true keeps the agent in the background even when Claude asks for the foreground. Background "
              "runs get the reduced tool set and surface permission prompts in the main session"),
        Field("omitClaudeMd", BOOL, "false",
              "true launches the agent without the user, project and local CLAUDE.md files (managed policy "
              "files still load); no effect on a main-session agent", since="2.1.271"),
        Field("effort", "enum", "the session effort",
              "effort level while the agent runs; overrides the session effort but not `CLAUDE_CODE_EFFORT_LEVEL`",
              values=EFFORT_LEVELS, open_values="an integer"),
        Field("isolation", "enum", "-",
              "`worktree` runs the agent in a temporary git worktree branched from the default branch, not the "
              "parent session's HEAD; cleaned up automatically if unchanged",
              values=("worktree",)),
        Field("color", "enum", "-", "display colour in the task list and transcript",
              values=("red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan")),
        Field("initialPrompt", "string", "-",
              "auto-submitted first user turn when the agent runs as the main session (`--agent` or the `agent` "
              "setting); not read for a delegated subagent", plugin_ignored=True),
        Field("experimental", "map", "-",
              "experimental options; its `cacheTtl` key (`5m` or `1h`) sets the prompt-cache lifetime of the "
              "agent's requests. Write `cacheTtl` inside the map, not at the top level", since="2.1.248"),
    ),
    notes=(
        "Only `name` and `description` are required; a file missing either is skipped silently. Field names "
        "are camelCase, and an unrecognised field is ignored without an error.",
        "Tools withheld whatever `tools` lists: AskUserQuestion, EnterPlanMode, ExitPlanMode (unless "
        "`permissionMode` is `plan`), ScheduleWakeup, WaitForMcpServers, Workflow, EndConversation, and Agent "
        "at the depth limit.",
        "Background tool set: a subagent running in the background (the default in interactive sessions) "
        "loses every built-in tool outside a fixed set - file, search, shell, web, Skill, TodoWrite and a few "
        "more; MCP tools stay - so one definition can resolve to different tools in the foreground and the "
        "background.",
        "Nesting: a subagent can spawn subagents, three layers below the main conversation by default "
        "(`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`; 1 turns nesting off).",
        "`Agent(type, ...)` in `tools` restricts which types may be spawned only for a main-thread agent "
        "(`claude --agent`); inside a subagent definition the type list is ignored.",
        "Model resolution order (2.1.251 and later): the per-invocation parameter, then `model`, then the "
        "`CLAUDE_CODE_SUBAGENT_MODEL` environment variable, then the main conversation's model.",
        "`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` puts that variable above the `model` field. An alias for the "
        "family the main conversation is already on resolves to the main conversation's exact model.",
        "Permission-mode precedence: when the parent is in `bypassPermissions`, `acceptEdits` or auto mode the "
        "agent runs in that mode and its own `permissionMode` is ignored (under auto the classifier governs).",
        "When the parent is in `default`, `dontAsk` or `plan` the agent's `permissionMode` applies - except "
        "`bypassPermissions`, which an agent cannot grant itself (2.1.267 and later).",
        "Scope precedence when names collide: managed, then CLI `--agents`, then project, then user, then "
        "plugin; among nested project directories the one closest to the working directory wins.",
        "Two files with one name in the same scope directory: one is discarded silently, picked by filesystem "
        "read order.",
        "A plugin-distributed agent ignores `hooks`, `mcpServers`, `permissionMode` and `initialPrompt` "
        "(ship the role as a project or user agent, or move hooks and servers to the plugin's own "
        "hooks/hooks.json and .mcp.json).",
        "A plugin agent's body is the one agent body that is expanded, code spans included: ${CLAUDE_PLUGIN_ROOT}, "
        "${CLAUDE_PLUGIN_DATA} and ${CLAUDE_PROJECT_DIR}, nothing else. Those variables are not in the Bash "
        "tool's environment, so the agent cannot build such a path itself.",
        "Preloaded skills: a bare name is tried as an exact match, then inside the agent's own plugin, then as "
        "any `:name` suffix; `plugin:name` cannot be shadowed by a same-named project skill, while a bare name survives a "
        "plugin rename (observed on 2.1.295; the docs show bare names).",
        "Each preloaded skill arrives headed \"Base directory for this skill: <path>\"; its `allowed-tools` "
        "does not carry into the agent (observed).",
        "`cd` does not persist between an agent's tool calls.",
    ),
    unlisted=("autoCompactWindow", "observer", "observerMessage", "observeSubagents"),
    # The hints Claude Code itself gives in its debug log; it offers none for `mode`.
    aliases=(("allowed-tools", "tools"), ("allowedTools", "tools"), ("when_to_use", "description"),
             ("when-to-use", "description"), ("whenToUse", "description"), ("mode", "")),
)

RULE_REFERENCE = Reference(
    kind="rule",
    source="https://code.claude.com/docs/en/memory",
    fields=(
        Field("paths", "YAML list or one comma-separated string of globs", "unset: the rule loads at launch in every session",
              "scopes the rule: it loads when Claude uses Read, Write or Edit on a matching file. Same glob "
              "format as a skill's `paths`"),
    ),
    notes=(
        "`paths` is the only field. Other keys are ignored without an error and the frontmatter is removed "
        "before the body reaches context, so one file can also carry another tool's keys (Cursor's `globs`).",
        "Quote every glob: one that starts with `*`, `{` or `[` is not valid YAML unquoted, and frontmatter "
        "that fails to parse is dropped - the rule then loads in every session, silently (`claude --debug` "
        "shows the parse error).",
        "A glob with an unbalanced `[` matches nothing; escape a literal one.",
        "Brace groups multiply: a rule's whole `paths` list shares one budget of 1,000 expanded patterns and "
        "4 MiB; patterns without braces do not count against it.",
    ),
)

REFERENCES = {r.kind: r for r in (SKILL_REFERENCE, AGENT_REFERENCE, RULE_REFERENCE)}
COMMAND_FILE_EXCLUDED = ("name", "paths")       # fields a `.claude/commands/` file does not take
PLUGIN_AGENT_DESCRIPTION_ALIASES = ("when_to_use", "when-to-use")   # read as `description` there


def field_named(reference, name):
    """The Field called `name` in a reference table, or None."""
    return next((f for f in reference.fields if f.name == name), None)


def _fold(key):
    """A field name as Claude Code compares it: case, hyphens and underscores removed."""
    return key.replace("-", "").replace("_", "").lower()


def edit_distance(a, b, cap=3):
    """Levenshtein distance between two short strings, cut off at `cap`
    (returns `cap` for anything that far apart or further)."""
    if abs(len(a) - len(b)) >= cap:
        return cap
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        if min(current) >= cap:
            return cap
        previous = current
    return min(previous[-1], cap)


def unknown_field(reference, key, extra_known=()):
    """Judge one frontmatter key against a reference table.

    Returns None when Claude Code reads the key (a table field, one the build
    accepts without documenting, or either spelt with different case or
    separators), else the field it was probably meant to be - from the kind's
    alias list, or the nearest table field within two edits - or "" when
    nothing is close."""
    known = [f.name for f in reference.fields]
    if key in extra_known:
        return None
    alias = dict(reference.aliases).get(key)
    if alias is not None:
        return alias
    if _fold(key) in {_fold(k) for k in known + list(reference.unlisted)}:
        return None
    scored = sorted((edit_distance(key.lower(), k.lower()), k) for k in known)
    return scored[0][1] if scored and scored[0][0] <= 2 else ""


def enum_problem(field, value):
    """Why `value` is not one of a field's allowed values, or None when it is
    (or when the field is not an enum, or the value has a shape the field
    also takes: an integer effort, a full model id)."""
    if not field.values or value is None or isinstance(value, (list, dict)):
        return None
    if isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value).strip()
    # Claude Code lower-cases these three before comparing; the rest are exact.
    seen = text.lower() if field.name in ("effort", "shell", "model") else text
    if not text or seen in field.values or seen in UNLISTED_VALUES.get(field.name, ()):
        return None
    if field.name == "effort" and re.match(r"^\d+$", text):
        return None
    if field.name == "model" and not re.match(r"^[A-Za-z]+$", text):
        return None                      # has a digit, hyphen, dot or colon: a full model id
    allowed = ", ".join(field.values) + (f", or {field.open_values}" if field.open_values else "")
    return f"`{field.name}: {text}` is not one of {allowed}"


def fields_json(reference):
    """A reference table as the plain data `fields --json` prints."""
    def row(f):
        out = {"field": f.name, "type": f.type, "default": f.default, "values": list(f.values) or None,
               "effect": f.effect, "since": f.since or None}
        if f.open_values:
            out["also_accepts"] = f.open_values
        if reference.kind == "agent":
            out["plugin"] = "ignored" if f.plugin_ignored else "read"
        return out
    return {"kind": reference.kind, "source": reference.source, "verified_against": TABLES_VERIFIED_AGAINST,
            "fields": [row(f) for f in reference.fields], "notes": list(reference.notes),
            "unlisted": list(reference.unlisted)}


FIELDS_EFFECT_WIDTH = 110    # the default `fields` view cuts an effect to about this many characters


def _field_type(f):
    """The type column of a field: its closed values when it has them."""
    kind = "|".join(f.values) if f.values else f.type
    return f"{kind} or {f.open_values}" if f.values and f.open_values else kind


def shortened(text, width=FIELDS_EFFECT_WIDTH):
    """`text` cut at the last word that fits in `width` characters and ended
    with `...`; unchanged when it fits."""
    if len(text) <= width:
        return text
    return text[:width + 1].rsplit(" ", 1)[0].rstrip(" ,;:(-") + "..."


def fields_text(reference, full=False):
    """A reference table as compact text: one line per field - the effect cut
    short unless `full` - then the notes, one per line."""
    lines = [f"{reference.kind} frontmatter - Claude Code {TABLES_VERIFIED_AGAINST}, {reference.source}",
             "field | type | default | effect"]
    for f in reference.fields:
        tail = (f" [since {f.since}]" if f.since else "") + (" [ignored in a plugin agent]" if f.plugin_ignored else "")
        lines.append(f"{f.name} | {_field_type(f)} | {f.default} | {f.effect if full else shortened(f.effect)}{tail}")
    if not full and any(len(f.effect) > FIELDS_EFFECT_WIDTH for f in reference.fields):
        lines.append(f"(effects ending in ... are cut short: {self_command('fields', reference.kind, '<field>')} "
                     "prints one field in full, --full the whole table)")
    lines += ["", "notes:"]
    lines.extend(f"- {note}" for note in reference.notes)
    if reference.unlisted:
        lines.append("- Also accepted by this build's schema, undocumented, and not flagged as unknown: "
                     + ", ".join(reference.unlisted) + ".")
    return "\n".join(lines)


def field_text(reference, f):
    """One field of a reference table, every attribute on its own line."""
    lines = [f"{reference.kind} frontmatter field `{f.name}` - Claude Code {TABLES_VERIFIED_AGAINST}, {reference.source}",
             f"type: {f.type}"]
    if f.values:
        lines.append("values: " + ", ".join(f.values) + (f", or {f.open_values}" if f.open_values else ""))
    lines.append(f"default: {f.default}")
    if f.since:
        lines.append(f"since: {f.since}")
    if reference.kind == "agent":
        lines.append("in a plugin agent: " + ("ignored" if f.plugin_ignored else "read"))
    lines.append(f"effect: {f.effect}")
    return "\n".join(lines)


# ---- file-keyed triggers (SK016, AG007) ---------------------------------------
#
# A description is a request matcher: the model reads it and judges whether
# the user's request fits. Wording such as "use whenever editing any SKILL.md"
# keys the trigger on a file instead, and whether the skill then loads when
# that file is touched is still a judgement - where a path-scoped rule or a
# hook would be a guarantee. Heuristic, tuned for precision on 71 real
# descriptions (the tests hold the representative ones as literal strings):
#
#   * the text is cut into sentences (parentheses cut too), and each sentence
#     into trigger segments, one per cue word: when, whenever, while, after,
#     before, if, "any time", "every time";
#   * a segment is file-keyed when it holds a file-action verb and a path-like
#     token within FILE_KEY_WINDOW characters of each other;
#   * unless the segment says the file comes from the user ("if the user
#     mentions a .pdf", "when asked to review the .claude/ tree"): that is a
#     request, which is what a description is for.

FILE_KEY_WINDOW = 100
_TRIGGER_CUE_RE = re.compile(r"\b(?:when(?:ever)?|while|after|before|if|(?:any|every|each)\s+time)\b", re.I)
_FILE_VERB_RE = re.compile(
    r"\b(?:writ(?:e|es|ing|ten)|wrote|edit(?:s|ed|ing)?|review(?:s|ed|ing)?|touch(?:es|ed|ing)?|"
    r"modif(?:y|ies|ied|ying)|chang(?:e|es|ed|ing)|open(?:s|ed|ing)?(?!-)|creat(?:e|es|ed|ing)|"
    r"work(?:s|ed|ing)?\s+(?:on|in))\b", re.I)
_USER_SUPPLIED_RE = re.compile(
    r"\b(?:users?|person|people|someone|anyone|they|he|she)\b[^.;]{0,60}?\b(?:wants?|asks?|asked|mentions?|"
    r"provides?|uploads?|attach(?:es|ed)?|references?|says?|requests?|gives?|shares?|pastes?|names?|hands?|sends?)\b"
    r"|\b(?:asked|told|requested)\b|\b(?:uploaded|attached|provided|mentioned)\b", re.I)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;!?])\s+|\n+|[()]")
_URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.I)
_NAMED_FILE_RE = re.compile(r"(?<![\w./-])(?:Dockerfile|Makefile)\b")
_FILE_NAME_RE = re.compile(r"(?<![\w./*-])[\w-]+(?:\.[\w-]+)*\.([A-Za-z][A-Za-z0-9]{0,5})\b(?![/(])")
_BARE_EXT_RE = re.compile(r"(?<![\w/.*])\.(?:claude|github|vscode|[a-z][a-z0-9]{1,4})\b(?![/(.])")
_SLASH_TOKEN_RE = re.compile(r"(?<![\w/.*~{-])(?:~|\.{1,2}|\*{1,2})?/?[\w.*{},\[\]-]+(?:/[\w.*{},\[\]-]*)+")
_GLOB_RE = re.compile(r"(?<![\w/])\*{1,2}[./][\w.*{},/-]+")
# `name.ext` shapes that are libraries or products, not files.
_NOT_FILES = frozenset({"node.js", "next.js", "vue.js", "p5.js", "three.js", "d3.js", "react.js", "express.js",
                        "nuxt.js", "claude.ai"})
_FILE_EXTENSIONS = AT_KNOWN_EXT | frozenset("c4 tcss docx dotx xlsx xlsm pptx potx env gitignore lockb".split())


def path_like_tokens(text):
    """(offset, token) for each token in `text` that names a file or a place
    in a tree: a path with a path's shape (`.claude/agents/`, `src/`,
    `~/x/y`, `a/b.ts` - not `and/or`, `read/write` or a `/command`), a glob, a
    `name.ext` with a known extension, a bare extension (`.tcss`), or a
    Dockerfile or Makefile."""
    text = _URL_RE.sub(lambda m: " " * len(m.group(0)), text)
    found = {}
    for m in _SLASH_TOKEN_RE.finditer(text):
        token = m.group(0).rstrip(".,")
        segments = [s for s in token.split("/") if s]
        last = token.rsplit("/", 1)[-1]
        shaped = (token.startswith((".", "~", "*")) or "*" in token or token.endswith("/")
                  or bool(re.search(r"\.[A-Za-z][A-Za-z0-9]{0,5}$", last))
                  or (token.startswith("/") and len(segments) >= 2))
        if shaped and re.search(r"[A-Za-z]", token):
            found[m.start()] = token
    for m in _GLOB_RE.finditer(text):
        found.setdefault(m.start(), m.group(0).rstrip(".,"))
    for m in _FILE_NAME_RE.finditer(text):
        if m.group(1).lower() in _FILE_EXTENSIONS and m.group(0).lower() not in _NOT_FILES:
            found.setdefault(m.start(), m.group(0))
    for regex in (_BARE_EXT_RE, _NAMED_FILE_RE):
        for m in regex.finditer(text):
            found.setdefault(m.start(), m.group(0))
    covered, out = -1, []
    for start in sorted(found):
        if start >= covered:
            out.append((start, found[start]))
            covered = start + len(found[start])
    return out


def file_keyed_triggers(text):
    """(verb, path token, segment) for each trigger segment of a description
    that keys on which file is being touched; see the section notes."""
    hits = []
    for sentence in _SENTENCE_SPLIT_RE.split(text or ""):
        cues = [m.start() for m in _TRIGGER_CUE_RE.finditer(sentence)]
        for start, end in zip(cues, cues[1:] + [len(sentence)]):
            segment = sentence[start:end]
            if _USER_SUPPLIED_RE.search(segment):
                continue
            verbs = [(m.start(), m.group(0)) for m in _FILE_VERB_RE.finditer(segment)]
            for at, token in path_like_tokens(segment):
                near = [verb for pos, verb in verbs if abs(pos - at) <= FILE_KEY_WINDOW]
                if near:
                    hits.append((near[-1] if verbs[0][0] > at else near[0], token, " ".join(segment.split())))
                    break
    return hits


# ---- per-kind checks --------------------------------------------------------

class Ctx:
    def __init__(self, abspath, shown, text=None):
        self.abspath = abspath
        self.shown = shown
        self.text = text
        self.fm = parse_frontmatter(text) if text is not None else None
        self.findings = []

    def add(self, line, rule_id, message, severity=None, path=None):
        self.findings.append(Finding(path or self.shown, line, rule_id, message, severity))


def _truthy(v):
    return v is True or (isinstance(v, str) and v.lower() == "true")


def _falsy(v):
    return v is False or (isinstance(v, str) and v.lower() == "false")


def _link_target(raw):
    """Normalise a markdown link target to a relative file path, or None to skip."""
    from urllib.parse import unquote
    t = raw.strip()
    if not t or t.startswith(("#", "/", "~")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", t):
        return None
    if any(c in t for c in "<>{}$*"):
        return None
    t = unquote(t.split("#", 1)[0].split("?", 1)[0])
    return t or None


def dead_links(text, base_dir, first_line=1):
    """(line, target) for each relative markdown link that does not exist."""
    prose = mask_spans(mask_fences(text))
    out = []
    for m in MD_LINK_RE.finditer(prose):
        target = _link_target(m.group(1))
        if target and not os.path.exists(os.path.join(base_dir, target)):
            out.append((line_of(prose, m.start(), first_line), target))
    for m in MD_SPACED_LINK_RE.finditer(prose):
        target = m.group(1).strip()
        if "://" not in target and not os.path.exists(os.path.join(base_dir, target)):
            out.append((line_of(prose, m.start(), first_line), target))
    return sorted(out)


SKILL_ENUM_FIELDS = ("effort", "context", "shell")
AGENT_ENUM_FIELDS = ("color", "effort", "permissionMode", "model", "memory", "isolation")


def check_frontmatter_fields(ctx, reference, unknown_id, enum_id, enum_fields, not_taken=(), extra_known=()):
    """SK017/AG008 and SK018/AG009: every key against the kind's reference
    table, and the enum fields' values against their sets."""
    fm = ctx.fm
    for key in fm.data:
        if key in not_taken:
            ctx.add(fm.line(key), unknown_id,
                    f"`{key}` is not read in a `.claude/commands/` file: a command file takes every skill field "
                    f"except {' and '.join('`' + k + '`' for k in not_taken)}, and the file name is the command - "
                    "the field is ignored without an error. Remove it, or move the command to a skill directory")
            continue
        meant = unknown_field(reference, key, extra_known)
        if meant is not None:
            hint = f"; did you mean `{meant}`?" if meant else ""
            ctx.add(fm.line(key), unknown_id,
                    f"`{key}` is not a field Claude Code reads in {reference.kind} frontmatter{hint} - "
                    f"{RULE_WHY[unknown_id]}. Fix the name or remove it "
                    f"(`{self_command('fields', reference.kind)}` lists the fields)")
            continue
        field = field_named(reference, key)
        problem = enum_problem(field, fm.get(key)) if field and key in enum_fields else None
        if problem:
            ctx.add(fm.line(key), enum_id, f"{problem} - {RULE_WHY[enum_id]}. Use a listed value or remove the field")


def check_file_keyed(ctx, rule_id, keys):
    """SK016/AG007: one finding per field whose text keys the trigger on a file."""
    for key in keys:
        value = ctx.fm.get(key)
        hits = file_keyed_triggers(value) if isinstance(value, str) else []
        if hits:
            verb, token, segment = hits[0]
            if len(segment) > 90:
                segment = segment[:90].rsplit(" ", 1)[0] + " ..."
            segment = re.sub(r"[\s,;]+(?:(?:and|or)\b)?[\s,]*$", "", segment)
            more = f" (and {len(hits) - 1} more)" if len(hits) > 1 else ""
            ctx.add(ctx.fm.line(key), rule_id,
                    f"`{key}` keys the trigger on a file: \"{segment}\"{more} ties `{verb}` to "
                    f"`{token}` - {RULE_WHY[rule_id]}. Describe the request that should trigger this, and move "
                    "what must hold whenever such a file is touched into a path-scoped rule or a hook")


def lint_skill(ctx):
    fm, body, first = ctx.fm, ctx.fm.body, ctx.fm.body_line
    skill_dir = os.path.dirname(ctx.abspath)
    is_skill_md = os.path.basename(ctx.abspath) == "SKILL.md"

    name = fm.get("name")
    if "name" in fm.data:
        if not isinstance(name, str) or not NAME_RE.match(name):
            ctx.add(fm.line("name"), "SK001",
                    f"name {name!r} must be lowercase letters, digits and hyphens only - {RULE_WHY['SK001']}. "
                    "Rename it, or drop `name` and let the directory name be the command")
        elif is_skill_md and name != os.path.basename(skill_dir):
            ctx.add(fm.line("name"), "SK002",
                    f"name '{name}' differs from its directory '{os.path.basename(skill_dir)}' - "
                    f"{RULE_WHY['SK002']}. Rename one to match, or drop `name`")

    desc = fm.get("description") if isinstance(fm.get("description"), str) else ""
    when = fm.get("when_to_use") if isinstance(fm.get("when_to_use"), str) else ""
    total = len(desc.strip()) + len(when.strip())
    if total > DESC_CAP:
        ctx.add(fm.line("description") if "description" in fm.lines else fm.line("when_to_use"), "SK003",
                f"description + when_to_use is {total} characters; the cap is {DESC_CAP} - {RULE_WHY['SK003']}. "
                "Put the key use case first and cut the rest")

    if _truthy(fm.get("disable-model-invocation")) and _falsy(fm.get("user-invocable")):
        ctx.add(fm.line("user-invocable"), "SK004",
                "disable-model-invocation: true with user-invocable: false means the skill can never run - "
                f"{RULE_WHY['SK004']}. Remove one of the two")

    command_file = not is_skill_md and in_claude_dir(ctx.abspath, "commands")
    check_frontmatter_fields(ctx, SKILL_REFERENCE, "SK017", "SK018", SKILL_ENUM_FIELDS,
                             not_taken=COMMAND_FILE_EXCLUDED if command_file else ())
    check_file_keyed(ctx, "SK016", ("description", "when_to_use"))

    directives = find_directives(body, first)
    all_lines = (ctx.text or "").split("\n")
    consumed = ("a skill body is a template, so this is executed or substituted at load, code span or not. Move "
                "literal syntax examples into a references/ file, which is not preprocessed")
    allowed = fm.get("allowed-tools")
    declared = fm.get("arguments")
    if isinstance(declared, str):
        declared = declared.replace(",", " ").split()
    argument_names = tuple(a for a in declared if isinstance(a, str)) if isinstance(declared, list) else ()
    outside = skill_dir_is_outside(ctx.abspath)
    for d in directives:
        shown_cmd = d.command.replace("\n", " ")[:50] or "(empty)"
        first_word = d.command.split()[0] if d.command.split() else ""
        placeholder = (not d.command or first_word in PLACEHOLDER_WORDS or d.quoted
                       or bool(ANGLE_PLACEHOLDER_RE.search(d.command)))
        has_fallback = has_failure_fallback(d.command)
        if not has_fallback:
            ctx.add(d.line, "SK005",
                    f"injection `{shown_cmd}` has no fallback - a command that exits non-zero aborts the whole "
                    "skill load, with or without `2>/dev/null`, and Claude sees only \"Shell command failed\". "
                    "End it with `|| echo \"<what is missing>\"`")
        if placeholder:
            # Only what reads as documentation. A real command with no fallback
            # is SK005's alone: saying it twice helped nobody.
            ctx.add(d.line, "SK012", f"placeholder injection `{shown_cmd}` will be executed, not shown - {consumed}")
        if not placeholder:
            for problem in injection_problems(d.command, allowed, outside, argument_names):
                ctx.add(d.line, "SK013", problem.message())
        if not placeholder and UNBOUNDED_RE.search(d.command) and not BOUNDED_RE.search(d.command):
            ctx.add(d.line, "SK006",
                    f"injection `{shown_cmd}` looks unbounded - {RULE_WHY['SK006']}. Cap it (for example "
                    "`| head -50`, `--stat`, `-maxdepth 2`)")
        lo, hi = max(d.line - 1, 1), min(d.end_line + 1, len(all_lines))
        for n in range(lo, hi + 1):
            if SECRET_RE.search(all_lines[n - 1]):
                ctx.add(n, "SK007",
                        "secret-looking literal on or next to an injection line - injected output enters the "
                        "prompt, and so does anything the command echoes. Have an approved script read the "
                        "secret from the environment instead")
                break

    fenceless = mask_fences(body)
    for line, token in described_tokens(fenceless, first):
        ctx.add(line, "SK012", f"`{token}` is described here but will be replaced - {consumed}")

    body_lines = len(body.rstrip("\n").split("\n")) if body.strip() else 0
    if body_lines > SKILL_BODY_MAX_LINES:
        ctx.add(first, "SK008",
                f"body is {body_lines} lines; the target is at most {SKILL_BODY_MAX_LINES} - {RULE_WHY['SK008']}. "
                "Keep what must always be read at the top and move detail to references/ and scripts/")

    # SK009: markdown links, bundled references/ and scripts/ paths, @file refs.
    reported = set()
    for line, target in dead_links(body, skill_dir, first):
        reported.add(os.path.normpath(target))
        ctx.add(line, "SK009", f"link target '{target}' does not exist - {RULE_WHY['SK009']}. "
                               "Fix the path or add the file")
    index = skill_index_for(ctx.abspath)
    sibling_dirs = sorted({os.path.dirname(p) for p in index.skills.values()}) if index else []

    def bundled(line, rel, strict):
        if rel in reported or os.path.exists(os.path.join(skill_dir, rel)):
            return
        if not strict and any(os.path.exists(os.path.join(s, rel)) for s in sibling_dirs):
            return  # prose mention of another skill's bundled file
        reported.add(rel)
        ctx.add(line, "SK009", f"'{rel}' does not exist under {display_path(skill_dir)} - {RULE_WHY['SK009']}. "
                               "Fix the path or add the file")

    for m in BUNDLED_PATH_RE.finditer(body):
        if m.group(1) and "." in os.path.basename(m.group(2)):
            bundled(line_of(body, m.start(), first), m.group(2), True)
    for m in BUNDLED_PATH_RE.finditer(fenceless):
        if not m.group(1) and "." in os.path.basename(m.group(2)):
            bundled(line_of(fenceless, m.start(), first), m.group(2), False)
    spanless = mask_spans(fenceless)
    for m in AT_REF_RE.finditer(spanless):
        bundled(line_of(spanless, m.start(), first), os.path.normpath(m.group(1)), True)

    # SK015: at-sign paths that are attached at load although they read as documentation.
    scope, scope_root = skill_scope(ctx.abspath)
    flagged = set()
    for line, token, context in at_file_refs(body, first):
        if "$" in token or not AT_PATHISH_RE.match(token) or (line, token) in flagged:
            continue                      # a substituted path is deliberate; odd characters are not a path
        rooted = token.startswith(("/", "~"))
        in_skill = not rooted and os.path.exists(os.path.join(skill_dir, token))
        if scope == "project":
            # Here the working directory is known well enough to check: a prose
            # reference that resolves is the documented feature, working.
            in_cwd = os.path.exists(os.path.expanduser(token) if rooted else os.path.join(scope_root, token))
            if (in_cwd and context == "prose") or not (in_cwd or in_skill):
                continue
        else:
            in_cwd = rooted and os.path.exists(os.path.expanduser(token))
            in_root = bool(scope_root) and not rooted and os.path.exists(os.path.join(scope_root, token))
            if not (looks_like_a_file(token) or in_skill or in_cwd or in_root):
                continue
            if not (in_skill or in_cwd or in_root):
                # A file-shaped name that resolves nowhere the linter can look.
                # OBSERVED on 2.1.295: a reference to a file that does not exist
                # attaches nothing, and a plugin or personal skill's working
                # directory is the user's project, which is not visible from
                # here - so this is a note, not a warning.
                flagged.add((line, token))
                ctx.add(line, "SK015",
                        f"`@{token}` reads as a file reference: attached if a file of this name exists in the "
                        "session's working directory, which the linter cannot see for a plugin or personal skill "
                        f"(nothing of that name is at the plugin root or beside the skill). Write `` `@{token}` `` "
                        "- the at-sign directly after the backtick - if it is an example", "info")
                continue
        flagged.add((line, token))
        where = {"fence": " - a fenced block does not protect it", "prose": "",
                 "span": " - a code span protects it only when the `@` comes directly after the backtick"}[context]
        if in_skill and not in_cwd:
            where += f" - and not from {display_path(skill_dir)}, where this file is"
        ctx.add(line, "SK015",
                f"`@{token}` is a file reference: its content (a directory's listing; only the named lines with a "
                "`#L<n>-<m>` suffix) is attached if a file of that name exists in the session's working directory "
                f"when the skill loads{where}. Put it directly inside an inline code span "
                f"(`` `@{token}` ``) if it is an example, or use `${{CLAUDE_SKILL_DIR}}` with an explicit Read "
                "instruction if a bundled file is meant")

    check_skill_refs(ctx)


def described_tokens(fenceless, first_line=1):
    """SK012: (line, token) for substitution tokens that are being described
    rather than used, in a body with its fenced blocks already blanked. One
    hit per line. Heuristic, tuned on the skill bodies this plugin shipped
    before the bug was understood (see the tests):

    - a token inside a bolded code span - the usual shape of a reference entry;
    - `$ARGUMENTS`, `$ARGUMENTS[N]` or a ${CLAUDE_...} variable alone in a code
      span - the span is exactly the token - unless it sits in a value
      position ("lives at `...`.", "Directory: `...`") with no gloss after it.
      A span that holds more (a path built from the variable, a command that
      takes the arguments) is a use, not a description;
    - `$0` or `$1` alone in a code span, under the same exception, when the
      rest of the line speaks of arguments, placeholders or substitution
      (alone in a span it is otherwise as likely awk or shell);
    - `$0`/`$1`-style alternatives, and "no `$ARGUMENTS`";
    - a token inside an escaped directive example."""
    hits = {}
    lines = fenceless.split("\n")
    for idx, line in enumerate(lines):
        if "$" not in line:
            continue
        for regex in (DOC_TOKEN_RE, ARG_ALTERNATIVES_RE, NEGATED_ARG_RE, ESCAPED_EXAMPLE_RE):
            m = regex.search(line)
            if m:
                hits.setdefault(idx, m.group(1))
        spans = list(BARE_TOKEN_SPAN_RE.finditer(line))
        if "`$" in line and ARGUMENT_TALK_RE.search(BARE_INDEX_SPAN_RE.sub(" ", line)):
            spans = sorted(spans + list(BARE_INDEX_SPAN_RE.finditer(line)), key=lambda m: m.start())
        for m in spans:
            before, after = line[max(m.start() - 80, 0):m.start()], line[m.end():m.end() + 8]
            if not before.strip(" >*-\t") and idx > 0:
                before = lines[idx - 1][-80:] + " " + before  # the sentence wrapped
            if VALUE_LEAD_RE.search(before) and not GLOSS_FOLLOWS_RE.match(after):
                continue
            hits.setdefault(idx, m.group(1))
    return [(first_line + idx, token) for idx, token in sorted(hits.items())]


def _numbered_steps(ctx, rule_id, what):
    prose = mask_fences(ctx.fm.body).split("\n")
    hits = [i for i, ln in enumerate(prose) if NUMBERED_RE.match(ln)]
    if hits:
        ctx.add(ctx.fm.body_line + hits[0], rule_id,
                f"{len(hits)} numbered step line(s) in {what} - {RULE_WHY[rule_id]}. Move the procedure to a "
                "skill and leave the constraint here")


YAML_NEEDS_QUOTES = "*&![{%@`|>"   # a plain (unquoted) YAML scalar cannot start with any of these


def unclosed_bracket(glob):
    """Does the glob open a `[` character class that it never closes? A
    backslash escapes the next character, and a `]` with no `[` is literal."""
    i, open_at = 0, None
    while i < len(glob):
        c = glob[i]
        if c == "\\":
            i += 2
            continue
        if c == "[" and open_at is None:
            open_at = i
        elif c == "]" and open_at is not None and i > open_at + 1:
            open_at = None
        i += 1
    return open_at is not None


def brace_expansion_count(glob):
    """How many patterns a glob becomes once its brace groups are expanded:
    `src/*.{ts,tsx}` is 2 and `{a,b}/{c,d}/*.{ts,tsx}` is 8; 1 with no group.
    Groups nest, and a backslash escapes the next character."""
    def sequence(i, nested):
        total = 1
        while i < len(glob):
            c = glob[i]
            if c == "\\":
                i += 2
            elif c == "{":
                alternatives, i = group(i + 1)
                total *= alternatives
            elif nested and c in ",}":
                break
            else:
                i += 1
        return total, i

    def group(i):
        counts = []
        while True:
            n, i = sequence(i, True)
            counts.append(n)
            if i >= len(glob) or glob[i] == "}":
                return (sum(counts) if len(counts) > 1 else counts[0]), i + 1
            i += 1                       # the comma

    return sequence(0, False)[0]


def paths_expansion_total(globs):
    """Expanded patterns over a whole `paths` list. A pattern with no brace
    group does not count against the budget."""
    return sum(brace_expansion_count(g) for g in globs if "{" in g)


PARSE_FAILURE = ("frontmatter that fails to parse is dropped, and the rule then loads in every session, silently "
                 "(`claude --debug` shows the parse error)")


def _glob_problem(raw, value=None):
    """What is wrong with one `paths` glob, as (severity, text), or None. `raw`
    is the glob as written and `value` what YAML makes of it (a doubled
    backslash inside double quotes is one). A plain glob such as
    src/api/**/*.ts is fine; quoting is needed only where YAML needs it."""
    if not isinstance(raw, str) or not raw.strip():
        return "error", "is empty - an empty pattern matches no file. Remove it or write the glob"
    if _is_quoted(raw):
        inner = value if isinstance(value, str) else raw[1:-1]
    else:
        inner = raw
        if raw[0] in YAML_NEEDS_QUOTES:
            return "error", (f"must be quoted: a plain YAML scalar cannot start with '{raw[0]}' - {PARSE_FAILURE}. "
                             "Put the glob in double quotes")
        if ": " in raw:
            return "error", f"must be quoted: it contains ': ' - {PARSE_FAILURE}. Put the glob in double quotes"
    if not inner.strip():
        return "error", "is empty - an empty pattern matches no file. Remove it or write the glob"
    if unclosed_bracket(inner):
        return "warn", ("has an unclosed `[` - a glob with an unbalanced `[` matches nothing, so the rule never "
                        "loads for these files. Close the class, or escape a literal bracket as `\\[`")
    if inner.replace("\\{", "").count("{") != inner.replace("\\}", "").count("}"):
        return "error", "has unbalanced {} - the brace group cannot expand as written. Close it or remove it"
    return None


def lint_rule(ctx):
    fm, body, first = ctx.fm, ctx.fm.body, ctx.fm.body_line
    total = len((ctx.text or "").rstrip("\n").split("\n"))
    if total > RULE_MAX_LINES:
        ctx.add(1, "RU001", f"file is {total} lines; the target is at most {RULE_MAX_LINES} - {RULE_WHY['RU001']}. "
                            "Split it by topic, and move reference material to a skill's supporting files")

    for line, what in live_grammar(body, first):
        ctx.add(line, "RU002", f"{what} is skill-body grammar - {RULE_WHY['RU002']}. State the constraint in "
                               "words, or put the syntax in a code span if it is an example")

    _numbered_steps(ctx, "RU003", "a rule")

    lines = body.split("\n")
    idx = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if idx is not None and re.match(r"^#\s", lines[idx]):
        idx = next((i for i in range(idx + 1, len(lines)) if lines[i].strip()), None)
    if idx is None or not re.match(r"^Applies (when|to)\b", lines[idx].strip()):
        ctx.add(first + (idx or 0), "RU004",
                f"no opening line stating when the rule applies - {RULE_WHY['RU004']}. Start the body with "
                "\"Applies when ...\" or \"Applies to ...\"")

    unparsed = None
    if "paths" not in fm.data:
        ctx.add(1, "RU005", f"no `paths:` frontmatter - {RULE_WHY['RU005']}. Scope it to the files it governs, or "
                            "mark a deliberately global rule with <!-- claude-lint-disable RU005 -->")
    else:
        value, raw, line = fm.get("paths"), fm.raw.get("paths"), fm.line("paths")
        rest = fm.rest.get("paths", "")
        # `paths: [ab]*.ts` and `paths: {a,b}/**` read as a broken flow list or
        # mapping, not as a glob: say so instead of reporting the parse debris.
        bare_bracket = rest.startswith("[") and "]" in rest and not rest.endswith("]")
        if bare_bracket or rest.startswith("{"):
            ctx.add(line, "RU006", f"paths value {rest!r} must be quoted: a plain YAML scalar cannot "
                                   f"start with '{rest[0]}' - {PARSE_FAILURE}. Put the glob in double quotes")
            unparsed = line
        elif (isinstance(value, list) and value) or (isinstance(value, str) and value.strip()):
            listed = isinstance(value, list)
            raws = raw if listed else [raw]
            for item_raw, item in zip(raws, value if listed else [value]):
                problem = _glob_problem(item_raw, item)
                if problem:
                    ctx.add(line, "RU006", f"paths {'entry' if listed else 'value'} {item_raw!r} {problem[1]}",
                            problem[0])
            globs = [g for g in (value if listed else str(value).split(",")) if isinstance(g, str)]
            expanded = paths_expansion_total(globs)
            if expanded > PATHS_EXPANSION_MAX:
                ctx.add(line, "RU006",
                        f"`paths` expands to {expanded:,} patterns; the budget is {PATHS_EXPANSION_MAX:,} - each "
                        "brace group multiplies the count, and a rule's whole list shares one budget. Replace "
                        "brace groups with `*` or `**` where the alternatives are not needed", "warn")
        else:
            ctx.add(line, "RU006", "`paths:` must be a glob or a non-empty YAML list of globs - as written it "
                                   "scopes nothing. Write the globs, or remove the key for a global rule")
    for line, message in fm.errors:
        if line != unparsed:
            ctx.add(line, "RU006", f"{message} - {PARSE_FAILURE}. Fix the YAML")

    rule_dir = os.path.dirname(ctx.abspath)
    for line, target in memory_imports(body):
        line += first - 1
        if target.startswith("~/"):
            where = None                  # machine-specific: cannot be judged from the repo
        else:
            where = os.path.normpath(os.path.join(rule_dir, target))
        if where is not None and not os.path.isfile(where):
            bare = target.rstrip(IMPORT_TRAILING)
            if _import_looking(bare):
                ctx.add(line, "RU007",
                        f"@{target} does not resolve from {display_path(rule_dir)} - an import in a rule expands "
                        "relative to the rule file, and one that does not resolve imports nothing, silently. Fix "
                        "the path (the project root from .claude/rules/ is `../../`), or put it in a code span "
                        "if it is an example")
            continue
        size = ""
        if where is not None:
            try:
                size = f" ({len(read_text(where).splitlines())} lines)"
            except OSError:
                size = ""
        ctx.add(line, "RU007",
                f"@{target} is an import{size} - {RULE_WHY['RU007']}. State the constraint here instead, put the "
                "path in a code span if it is only a mention, or keep a deliberate import with "
                "<!-- claude-lint-disable RU007 -->")

    check_skill_refs(ctx)


def agent_scope_root(path):
    """The directory whose agent names must be unique for this file: the
    `.claude/agents/` (or plugin `agents/`) directory above it, subfolders
    included - or None when the file is not under one."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        up = os.path.dirname(d)
        if os.path.basename(d) == "agents" and (os.path.basename(up) == ".claude" or _is_plugin_root(up)):
            return d
        if up == d:
            return None
        d = up


_AGENT_NAMES = {}        # scope root -> {name: [paths]}, for one lint run


def agent_names_in(scope_root):
    """{declared name: [agent files]} for every .md under a scope directory."""
    if scope_root not in _AGENT_NAMES:
        names = {}
        for base, dirnames, files in os.walk(scope_root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for f in sorted(files):
                if not f.endswith(".md"):
                    continue
                path = os.path.join(base, f)
                try:
                    name = parse_frontmatter(read_text(path)).get("name")
                except OSError:
                    continue
                if isinstance(name, str) and name.strip():
                    names.setdefault(name.strip(), []).append(path)
        _AGENT_NAMES[scope_root] = names
    return _AGENT_NAMES[scope_root]


def agent_name_problems(name):
    """Every reason Claude Code skips an agent file with this `name`; empty when it loads."""
    checks = (
        (name.startswith("-"), "starts with `-`"),
        (":" in name, "contains `:`, which is reserved for plugin namespacing"),
        (len(name) > AGENT_NAME_MAX, f"is {len(name)} characters; the limit is {AGENT_NAME_MAX}"),
    )
    return tuple(problem for failed, problem in checks if failed)


def lint_agent(ctx):
    fm, body, first = ctx.fm, ctx.fm.body, ctx.fm.body_line
    name, desc = fm.get("name"), fm.get("description")
    parent = os.path.dirname(ctx.abspath)
    plugin_agent = os.path.basename(parent) == "agents" and _is_plugin_root(os.path.dirname(parent))
    skipped = "Claude Code skips the file, and only the debug log says so"
    if not isinstance(name, str) or not name.strip():
        ctx.add(fm.line("name"), "AG001", f"`name` is required - without it {skipped}. Add `name: <identifier>`")
    elif agent_name_problems(name):
        for problem in agent_name_problems(name):
            ctx.add(fm.line("name"), "AG001", f"name {name[:40]!r} {problem} - {skipped}. Rename it")
    elif not NAME_RE.match(name):
        ctx.add(fm.line("name"), "AG001",
                f"name {name!r} is not lowercase letters, digits and hyphens - a convention only: Claude Code "
                "loads the agent, but every documented name has that shape and it is what `subagent_type` and "
                "`--agent` are typed as. Rename it to match", "warn")
    if not isinstance(desc, str) or not desc.strip():
        ctx.add(fm.line("description"), "AG001",
                f"`description` is required - without it {skipped}. Add one that says when to delegate to this agent")

    scope_root = agent_scope_root(ctx.abspath)
    if scope_root and isinstance(name, str) and name.strip():
        twins = [p for p in agent_names_in(scope_root).get(name.strip(), []) if p != ctx.abspath]
        if plugin_agent:                 # a plugin agent's subfolder is part of its identifier
            twins = [p for p in twins if os.path.dirname(p) == parent]
        if twins:
            ctx.add(fm.line("name"), "AG010",
                    f"name '{name}' is also declared by {display_path(twins[0])}"
                    + (f" (and {len(twins) - 1} more)" if len(twins) > 1 else "")
                    + f" in the same agents directory - {RULE_WHY['AG010']}. Rename one of them")

    check_frontmatter_fields(ctx, AGENT_REFERENCE, "AG008", "AG009", AGENT_ENUM_FIELDS,
                             extra_known=PLUGIN_AGENT_DESCRIPTION_ALIASES if plugin_agent else ())
    check_file_keyed(ctx, "AG007", ("description",))

    for line, what in live_grammar(body, first):
        if what in PLUGIN_AGENT_VARS:
            if not plugin_agent:
                ctx.add(line, "AG002", f"{what} is expanded only in a plugin-distributed agent's body; here it "
                                       "arrives as literal text. Write the real path, or ship the agent in a plugin")
            continue
        ctx.add(line, "AG002", f"{what} is skill-body grammar - {RULE_WHY['AG002']}" + (
            " (a plugin agent's body expands only ${CLAUDE_PLUGIN_ROOT}, ${CLAUDE_PLUGIN_DATA} and "
            "${CLAUDE_PROJECT_DIR})" if plugin_agent else "")
            + ". Say it in words, or move the dynamic part into a skill the agent preloads")

    if _truthy(fm.get("background")) and "maxTurns" not in fm.data:
        ctx.add(fm.line("background"), "AG003",
                "background: true without maxTurns - `maxTurns` is the runaway guard for an agent nobody is "
                "watching; at the limit it stops and its output comes back marked partial. Set it to the "
                "role's real task length")

    skills = fm.get("skills")
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    if isinstance(skills, list):
        index = skill_index_for(ctx.abspath)
        distinct = list(dict.fromkeys(ref for ref in skills if isinstance(ref, str)))
        if len(distinct) > AGENT_SKILLS_MAX:
            ctx.add(fm.line("skills"), "AG004",
                    f"`skills` lists {len(distinct)} names; only the first {AGENT_SKILLS_MAX} are preloaded - "
                    f"'{distinct[AGENT_SKILLS_MAX]}' and everything after it is dropped without a message. "
                    "Preload fewer, or merge skills")
        for ref in skills:
            if not isinstance(ref, str) or index is None:
                continue
            resolved = index.resolve(ref)
            if resolved is False:
                ctx.add(fm.line("skills"), "AG004",
                        f"preloaded skill '{ref}' does not resolve under {display_path(index.root)} - a missing "
                        "skill is skipped with only a debug-log warning, so the agent starts without it. Fix "
                        "the name (after a rename, check every agent that preloads it)")
            elif resolved and index.disables_model_invocation(ref):
                ctx.add(fm.line("skills"), "AG004",
                        f"preloaded skill '{ref}' sets disable-model-invocation: true - such a skill cannot be "
                        "preloaded and is skipped with only a debug-log warning. Drop the flag on the skill, or "
                        "remove it from `skills`")

    if plugin_agent:
        for key in PLUGIN_AGENT_IGNORED:
            if key in fm.data:
                ctx.add(fm.line(key), "AG005",
                        f"`{key}` is ignored on a plugin-distributed agent - Claude Code does not read it there, "
                        "so a role that depends on it does not get it. Ship the agent as a project or user "
                        "agent, or move hooks and servers to the plugin's own hooks/hooks.json and .mcp.json")

    for field in ("tools", "disallowedTools"):
        value = fm.get(field)
        for entry in value if isinstance(value, list) else [value]:
            for m in TOOL_SPECIFIER_RE.finditer(entry) if isinstance(entry, str) else ():
                tool = m.group(1)
                if tool in TOOLS_WITH_REAL_SPECIFIERS:
                    continue
                if field == "tools":
                    ctx.add(fm.line(field), "AG006",
                            f"`{m.group(0)}` in `tools` does not restrict {tool}: a permission specifier there "
                            f"grants the whole tool and pre-approves nothing. List `{tool}` and use a `PreToolUse` "
                            "hook to allow some calls and block others")
                else:
                    ctx.add(fm.line(field), "AG006",
                            f"`{m.group(0)}` in `disallowedTools` removes ALL of {tool}, not only the calls that "
                            f"match: an entry with a specifier \"{DISALLOWED_DOC_QUOTE}\" (sub-agents docs). To "
                            f"block some {tool} calls and keep the rest, leave {tool} out of `disallowedTools` and "
                            "deny those calls with a `PreToolUse` hook; to remove the tool, write "
                            f"`{tool}` alone")

    check_skill_refs(ctx)


def mask_indented_code(text):
    """Blank out indented code blocks: lines indented four spaces or a tab
    that follow a blank line (or open the text) outside a list."""
    out, in_code, in_list, prev_blank = [], False, False, True
    for line in text.split("\n"):
        if not line.strip():
            out.append(line)
            prev_blank = True
            continue
        indented = line.startswith(("    ", "\t"))
        if indented and (in_code or (prev_blank and not in_list)):
            in_code = True
            out.append("")
        else:
            in_code = False
            if LIST_ITEM_RE.match(line):
                in_list = True
            elif prev_blank and not line.startswith((" ", "\t")):
                in_list = False
            out.append(line)
        prev_blank = False
    return "\n".join(out)


def memory_imports(text):
    """(line, path) for each `@path` that Claude Code reads as an import in a
    memory or rule file, the path exactly as it takes it - see IMPORT_RE for
    what was observed. Whether the path exists is the caller's business: one
    that does not is not imported, and nothing says so."""
    prose = mask_spans(mask_indented_code(HTML_COMMENT_RE.sub(_blank, mask_fences(text))))
    out = []
    for m in IMPORT_RE.finditer(prose):
        target = m.group(1).split("#", 1)[0]
        if target:
            out.append((line_of(prose, m.start()), target))
    return out


QUOTED_IMPORT_RE = re.compile(r'"@([^"\s]+)"|(?:^|(?<=\s))@"([^"\n]+)"', re.M)


def quoted_imports(text):
    """(line, path, as written) for each at-sign path in double quotes in a
    memory file: `"@docs/a.md"` and `@"Design Docs/a.md"`. OBSERVED on 2.1.295
    (see IMPORT_RE): neither form imports anything."""
    prose = mask_spans(mask_indented_code(HTML_COMMENT_RE.sub(_blank, mask_fences(text))))
    return [(line_of(prose, m.start()), m.group(1) or m.group(2), m.group(0).strip())
            for m in QUOTED_IMPORT_RE.finditer(prose)]


def _import_looking(target):
    """Is a path that failed to resolve worth reporting? `@someone` and
    `@scope/pkg` are not import attempts; `@./x` and `@docs/a.md` are."""
    return target.startswith(("./", "../", "/", "~/")) or bool(re.search(r"\.[A-Za-z0-9]{1,5}$", target))


def lint_memory(ctx):
    total = len((ctx.text or "").rstrip("\n").split("\n"))
    if total > MEMORY_MAX_LINES:
        ctx.add(1, "CM001",
                f"{os.path.basename(ctx.abspath)} is {total} lines; the target is at most {MEMORY_MAX_LINES} - "
                f"{RULE_WHY['CM001']}. Move domain constraints to path-scoped rules and procedures to skills")

    too_deep = []

    def follow(path, text, hops, chain, report_line):
        for line, target in memory_imports(text):
            top_line = report_line or line
            if target.startswith("~/"):
                continue  # machine-specific; cannot be judged from the repo
            resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
            if not os.path.isfile(resolved):
                bare = target.rstrip(IMPORT_TRAILING)
                if not _import_looking(bare):
                    continue
                where = "" if hops == 0 else f" (imported via {display_path(path)})"
                if bare != target and os.path.isfile(os.path.normpath(os.path.join(os.path.dirname(path), bare))):
                    ctx.add(top_line, "CM002",
                            f"@{target} does not resolve{where}: the `{target[len(bare):]}` straight after the path "
                            f"is read as part of it, so nothing is imported - follow `@{bare}` with whitespace or "
                            "put it on a line of its own")
                else:
                    ctx.add(top_line, "CM002",
                            f"@{bare} does not resolve{where} - an import that does not resolve imports nothing, "
                            "and nothing says so. Fix the path (it is relative to the importing file), or put "
                            "it in a code span if it is a mention")
                continue
            if resolved in chain:
                continue
            if hops + 1 > IMPORT_MAX_HOPS:
                if not too_deep:
                    too_deep.append(1)
                    ctx.add(top_line, "CM002",
                            f"@import chain goes deeper than {IMPORT_MAX_HOPS} hops (reaching "
                            f"{display_path(resolved)}) - Claude Code follows imports only {IMPORT_MAX_HOPS} hops "
                            "deep, so that file is never read. Flatten the chain")
                continue
            try:
                follow(resolved, read_text(resolved), hops + 1, chain | {resolved}, top_line)
            except OSError:
                pass

    follow(ctx.abspath, ctx.text or "", 0, {ctx.abspath}, None)
    for line, target, form in quoted_imports(ctx.text or ""):
        if os.path.isfile(os.path.normpath(os.path.join(os.path.dirname(ctx.abspath), target))) \
                or _import_looking(target):
            ctx.add(line, "CM002",
                    f"{form} is in quotes, and a quoted path is not imported - nothing says so. Write it unquoted "
                    "to import it (a space in the path is escaped with a backslash); leave it if it is only a "
                    "mention", "info")
    # AGENTS.md is shared with other tools, whose conventions allow numbered
    # steps; CM003 is a Claude Code memory convention and stays out of it.
    if os.path.basename(ctx.abspath) != "AGENTS.md":
        _numbered_steps(ctx, "CM003", "project memory")
    else:
        check_agents_md_is_read(ctx)


def _repo_ceiling(directory):
    """The nearest directory at or above `directory` that holds a .git, else
    the filesystem root."""
    d = directory
    while True:
        up = os.path.dirname(d)
        if os.path.exists(os.path.join(d, ".git")) or up == d:
            return d
        d = up


def _reaches(source, target, hops=0, seen=None):
    """Does the memory file `source` import `target`, directly or through a
    chain of at most IMPORT_MAX_HOPS imports?"""
    seen = seen if seen is not None else set()
    if source in seen or hops >= IMPORT_MAX_HOPS:
        return False
    seen.add(source)
    try:
        text = read_text(source)
    except OSError:
        return False
    for _, ref in memory_imports(text):
        path = os.path.expanduser(ref) if ref.startswith("~/") else os.path.join(os.path.dirname(source), ref)
        path = os.path.realpath(path)
        if path == target or (os.path.isfile(path) and _reaches(path, target, hops + 1, seen)):
            return True
    return False


def check_agents_md_is_read(ctx):
    """CM004. Documented: "By default, Claude reads AGENTS.md only when you
    have no CLAUDE.md in your working directory or above it." So an AGENTS.md
    with a CLAUDE.md beside or above it is read only through an import (or
    when the CLAUDE.md is a symlink to it). The instruction-files setting can
    load both, and no file the linter sees records it - hence the caveat.

    OBSERVED on 2.1.295 (see IMPORT_RE): an import from a .claude/rules/ file
    loads it too, whatever the CLAUDE.md says; and a CLAUDE.md, CLAUDE.local.md
    or .claude/CLAUDE.md that is empty, whitespace or nothing but an HTML
    comment does not count as a CLAUDE.md at all - the AGENTS.md beside it was
    read. A non-empty CLAUDE.local.md or .claude/CLAUDE.md on its own does
    shadow it."""
    target = os.path.realpath(ctx.abspath)
    start = os.path.dirname(os.path.abspath(ctx.abspath))
    if os.path.basename(start) == ".claude":
        start = os.path.dirname(start)
    ceiling = _repo_ceiling(start)
    found, d = [], start
    while True:
        for place in CLAUDE_MD_PLACES:
            candidate = os.path.join(d, place)
            if os.path.isfile(candidate):
                if os.path.realpath(candidate) == target or _reaches(os.path.realpath(candidate), target):
                    return
                try:
                    empty = not HTML_COMMENT_RE.sub("", read_text(candidate)).strip()
                except OSError:
                    empty = True
                if not empty:
                    found.append(candidate)
        for base, dirnames, files in os.walk(os.path.join(d, ".claude", "rules")):
            dirnames.sort()
            for f in sorted(files):
                if f.endswith(".md") and _reaches(os.path.realpath(os.path.join(base, f)), target):
                    return
        up = os.path.dirname(d)
        if d == ceiling or up == d:
            break
        d = up
    if found:
        more = f" (and {len(found) - 1} more)" if len(found) > 1 else ""
        ctx.add(1, "CM004",
                f"this AGENTS.md is not read: {display_path(found[0])}{more} exists and does not import it, and by "
                "default Claude Code reads AGENTS.md only when there is no CLAUDE.md in the working directory or "
                f"above it. Add `@{os.path.relpath(ctx.abspath, os.path.dirname(found[0]))}` to that file, on a line "
                "of its own (punctuation straight after the path breaks the import) - unless "
                "the instruction-files setting is `claude-md-and-agents-md`, which loads both")


def find_hooktool():
    """hooktool.py, located relative to this script's real path. None if absent."""
    path = os.path.join(own_plugin_root(), "skills", "authoring-hooks", "scripts", "hooktool.py")
    return path if os.path.isfile(path) else None


def _run_hooktool(tool, path, plugin):
    import subprocess
    cmd = [sys.executable or "python3", tool, "validate", path, "--json"]
    if plugin:
        cmd.append("--plugin")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=HOOKTOOL_TIMEOUT_S)
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        report = None
    return proc, report if isinstance(report, dict) else None


def lint_hooks(ctx):
    base = os.path.basename(ctx.abspath)
    is_plugin_hooks = base == "hooks.json" and _is_plugin_root(os.path.dirname(os.path.dirname(ctx.abspath)))
    if base != "hooks.json":
        try:
            data = json.loads(read_text(ctx.abspath))
        except (OSError, ValueError) as ex:
            ctx.add(1, "HK001", f"invalid JSON: {ex}")
            return
        if not isinstance(data, dict) or "hooks" not in data:
            return  # a settings file with no hooks is not a hook config
    tool = find_hooktool()
    if tool is None:
        ctx.add(1, "HK001", "hooktool.py not found next to this linter; hook config was not validated", "info")
        return
    import subprocess
    try:
        proc, report = _run_hooktool(tool, ctx.abspath, is_plugin_hooks)
        if report is None and is_plugin_hooks and proc.returncode == 2:
            proc, report = _run_hooktool(tool, ctx.abspath, False)  # older hooktool without --plugin
    except (OSError, subprocess.SubprocessError) as ex:
        ctx.add(1, "HK001", f"could not run hooktool: {ex}", "info")
        return
    if report is None:
        detail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        ctx.add(1, "HK001", f"hooktool gave no report (exit {proc.returncode}): {detail[0][:120]}", "info")
        return
    for message in report.get("errors") or []:
        ctx.add(1, "HK001", str(message), "error")
    for message in report.get("warnings") or []:
        ctx.add(1, "HK001", str(message), "warn")


RESERVED_NAME_PREFIXES = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")
RESERVED_NAMES = frozenset({"claude", "anthropic", "anthropics", "claude-code", "claude-mods"})


def reserved_plugin_name(name):
    """'reserved', 'reads-as' or None - what `claude plugin validate` said
    about each of some 60 throwaway names on 2.1.295 (2026-10-09). It compares
    case-insensitively and treats `_` and `.` like `-`; "official" counts when
    it sits directly beside claude or anthropic. 'reads-as' is the validator's
    softer warning for claude, anthropic or anthropics as a whole word
    elsewhere. Re-checked the same day against the documented wording ("ignores
    case and treats any run of separators as one"): 41 more names, all agreeing
    - a reserved name exits 1, a reads-as name exits 0 with a warning."""
    norm = re.sub(r"[^a-z0-9]+", "-", name.lower())
    squashed = re.sub(r"[^a-z0-9]", "", name.lower())
    if norm.startswith(RESERVED_NAME_PREFIXES) or norm in RESERVED_NAMES \
            or re.search(r"official(?:claude|anthropic)|(?:claude|anthropic)official", squashed):
        return "reserved"
    if re.search(r"(?:^|-)(?:claude|anthropics?)(?:-|$)", norm):
        return "reads-as"
    return None


def lint_plugin_manifest(ctx, data):
    """PL004-PL006: the parts of `claude plugin validate` that are cheap to
    assert offline. Only what the validator was observed to enforce; it stays
    the authority (unknown fields, component paths and more are its job)."""
    name = data["name"]
    line = next((n for n, ln in enumerate(read_text(ctx.abspath).split("\n"), 1) if '"name"' in ln), 1)
    verdict = reserved_plugin_name(name)
    if verdict == "reserved":
        ctx.add(line, "PL004", f"plugin name {name!r} is reserved and `claude plugin validate` fails on it: a name "
                               "cannot start with claude-, anthropic-, anthropics- or cc-plugin-, be claude, "
                               "anthropic, anthropics, claude-code or claude-mods, or put \"official\" beside "
                               "claude or anthropic - name it for what it does")
    elif verdict == "reads-as":
        ctx.add(line, "PL004", f"plugin name {name!r} reads as one of Anthropic's own: claude, anthropic or "
                               "anthropics is a whole word in it (`claude plugin validate` warns); name it for "
                               "what it does", "warn")
    if re.search(r"\s", name):
        ctx.add(line, "PL005", f"plugin name {name!r} contains whitespace, which `claude plugin validate` "
                               "rejects; use kebab-case", "error")
    elif not KEBAB_RE.match(name):
        ctx.add(line, "PL005", f"plugin name {name!r} is not kebab-case (lowercase letters, digits and single "
                               "hyphens); Claude Code loads it but marketplace sync requires kebab-case")
    for key, kind, what in (("version", str, "a string"), ("author", dict, "an object"),
                            ("keywords", list, "an array")):
        if key in data and not isinstance(data[key], kind):
            ctx.add(1, "PL006", f"`{key}` must be {what}; `claude plugin validate` rejects "
                                f"{type(data[key]).__name__}")


def lint_plugin(ctx):
    root = os.path.dirname(os.path.dirname(ctx.abspath))
    try:
        data = json.loads(read_text(ctx.abspath))
    except (OSError, ValueError) as ex:
        ctx.add(getattr(ex, "lineno", 1), "PL001", f"plugin.json is not valid JSON: {ex}")
        data = None
    if data is not None and (not isinstance(data, dict) or not isinstance(data.get("name"), str)
                             or not data["name"].strip()):
        ctx.add(1, "PL001", "plugin.json needs a non-empty string `name`")
    elif data is not None:
        lint_plugin_manifest(ctx, data)

    if os.path.isdir(os.path.join(root, "bin")):
        ctx.add(1, "PL007",
                f"the plugin has a top-level `bin/` directory, and \"{BIN_DOC_QUOTE}\" (plugin docs, on `bin/`). "
                "Move the executables to `scripts/` and call each by an explicit path such as "
                "`python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/<tool>\"` - nothing is put on PATH from there")

    skills_dir = os.path.join(root, "skills")
    if os.path.isdir(skills_dir):
        for entry in sorted(os.listdir(skills_dir)):
            sub = os.path.join(skills_dir, entry)
            if os.path.isdir(sub) and not entry.startswith(".") \
                    and not os.path.isfile(os.path.join(sub, "SKILL.md")):
                ctx.add(1, "PL002", f"skills/{entry}/ has no SKILL.md")

    for base, dirnames, files in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in sorted(files):
            path = os.path.join(base, f)
            if not f.endswith(".md") or classify(path) == "skill":
                continue
            try:
                text = read_text(path)
            except OSError:
                continue
            if "PL003" in disabled_ids(text):
                continue
            for line, target in dead_links(text, base):
                ctx.add(line, "PL003", f"link target '{target}' does not exist", path=display_path(path))


LINTERS = {"skill": lint_skill, "rule": lint_rule, "agent": lint_agent,
           "memory": lint_memory, "hooks": lint_hooks, "plugin": lint_plugin}


def lint_file(path, shown=None):
    """Lint one file. Returns a list of Finding; empty if it is not an artifact."""
    abspath = os.path.abspath(path)
    kind = classify(abspath)
    if kind is None or not os.path.isfile(abspath):
        return []
    text = None
    if abspath.endswith(".md"):
        try:
            text = read_text(abspath)
        except OSError as ex:
            eprint(f"claude-lint: cannot read {path}: {ex}")
            return []
    ctx = Ctx(abspath, shown or display_path(abspath), text)
    try:
        LINTERS[kind](ctx)
    except RecursionError:
        eprint(f"claude-lint: gave up on {path}: nesting too deep")
    except Exception as ex:  # noqa: BLE001 - one hostile file must not end a whole run
        eprint(f"claude-lint: internal error linting {path}: {type(ex).__name__}: {ex}")
    off = disabled_ids(text) if text else set()
    return [f for f in ctx.findings if f.id not in off]


def collect(paths):
    """Expand files and directories into the artifact files to lint."""
    out, seen = [], set()

    def take(p):
        a = os.path.abspath(p)
        if a not in seen and classify(a):
            seen.add(a)
            out.append(a)

    for p in paths:
        if os.path.isdir(p):
            for base, dirnames, files in os.walk(p):
                dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
                for f in sorted(files):
                    take(os.path.join(base, f))
        else:
            take(p)
    return out


def lint_paths(paths):
    findings, seen = [], set()
    for a in collect(paths):
        for f in lint_file(a):
            if f.key() not in seen:
                seen.add(f.key())
                findings.append(f)
    findings.sort(key=lambda f: (f.path, f.line, f.id, f.message))
    return findings


def summarise(findings):
    summary = {s: 0 for s in SEVERITIES}
    for f in findings:
        summary[f.severity] += 1
    return summary


# ---- install-rules ----------------------------------------------------------

MANIFEST_SUFFIX = "-rules.json"


def _sha(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load_manifest(path):
    """{installed file name: sha256 of the content claude-lint wrote}, or {}."""
    try:
        data = json.loads(read_text(path))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def _write_manifest(path, manifest):
    if manifest:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
            f.write("\n")
    elif os.path.exists(path):
        os.remove(path)


def _earlier_installs(dest_dir, rules, prefix, manifest_name):
    """Files an earlier install-rules run left under a different prefix - the
    plugin was renamed since, or the files predate the manifest. Recognised
    without knowing any earlier name: either another `.<name>-rules.json`
    manifest in the directory vouches for a copy, or the entry is a symlink
    to a `rules/<rule>.md`, which is what the old default created.

    Returns [(path, state, manifest_path, key)] with state 'copy' (unedited
    since it was installed), 'edited' or 'link'."""
    found = []
    try:
        entries = sorted(os.listdir(dest_dir))
    except OSError:
        return found
    for entry in entries:
        path = os.path.join(dest_dir, entry)
        if entry.startswith(".") and entry.endswith(MANIFEST_SUFFIX) and entry != manifest_name:
            old_prefix = entry[1:-len(MANIFEST_SUFFIX)] + "-"
            for key, sha in sorted(_load_manifest(path).items()):
                old = os.path.join(dest_dir, key)
                if key.startswith(old_prefix) and key[len(old_prefix):] in rules \
                        and os.path.isfile(old) and not os.path.islink(old):
                    found.append((old, "copy" if _sha(old) == sha else "edited", path, key))
        elif os.path.islink(path):
            target = os.readlink(path)
            rule = os.path.basename(target)
            if rule in rules and entry.endswith("-" + rule) and entry != prefix + rule \
                    and os.path.basename(os.path.dirname(target)) == "rules":
                found.append((path, "link", None, entry))
    return found


def install_rules(target, dry_run=False, check=False, plugin_root=None, out=print):
    """Install the plugin's rules/*.md into target/.claude/rules/ as
    <plugin-name>-<rule>.md.

    Always a copy. There used to be a link mode, and it installed rules that
    never loaded: Claude Code treats a rule file that is a symlink to a target
    outside the project as external, and a path-scoped one stays unloaded
    (reported against 2.1.295: after linking, reading a matching file surfaced
    no rule text, where copies did). The plugin is always outside the project.
    Links an earlier version created are still recognised, and replaced by
    copies. A manifest of content hashes beside the copies lets a later run
    refresh the ones nobody edited and leave edited or foreign files alone.

    check=True changes nothing and reports each rule whose installed copy is
    missing, out of date, modified or still a link. Returns the number of
    files skipped, or in check mode the number of problems."""
    plugin_root = plugin_root or own_plugin_root()
    plugin = own_plugin_name(plugin_root)
    prefix, manifest_name = plugin + "-", "." + plugin + MANIFEST_SUFFIX
    src_dir = os.path.join(plugin_root, "rules")
    if not os.path.isdir(src_dir):
        eprint(f"claude-lint: no rules/ directory under {plugin_root}")
        return 1
    rules = sorted(n for n in os.listdir(src_dir) if n.endswith(".md"))
    dest_dir = os.path.join(os.path.abspath(target), ".claude", "rules")
    manifest_path = os.path.join(dest_dir, manifest_name)
    manifest = _load_manifest(manifest_path)
    tag = "would " if dry_run else ""
    problems = 0

    earlier = _earlier_installs(dest_dir, rules, prefix, manifest_name)
    if check:
        for path, _state, _, _ in earlier:
            out(f"stale    {path} (left by an install under an earlier plugin name; run "
                f"`{self_command('install-rules')}`)")
            problems += 1
    else:
        touched = {}
        for path, state, old_manifest, key in earlier:
            if state == "edited":
                eprint(f"skip     {path} (installed under an earlier plugin name and edited since; left alone)")
                problems += 1
                continue
            out(f"{tag}remove   {path} (installed under an earlier plugin name)")
            if not dry_run:
                os.remove(path)
                if old_manifest:
                    touched.setdefault(old_manifest, _load_manifest(old_manifest)).pop(key, None)
        for old_manifest, remaining in touched.items():
            _write_manifest(old_manifest, remaining)
        if not dry_run:
            os.makedirs(dest_dir, exist_ok=True)

    for rule in rules:
        src = os.path.join(src_dir, rule)
        name = prefix + rule
        dest = os.path.join(dest_dir, name)
        is_link = os.path.islink(dest)
        is_file = not is_link and os.path.isfile(dest)
        same = is_file and _sha(dest) == _sha(src)
        if check:
            if is_link:
                if not os.path.exists(dest):
                    out(f"dangling {dest} (a link that no longer reaches {src})")
                elif os.path.samefile(dest, src):
                    out(f"linked   {dest} (a symlink from an earlier version; a symlinked rule is not loaded - "
                        f"run `{self_command('install-rules')}` to replace it with a copy)")
                else:
                    out(f"foreign  {dest} (a link to something other than {src})")
                problems += 1
            elif not os.path.lexists(dest):
                out(f"missing  {dest}")
                problems += 1
            elif not same:
                if is_file and manifest.get(name) == _sha(dest):
                    out(f"outdated {dest} (the plugin's {rule} has changed)")
                else:
                    out(f"modified {dest} (differs from the plugin's {rule} and was edited, or not installed "
                        "by claude-lint)")
                problems += 1
            continue
        if same:
            out(f"ok       {dest} (already up to date)")
            if not dry_run:
                manifest[name] = _sha(dest)
            continue
        # replace only what an earlier run created: one of our links, or a copy
        # whose content is still what we wrote (or is identical to the source)
        ours = (not os.path.lexists(dest) or is_link
                or (is_file and (same or manifest.get(name) == _sha(dest))))
        if not ours:
            eprint(f"skip     {dest} (exists and was not created by claude-lint, or was edited since; left alone)")
            problems += 1
            continue
        if not dry_run:
            if os.path.lexists(dest):
                os.remove(dest)
            import shutil
            shutil.copyfile(src, dest)
            manifest[name] = _sha(dest)
        out(f"{tag}copy     {dest} <- {src}" + (" (replacing a symlink, which is not loaded)" if is_link else ""))
    if not dry_run and not check:
        _write_manifest(manifest_path, manifest)
    return problems


# ---- rule delivery on first touch (hook mode) ---------------------------------
#
# Claude Code does not load a plugin's rules/, so hook mode does: the first
# time a session - or a subagent in it - touches an artifact of a kind, the
# kind's rule file is handed over as additionalContext. Once per kind, tracked
# by marker files under the temp directory. A SessionStart removes them when
# the context no longer holds what was delivered: `clear` and `compact`, and
# `startup`, because a new session can arrive with an id that already has
# markers (a child `claude -p` run inherits its parent's id in some
# environments). Not `resume`: a resumed session still has the text.

KIND_GUIDES = {
    # kind: (the rule file under rules/, the skill that holds the judgement)
    "skill": ("skill-invariants.md", "authoring-skills"),
    "rule": ("rule-invariants.md", "authoring-rules"),
    "agent": ("subagent-invariants.md", "authoring-agents"),
    "memory": ("claude-md-invariants.md", "authoring-memory"),
    "hooks": ("hook-invariants.md", "authoring-hooks"),
    "plugin": (None, None),
}
RESET_SOURCES = ("startup", "clear", "compact")
MARKER_MAX_AGE_S = 7 * 24 * 3600   # a session directory untouched for this long is pruned at the next reset
LITMUS = ("Litmus for any model-facing prose you write or edit: if you could write an assertion for it, "
          "write code; if you would need a rubric, write prose.")
_UNSAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def kinds_json():
    """KIND_GUIDES as `rules --json` prints it: rule paths relative to the plugin root."""
    return {kind: {"rule": f"rules/{rule}" if rule else None, "skill": skill}
            for kind, (rule, skill) in KIND_GUIDES.items()}


def glob_regex(glob):
    """A regex for one rule glob, matched against a whole POSIX path: `**/` is
    any number of directories (none included), `**` anything, `*` and `?` stay
    inside one segment, `{a,b}` is an alternation and `[...]` a class."""
    out, i, depth = [], 0, 0
    while i < len(glob):
        c = glob[i]
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if glob.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "{":
            depth += 1
            out.append("(?:")
        elif c == "}" and depth:
            depth -= 1
            out.append(")")
        elif c == "," and depth:
            out.append("|")
        elif c == "[" and "]" in glob[i + 2:]:
            end = glob.index("]", i + 2)
            out.append("[" + glob[i + 1:end].replace("\\", "\\\\") + "]")
            i = end
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out) + ")" * depth


def glob_matches(path, globs):
    """Does the path match any of the globs? A glob may match at any depth."""
    posix = path.replace(os.sep, "/")
    for glob in globs:
        try:
            if re.fullmatch("(?:.*/)?" + glob_regex(glob), posix):
                return True
        except re.error:
            continue
    return False


def rule_paths(text):
    """The `paths` globs of a rule file's text, as a tuple (empty when unscoped)."""
    value = parse_frontmatter(text).get("paths")
    if isinstance(value, str):
        value = [g.strip() for g in value.split(",")]
    return tuple(g for g in value if isinstance(g, str) and g) if isinstance(value, list) else ()


def loads_natively(installed_text, path):
    """Will Claude Code itself load this installed rule copy for `path`? Yes
    when the copy is unscoped (it loads in every session) or one of its
    `paths` matches. A plugin's own agents/ or commands/ file is an artifact
    the installed rule's globs do not reach, so delivery still covers it."""
    globs = rule_paths(installed_text)
    return not globs or glob_matches(path, globs)


def tool_command(kind, plugin_root):
    """The runnable command that prints the mechanical side of a kind: the
    tool's real path, quoted, because nothing of this plugin is on PATH and a
    rule file cannot know where the plugin is installed. Always one simple
    command: it runs as written when pasted into a shell."""
    if kind == "hooks":
        script = os.path.join(plugin_root, "skills", "authoring-hooks", "scripts", "hooktool.py")
        return f'python3 "{script}" events'
    return f'python3 "{os.path.join(plugin_root, "scripts", "claude-lint")}" rules'


def command_line(kind, plugin_root):
    """The one line that follows a kind's delivery: what the command prints,
    a colon, and the command."""
    label = "Hook events and handler fields" if kind == "hooks" else "Mechanical invariants and their reasons"
    return f"{label}: {tool_command(kind, plugin_root)}"


def delivery_text(plugin, rule_file, text, line=None):
    """The block that hands one rule to the model: a header naming the plugin
    and the rule, the rule's body with its frontmatter removed, and - when a
    line is given - that closing line (see command_line)."""
    name = rule_file[:-3] if rule_file.endswith(".md") else rule_file
    block = f"[{plugin}] rule {name}\n\n{parse_frontmatter(text).body.strip()}"
    return f"{block}\n\n{line}" if line else block


def litmus_text(plugin):
    """The prefer-code litmus, as it leads a session's first rule delivery."""
    return f"[{plugin}] {LITMUS}"


def safe_id(value):
    """A session or agent id as one directory name, or None when it cannot be
    one: not a string, empty, or nothing but dots (`.` and `..` are the
    directory itself and its parent). Every character outside
    [A-Za-z0-9_.-] becomes `_`, so no separator survives."""
    if not isinstance(value, str):
        return None
    name = _UNSAFE_ID_CHARS.sub("_", value)[:120]
    return name if name.strip(".") else None


def marker_root(tmp, plugin):
    """The one directory this plugin keeps delivery markers under."""
    return os.path.join(tmp, f"claude-{safe_id(plugin) or FALLBACK_PLUGIN_NAME}-plugin")


def session_marker_dir(tmp, plugin, session_id):
    """The directory holding one session's markers - always a direct child of
    the marker root - or None when the session id cannot name one."""
    name = safe_id(session_id)
    if name is None:
        return None
    root = marker_root(tmp, plugin)
    path = os.path.join(root, name)
    return path if os.path.dirname(os.path.normpath(path)) == os.path.normpath(root) else None


def marker_path(tmp, plugin, session_id, agent_id, kind):
    """Where the "this is already in context" marker for one session (or one
    subagent of it) and one kind lives: <root>/<session>/<agent>/<kind>.seen.
    None when the session id cannot name a directory; an agent id that cannot
    is filed under `unknown`."""
    session_dir = session_marker_dir(tmp, plugin, session_id)
    if session_dir is None:
        return None
    agent = "main" if not agent_id else safe_id(agent_id) or "unknown"
    return os.path.join(session_dir, agent, (safe_id(kind) or "unknown") + ".seen")


def claim_delivery(marker):
    """Record that a rule is being delivered; True when this call is the one
    that should deliver it. Creating the marker is the claim, so of two hooks
    racing on the same kind exactly one wins. When the state directory cannot
    be used at all (unwritable, or a file where a directory should be) the
    answer is True: a rule repeated is better than a rule silently never
    delivered."""
    try:
        os.makedirs(os.path.dirname(marker), mode=0o700, exist_ok=True)
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        return True
    except FileExistsError:
        return False
    except OSError:
        return True


def _subdirectories(directory):
    """The real subdirectories of a directory (a symlink is not one, so
    nothing here ever leads outside it). Empty when it cannot be listed."""
    try:
        with os.scandir(directory) as entries:
            return tuple(e.path for e in entries if e.is_dir(follow_symlinks=False))
    except OSError:
        return ()


def reset_delivery(session_dir):
    """Forget what was delivered in a session, for every agent in it: the
    `.seen` files directly inside the session directory's own subdirectories,
    and nothing anywhere else. Never raises."""
    if os.path.islink(session_dir):
        return
    for agent_dir in _subdirectories(session_dir):
        try:
            with os.scandir(agent_dir) as entries:
                markers = tuple(e.path for e in entries if e.name.endswith(".seen") and not e.is_dir(follow_symlinks=False))
        except OSError:
            continue
        for marker in markers:
            try:
                os.remove(marker)
            except OSError:
                continue


def stale_sessions(last_used, now, max_age=MARKER_MAX_AGE_S):
    """The session directories to prune, from (path, when it was last
    written to) pairs: those untouched for longer than `max_age` seconds."""
    return tuple(path for path, when in last_used if now - when > max_age)


def _last_used(session_dir):
    """When a session's markers last changed: the newest modification time of
    the directory and its agent directories (creating a marker touches its
    agent directory). 0 when it cannot be read, so the caller leaves it alone."""
    try:
        return max(os.stat(path).st_mtime for path in (session_dir,) + _subdirectories(session_dir))
    except OSError:
        return 0


def prune_markers(root, now, keep=None):
    """Remove the session directories under the marker root that have not been
    used for MARKER_MAX_AGE_S - nothing else ever cleans them up. `keep` is
    the session being reset. Never raises."""
    sessions = tuple(path for path in _subdirectories(root) if path != keep)
    used = tuple((path, _last_used(path)) for path in sessions)
    for session_dir in stale_sessions(tuple(pair for pair in used if pair[1]), now):
        reset_delivery(session_dir)
        for directory in _subdirectories(session_dir) + (session_dir,):
            try:
                os.rmdir(directory)          # only when empty: a file that is not a marker keeps it
            except OSError:
                continue


def reset_session(event, tmp=None, now=None):
    """What a SessionStart event does to the markers: for a source that leaves
    the delivered text out of context, forget the session's deliveries and
    prune long-unused sessions. Never raises."""
    if event.get("source") not in RESET_SOURCES:
        return
    if tmp is None:
        import tempfile
        tmp = tempfile.gettempdir()
    plugin = own_plugin_name()
    session_dir = session_marker_dir(tmp, plugin, event.get("session_id"))
    if session_dir is None:
        return
    reset_delivery(session_dir)
    if now is None:
        import time
        now = time.time()
    prune_markers(marker_root(tmp, plugin), now, keep=session_dir)


def rule_delivery(event, path, plugin_root=None, tmp=None):
    """The blocks to deliver for a file-tool event on the artifact at `path` -
    the kind's rule, led by the litmus when this is the first delivery of any
    kind to this session or agent - or None: no rule for the kind, no usable
    session id to key on, or already delivered to this session or agent. When
    the project has this plugin's installed copy and Claude Code loads that one
    itself, the rule body is left out; the litmus (first time) and the kind's
    command line still go out."""
    kind = classify(path)
    rule_file = KIND_GUIDES.get(kind, (None, None))[0]
    if tmp is None:
        import tempfile
        tmp = tempfile.gettempdir()
    plugin_root = plugin_root or own_plugin_root()
    plugin = own_plugin_name(plugin_root)
    marker = marker_path(tmp, plugin, event.get("session_id"), event.get("agent_id"), kind) if rule_file else None
    if marker is None:
        return None
    try:
        text = read_text(os.path.join(plugin_root, "rules", rule_file))
    except OSError:
        return None
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd")
    native = False
    if isinstance(project, str) and project:
        installed = os.path.join(project, ".claude", "rules", f"{plugin}-{rule_file}")
        if os.path.isfile(installed) and not os.path.islink(installed):
            try:
                native = loads_natively(read_text(installed), path)
            except OSError:
                pass
    if not claim_delivery(marker):
        return None
    line = command_line(kind, plugin_root)
    # Claude Code loads a natively installed rule itself; the installed copy
    # cannot carry the command line, so that is all of the rule that goes out.
    parts = [line] if native else [delivery_text(plugin, rule_file, text, line)]
    if claim_delivery(os.path.join(os.path.dirname(marker), "litmus.seen")):
        parts.insert(0, litmus_text(plugin))
    return "\n\n".join(parts)


# ---- the auditor's Bash boundary (hook mode, PreToolUse) ----------------------
#
# The plugin's auditor agent is read-only and holds Bash for one purpose:
# running this linter. An agent's tool list cannot scope Bash to one command,
# and a sentence in its prompt is a request, so the boundary is held here: a
# Bash call from that agent runs only when it is exactly one invocation of this
# script. Every other session and agent never reaches this code - the shim
# hooks/auditor-bash-guard.sh lets a payload through only when it names the
# agent.

_INTERPRETER = "python3"
_WRITING_SUBCOMMAND = "install-rules"
_READ_ONLY_FLAGS = ("--check", "--dry-run")
_OPERATOR_REFUSALS = {"\n": "it is more than one command line", "(": "it opens a subshell", ")": "it opens a subshell"}


def is_own_auditor(agent_type, plugin):
    """Is this hook payload's `agent_type` this plugin's auditor: the
    plugin-scoped name a plugin agent reports, or the bare name?"""
    return agent_type in (f"{plugin}:{AUDITOR_AGENT}", AUDITOR_AGENT)


def _substitutes(raw_word):
    """Does a raw shell word run a command of its own, or quote in a way this
    scan does not follow: a backtick or `$(` outside single quotes, or the
    `$'...'` and `$"..."` forms?"""
    quote, i = None, 0
    while i < len(raw_word):
        c, pair = raw_word[i], raw_word[i:i + 2]
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "\\":
            i += 1                       # the next character is literal
        elif c == "`" or pair == "$(" or (quote is None and pair in ("$'", '$"')):
            return True
        elif c == '"':
            quote = None if quote else '"'
        elif c == "'" and quote is None:
            quote = "'"
        i += 1
    return False


def auditor_bash_refusal(command, linter):
    """Why the auditor may not run this Bash command, or None when it is
    exactly one invocation of the linter at `linter` (its real path):
    `python3 "<linter>" <args>`, no shell operators, nothing that writes."""
    tokens, hazards = lex_command(command)
    operators = [value for kind, value in tokens if kind != "word"]
    if operators:
        return _OPERATOR_REFUSALS.get(operators[0], f"it uses the shell operator `{operators[0]}`")
    if hazards:
        return f"it uses {sorted(hazards)[0]} syntax"
    raw_words = [value for _, value in tokens]
    if any(_substitutes(word) for word in raw_words):
        return "it uses command substitution or `$'...'` quoting"
    words = [_unquote(word) for word in raw_words]
    if not words:
        return "it is empty"
    if words[0] != _INTERPRETER:
        return f"it runs `{words[0][:60]}`"
    script = words[1] if len(words) > 1 else ""
    if not os.path.isabs(script) or os.path.realpath(script) != linter:
        return f"`{_INTERPRETER}` is not given this plugin's linter as its script"
    if _WRITING_SUBCOMMAND in words[2:3] and not any(flag in words[3:] for flag in _READ_ONLY_FLAGS):
        return f"`{_WRITING_SUBCOMMAND}` writes files; only its {' and '.join(_READ_ONLY_FLAGS)} forms read"
    return None


def auditor_block_message(plugin, refusal):
    """What the auditor is told when a Bash call is blocked: what was refused,
    why the boundary exists, and the command that is allowed."""
    return (f"[{plugin}] Bash call blocked for the {AUDITOR_AGENT} agent: {refusal}. The auditor is read-only "
            "and holds Bash only to run this plugin's linter, so any other command is refused here instead of "
            "being left to the prompt. Allowed: exactly one linter invocation with no shell operators "
            f"(`;`, `&&`, `||`, `|`, backticks, `$(`, redirection) - {self_command('<path>')} or "
            f"{self_command('--all', '<dir>')}. To read, list or search files use Read, Glob and Grep.")


def auditor_guard(event):
    """The block message for a PreToolUse Bash event, or None to let the call
    run: not this plugin's auditor, or no command to judge, or an allowed one."""
    plugin = own_plugin_name()
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not is_own_auditor(event.get("agent_type"), plugin) or not isinstance(command, str):
        return None
    refusal = auditor_bash_refusal(command, LAUNCHER)
    return auditor_block_message(plugin, refusal) if refusal else None


# ---- drift (the tables against the installed Claude Code) ---------------------
#
# `claude-lint drift` replaces a version stamp in every skill: instead of
# saying "this was written for 2.1.x" and leaving the reader to wonder, it
# compares what the tables claim with what the installed build contains.
# Everything here reads the build as bytes: an npm install is a JavaScript
# bundle and a native install is a binary with the same JavaScript inside.

DRIFT_OBJECT_WINDOW = 6000         # how far before a known key its object literal may start
_STRING_ARRAY_RE = re.compile(rb'\[(?:"[A-Za-z0-9_\[\]:. -]{1,40}",){1,80}"[A-Za-z0-9_\[\]:. -]{1,40}"\]')
_KEY_RE = re.compile(r'\s*(?:"([^"\\]+)"|([A-Za-z_$][\w$]*))\s*:')


def string_arrays(blob):
    """Every array literal of plain double-quoted strings in a blob of
    JavaScript, as a set of tuples (order kept inside each tuple)."""
    return {tuple(json.loads(m.group(0).decode("utf-8", "replace"))) for m in _STRING_ARRAY_RE.finditer(blob)}


def hook_events_in(arrays):
    """The hook event enum of a build: the longest string array that names
    both PreToolUse and SessionStart. Empty when there is none."""
    candidates = [a for a in arrays if "PreToolUse" in a and "SessionStart" in a]
    return max(candidates, key=len) if candidates else ()


def object_keys(source, start):
    """The top-level keys of the JavaScript object literal whose `{` is at
    source[start], in order; None when the text there is not an object
    literal with at least one `key:`. Strings, template literals, regexes in
    parentheses and nested brackets are skipped, not parsed."""
    if source[start:start + 1] != "{":
        return None
    keys, depth, i, expect_key = [], 0, start, False
    while i < len(source):
        c = source[i]
        if c in "\"'`":
            j = i + 1
            while j < len(source) and source[j] != c:
                j += 2 if source[j] == "\\" else 1
            i = j + 1
            continue
        if c in "{[(":
            depth += 1
            expect_key = depth == 1 and c == "{"
            i += 1
        elif c in "}])":
            depth -= 1
            if depth == 0:
                return keys or None
            i += 1
        elif c == "," and depth == 1:
            expect_key = True
            i += 1
        else:
            i += 1
        if expect_key and depth == 1:
            m = _KEY_RE.match(source, i)
            expect_key = False
            if m:
                keys.append(m.group(1) or m.group(2))
                i = m.end()
            elif not keys:
                return None
    return None


def schema_keys(blob, seed, required):
    """The keys of the object literal in `blob` that holds the key `seed` and
    every key in `required` - a frontmatter schema, found by what it contains
    and not by a minified name. None when no such object is there."""
    needles = (b'"' + seed.encode() + b'":', seed.encode() + b":")
    hits = []
    for needle in needles:               # plain finds: a regex over a quarter-gigabyte build takes seconds
        at = blob.find(needle)
        while at >= 0:
            hits.append(at)
            at = blob.find(needle, at + 1)
    for hit in sorted(set(hits)):
        lo = max(hit - DRIFT_OBJECT_WINDOW, 0)
        window = blob[lo:hit + 40000].decode("latin-1")
        at = hit - lo + 1
        while True:
            at = window.rfind("{", 0, at)
            if at < 0:
                break
            keys = object_keys(window, at)
            if keys and seed in keys and set(required) <= set(keys):
                return tuple(keys)
    return None


def name_drift(what, table, build, known_extra=()):
    """Compare a set of names the tables hold with the set the build holds.
    Returns the drift lines for it: names the build no longer has, and names
    the build has that the tables do not (`known_extra` are build names
    deliberately left out of the tables)."""
    table, build = set(table), set(build)
    lines = []
    gone = sorted(table - build)
    new = sorted(build - table - set(known_extra))
    if gone:
        lines.append(f"{what}: in the tables but not in this build: {', '.join(gone)}")
    if new:
        lines.append(f"{what}: in this build but not in the tables: {', '.join(new)}")
    return lines


def enum_drift(what, values, arrays, distinctive):
    """Compare one closed value set with a build's string arrays. Returns
    (state, line): ("ok", None) when an array with exactly these values
    exists; ("drift", line) when a slightly larger array holds them all (a
    value was added) or none matches and one shares all but one of them (a
    went away); ("unknown", None) when there is nothing to compare with.

    Only a set with words of its own (`xhigh`, `acceptEdits`) is `distinctive`
    enough for the larger-or-smaller comparison; for the rest (`bash`,
    `fork`) an unrelated list would raise a false alarm, so only the exact
    set is looked for."""
    wanted = set(values)
    exact = any(set(a) == wanted for a in arrays)
    if distinctive:
        larger = sorted((a for a in arrays if wanted < set(a) and len(a) <= len(wanted) + 4), key=len)
        if larger:
            return "drift", f"{what}: this build has a value set with more in it: " \
                            f"{', '.join(sorted(set(larger[0]) - wanted))}"
    if exact:
        return "ok", None
    if distinctive:
        near = [a for a in arrays if len(set(a) & wanted) >= max(len(wanted) - 1, 2) and len(a) <= len(wanted) + 4]
        if near:
            best = max(near, key=lambda a: (len(set(a) & wanted), -abs(len(a) - len(wanted))))
            extra = sorted(set(best) - wanted)
            return "drift", (f"{what}: no value set in this build holds exactly these; the nearest lacks "
                             f"{', '.join(sorted(wanted - set(best)))}"
                             + (f" and has {', '.join(extra)}" if extra else ""))
    return "unknown", None


def drift_report(blob, hook_events, running):
    """Everything `claude-lint drift` has to say about one build, as plain
    data: {"verified_against", "running", "drift": [lines], "checked":
    [what was compared], "not_checked": [what was not, and why]}.
    `hook_events` is the tool's own event list, or None when it could not be
    read."""
    drift, checked, not_checked = [], [], []
    arrays = string_arrays(blob)

    build_events = hook_events_in(arrays)
    if hook_events is None:
        not_checked.append("hook events: `hooktool events --json` gave no list")
    elif not build_events:
        not_checked.append("hook events: no event-name array found in this build")
    else:
        checked.append(f"hook event names ({len(build_events)} in this build)")
        drift += name_drift("hook events", hook_events, build_events)

    known_keys = max((a for a in arrays if "allowed-tools" in a and "when_to_use" in a), key=len, default=())
    base = schema_keys(blob, "disable-model-invocation", ("allowed-tools", "argument-hint", "user-invocable"))
    extension = schema_keys(blob, "when_to_use", ("paths", "context", "agent"))
    if base is None or extension is None:
        not_checked.append("skill fields: the skill frontmatter schema was not found in this build")
    else:
        checked.append(f"skill frontmatter fields ({len(base) + len(extension)} in this build's schema)")
        table = [f.name for f in SKILL_REFERENCE.fields]
        drift += name_drift("skill fields", table, set(base) | set(extension) | set(known_keys),
                            known_extra=set(SKILL_REFERENCE.unlisted) | set(known_keys) - set(base) - set(extension))
    agent = schema_keys(blob, "omitClaudeMd", ("name", "color", "isolation", "permissionMode"))
    if agent is None:
        not_checked.append("agent fields: the agent frontmatter schema was not found in this build")
    else:
        checked.append(f"agent frontmatter fields ({len(agent)} in this build's schema)")
        drift += name_drift("agent fields", [f.name for f in AGENT_REFERENCE.fields], agent,
                            known_extra=AGENT_REFERENCE.unlisted)
    if known_keys:
        checked.append("rule frontmatter: `paths` is still a known key")
        if "paths" not in known_keys:
            drift.append("rule fields: `paths` is not in this build's list of frontmatter keys")
    else:
        not_checked.append("rule fields: the list of known frontmatter keys was not found in this build")

    enums = (
        ("effort levels", EFFORT_LEVELS, True),
        ("permission modes", PERMISSION_MODES, True),
        ("model aliases", MODEL_ALIASES + UNLISTED_VALUES["model"], True),
        ("skill `context` values", field_named(SKILL_REFERENCE, "context").values, False),
        ("skill `shell` values", field_named(SKILL_REFERENCE, "shell").values, False),
        ("agent `isolation` values",
         field_named(AGENT_REFERENCE, "isolation").values + UNLISTED_VALUES["isolation"], False),
    )
    for what, values, distinctive in enums:
        state, line = enum_drift(what, values, arrays, distinctive)
        if state == "ok":
            checked.append(what if distinctive else f"{what} (only that this exact set is still in the build; "
                                                     "an added value would not show)")
        elif state == "drift":
            drift.append(line)
        else:
            not_checked.append(f"{what}: no array with these values found in this build")
    not_checked += [
        "agent `color` and `memory` values: not stored in a form that can be told apart from other lists",
        "types, defaults, effects and every note: prose from the docs, with nothing in the build to compare to",
        "the numeric limits (`rules --json`): constants with no name to find them by",
        "the injection permission model behind SK005/SK013 and `check-injection`: observed behaviour (583 probes "
        "on 2.1.295), re-run the probes to re-verify",
    ]
    return {"verified_against": TABLES_VERIFIED_AGAINST, "running": running, "drift": drift,
            "checked": checked, "not_checked": not_checked}


def running_version():
    import subprocess
    try:
        proc = subprocess.run(["claude", "--version"], capture_output=True, text=True,
                              timeout=VERSION_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    m = VERSION_RE.search(proc.stdout or "")
    return m.group(0) if m else None


def installed_build():
    """The path of the file that holds the installed Claude Code's JavaScript
    - `claude` on PATH with its symlinks resolved - or None."""
    import shutil
    found = shutil.which("claude")
    return os.path.realpath(found) if found else None


def tool_hook_events():
    """The event names `hooktool events --json` lists, or None."""
    tool = find_hooktool()
    if tool is None:
        return None
    import subprocess
    try:
        proc = subprocess.run([sys.executable or "python3", tool, "events", "--json"], capture_output=True,
                              text=True, timeout=HOOKTOOL_TIMEOUT_S)
        rows = json.loads(proc.stdout)
        return [row["event"] for row in rows]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None


# ---- commands ---------------------------------------------------------------

def cmd_lint(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="claude-lint", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paths", nargs="*", metavar="path", help="files or directories to lint")
    p.add_argument("--all", nargs="?", const=".", metavar="ROOT", dest="all_root",
                   help="lint every artifact under ROOT (default: current directory)")
    p.add_argument("--json", action="store_true", help="emit findings and a summary as one JSON object")
    args = p.parse_args(argv)
    paths = list(args.paths) + ([args.all_root] if args.all_root else [])
    if not paths:
        p.print_usage(sys.stderr)
        eprint("claude-lint: error: give at least one path, --all, or a subcommand (see --help)")
        return 2
    missing = [x for x in paths if not os.path.exists(x)]
    if missing:
        eprint(f"claude-lint: error: no such file or directory: {', '.join(missing)}")
        return 2
    artifacts = list(collect(paths))
    if not artifacts:
        # A clean run and a run that matched nothing must not look the same.
        eprint(f"claude-lint: error: no Claude Code artifacts under {', '.join(paths)} - nothing was checked. "
               "Check the path; `claude-lint classify <file>` says what counts as an artifact")
        return 2
    findings = lint_paths(artifacts)
    summary = summarise(findings)
    if args.json:
        print(json.dumps({"findings": [f.as_dict() for f in findings],
                          "summary": {**summary, "artifacts": len(artifacts)}}, indent=2))
    else:
        for f in findings:
            print(f.as_line())
        eprint(f"claude-lint: {len(artifacts)} artifact{'s' * (len(artifacts) != 1)} checked: "
               f"{summary['error']} error, {summary['warn']} warn, {summary['info']} info")
    return 1 if summary["error"] else 0


def cmd_rules(argv):
    import argparse
    p = argparse.ArgumentParser(prog="claude-lint rules",
                                description="List every rule: id, severity, artifact kind, check and the reason "
                                            "it exists; then the numeric limits and, per artifact kind, the "
                                            "rule file hook mode delivers and the skill that holds the judgement.")
    p.add_argument("--json", action="store_true",
                   help="emit {\"rules\": [...], \"limits\": {...}, \"kinds\": {...}}")
    args = p.parse_args(argv)
    if args.json:
        print(json.dumps({
            "rules": [{"id": i, "severity": s, "kind": k, "check": c, "why": w} for i, s, k, c, w in RULES],
            "limits": dict(LIMITS),
            "kinds": kinds_json(),
        }, indent=2))
        return 0
    for rule_id, sev, kind, check, why in RULES:
        print(f"{rule_id}  {sev:<5}  {kind:<18}  {check}")
        print(f"       why: {why}")
    print()
    print("limits: " + ", ".join(f"{k}={v}" for k, v in LIMITS.items()))
    print("kinds:  " + "; ".join(f"{kind} -> rules/{rule}, skill {skill}" if rule else f"{kind} -> (none)"
                                 for kind, (rule, skill) in KIND_GUIDES.items()))
    return 0


def cmd_fields(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="claude-lint fields",
        description="Print the frontmatter reference for one kind of artifact: every field with its type (or "
                    "allowed values), default and effect, one line each with a long effect cut short, then the "
                    "kind-level notes. Name a FIELD to print that one field in full, an attribute per line.")
    p.add_argument("kind", choices=sorted(REFERENCES), help="which table")
    p.add_argument("field", nargs="?", metavar="FIELD", help="print only this field, in full")
    p.add_argument("--full", action="store_true", help="print every effect in full instead of cutting it short")
    p.add_argument("--json", action="store_true",
                   help="emit {\"kind\", \"source\", \"verified_against\", \"fields\": [...], \"notes\": [...], "
                        "\"unlisted\": [...]}; with FIELD, that field's object alone")
    args = p.parse_args(argv)
    reference = REFERENCES[args.kind]
    if args.field is None:
        print(json.dumps(fields_json(reference), indent=2) if args.json else fields_text(reference, full=args.full))
        return 0
    field = field_named(reference, args.field)
    if field is None:
        eprint(f"claude-lint fields: error: no {args.kind} frontmatter field is named `{args.field}`; the fields are: "
               + ", ".join(f.name for f in reference.fields))
        return 2
    if args.json:
        print(json.dumps(next(row for row in fields_json(reference)["fields"] if row["field"] == field.name), indent=2))
    else:
        print(field_text(reference, field))
    return 0


def injection_verdict(command, allowed_tools=None, skill_dir_outside=False):
    """What `check-injection` reports for one command, as plain data:
    {"verdict": "loads" | "aborts", "problems": [{"kind", "part", "why",
    "entry"}], "add": [entries], "fallback": bool}. `fallback` is separate
    from the verdict: a command with none still loads - until it fails."""
    problems = injection_problems(command, allowed_tools, skill_dir_outside)
    return {
        "verdict": "aborts" if problems else "loads",
        "problems": [{"kind": p.kind, "part": p.text, "why": p.message(), "entry": p.entry or None}
                     for p in problems],
        "add": list(dict.fromkeys(p.entry for p in problems if p.entry)),
        "fallback": has_failure_fallback(command),
    }


def cmd_check_injection(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="claude-lint check-injection",
        description="Would this skill injection command pass the permission check Claude Code runs before a "
                    "skill loads? Prints `loads` or `aborts`, each part that fails with the reason, and the "
                    "`Bash(...)` entry to add to allowed-tools. The same model as lint rules SK013 and SK005 "
                    "(observed behaviour, 583 probes). Exit 0 loads, 1 aborts.")
    p.add_argument("command", help="the command as written inside the directive, in single quotes")
    p.add_argument("--allowed-tools", default=None, metavar="VALUE",
                   help="the skill's allowed-tools value, as written in its frontmatter")
    p.add_argument("--plugin-skill", action="store_true",
                   help="the skill ships in a plugin or under ~/.claude: its own directory is then outside "
                        "the session's working directories")
    p.add_argument("--json", action="store_true",
                   help="emit {\"verdict\", \"problems\": [...], \"add\": [...], \"fallback\": bool}")
    args = p.parse_args(argv)
    result = injection_verdict(args.command, args.allowed_tools, args.plugin_skill)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["verdict"])
        for problem in result["problems"]:
            print(f"- {problem['why']}")
        if result["add"]:
            print("add to allowed-tools: " + ", ".join(result["add"]))
        if not result["fallback"]:
            print("note: no fallback - if the command exits non-zero the load aborts all the same; end it with "
                  "`|| echo \"<what is missing>\"`")
    return 1 if result["problems"] else 0


def drift_text(report):
    """A drift report as the lines `claude-lint drift` prints."""
    lines = [f"tables verified against {report['verified_against']}; running {report['running'] or 'unknown'}"]
    if report.get("build"):
        lines.append(f"build: {report['build']}")
    if report["drift"]:
        lines += [f"drift: {line}" for line in report["drift"]]
        lines.append("re-verify those against the docs, update the tables, then set TABLES_VERIFIED_AGAINST")
    elif report["checked"]:
        lines.append("no drift found")
    else:
        lines.append("not checkable: none of the comparisons could be made against this build")
    if report["checked"]:
        lines.append("checked:")
        lines += [f"  - {item}" for item in report["checked"]]
    lines.append("NOT checked:")
    lines += [f"  - {item}" for item in report["not_checked"]]
    return "\n".join(lines)


def cmd_drift(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="claude-lint drift",
        description="Compare the tables this linter owns - frontmatter fields, their value sets, and hooktool's "
                    "hook events - with the installed Claude Code, read straight out of its build. Says what "
                    "was compared and what was not. Exit 0 when nothing drifted or nothing could be compared "
                    "(no `claude` on PATH), 1 on drift. For the maintainer and CI; nothing is cached.")
    p.add_argument("--json", action="store_true",
                   help="emit {\"verified_against\", \"running\", \"build\", \"drift\": [...], \"checked\": "
                        "[...], \"not_checked\": [...]}")
    args = p.parse_args(argv)
    build = installed_build()
    if build is None:
        report = {"verified_against": TABLES_VERIFIED_AGAINST, "running": None, "build": None, "drift": [],
                  "checked": [], "not_checked": ["everything: `claude` is not on PATH, so there is no build to "
                                                 "compare the tables with"]}
    else:
        try:
            with open(build, "rb") as f:
                blob = f.read()
        except OSError as ex:
            eprint(f"claude-lint drift: cannot read {build}: {ex}")
            blob = b""
        report = dict(drift_report(blob, tool_hook_events(), running_version()), build=build)
    print(json.dumps(report, indent=2) if args.json else drift_text(report))
    return 1 if report["drift"] else 0


def cmd_classify(argv):
    import argparse
    p = argparse.ArgumentParser(
        prog="claude-lint classify",
        description=f"Print the artifact kind of PATH ({', '.join(KINDS)}); exit 1 with no output if it is not one.")
    p.add_argument("path", nargs="?")
    p.add_argument("--extensions", action="store_true",
                   help="print each file-name suffix an artifact can have, one per line, and exit; "
                        "hooks/lint-on-write.sh gates on exactly this set")
    args = p.parse_args(argv)
    if args.extensions:
        print("\n".join(ARTIFACT_SUFFIXES))
        return 0
    if args.path is None:
        p.print_usage(sys.stderr)
        eprint("claude-lint classify: error: give a path or --extensions")
        return 2
    kind = classify(args.path)
    if kind is None:
        return 1
    print(kind)
    return 0


def findings_block(file_path, findings):
    """The lint half of a hook message: the path once, in the header; then
    `line: sev ID message` per finding. A finding about some other file
    (PL003 reports the .md it found a dead link in) keeps its own path."""
    lines = [f"{f.line}: {f.severity} {f.id} {f.message}" if f.path == file_path else f.as_line()
             for f in findings[:HOOK_MAX_FINDINGS]]
    if len(findings) > HOOK_MAX_FINDINGS:
        lines.append(f"(+{len(findings) - HOOK_MAX_FINDINGS} more)")
    return f"[claude-lint] {file_path}\n" + "\n".join(lines)


def hook_json(blocks):
    """The one object hook mode prints: every block, rule first, in a single
    additionalContext - the only channel from PostToolUse to the model."""
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n\n".join(blocks)}}


def hook_too_large(file_path, path):
    """The one info line hook mode prints instead of linting a file larger
    than HOOK_MAX_BYTES, or None. The write-time hook has a 30 second timeout
    and runs after every Write and Edit; a file this size is linted on demand."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size <= HOOK_MAX_BYTES:
        return None
    quoted = "'" + path.replace("'", "'\\''") + "'"
    return (f"info: file too large to lint at write time ({size} bytes; the limit is {HOOK_MAX_BYTES}); "
            f"run claude-lint on it directly: {self_command(quoted)}")


def lint_block(file_path, path):
    """What the write-time lint has to say about a file, as one block, or None."""
    note = hook_too_large(file_path, path)
    if note:
        return f"[claude-lint] {file_path}\n{note}"
    findings = lint_file(path, shown=file_path)
    findings.sort(key=lambda f: (SEVERITIES.index(f.severity), f.path, f.line, f.id))
    return findings_block(file_path, findings) if findings else None


def cmd_hook(argv):
    """Hook mode. Reads one hook event from stdin and always exits 0.

    PostToolUse on Read, Write or Edit of an authoring artifact: the first
    touch of each kind in a session (or in a subagent) delivers that kind's
    rule file, and a Write or Edit is linted. Both go out in one JSON object,
    as hookSpecificOutput.additionalContext - PostToolUse cannot block and its
    plain stdout never reaches the model. A file larger than 1 MiB is not
    linted here; one info line says so.

    SessionStart (source startup, clear or compact): forgets which rules were
    delivered, so they are delivered again, and prunes the markers of sessions
    unused for a week. Prints nothing.

    PreToolUse on Bash, from this plugin's auditor agent only: a command that
    is not exactly one invocation of this linter is blocked - the one case
    that exits 2, with the reason and the allowed form on stderr."""
    if any(a in ("-h", "--help") for a in argv):
        print("usage: claude-lint hook < event.json\n\n" + (cmd_hook.__doc__ or ""))
        return 0
    try:
        step = _HOOK_STEP              # set by the launcher when it read the payload
        if step is _NOT_READ:
            stdin = getattr(sys.stdin, "buffer", sys.stdin)
            step = read_hook_payload(stdin.read())
        if step is None:
            return 0
        if step[0] == "reset":
            reset_session(step[1])
            return 0
        if step[0] == "guard":
            blocked = auditor_guard(step[1])
            if blocked:
                eprint(blocked)
                return 2
            return 0
        _, event, file_path, path = step
        blocks = []
        try:
            rule = rule_delivery(event, path)
        except Exception:  # noqa: BLE001 - delivery must not cost the findings
            rule = None
        if rule:
            blocks.append(rule)
        if event.get("tool_name") != "Read":
            findings = lint_block(file_path, path)
            if findings:
                blocks.append(findings)
        if blocks:
            print(json.dumps(hook_json(blocks)))
    except Exception:  # noqa: BLE001 - a hook must never fail the tool call
        pass
    return 0


def cmd_install_rules(argv):
    import argparse
    prefix = own_plugin_name() + "-"
    if any(a == "--link" or a.startswith("--link=") for a in argv):
        eprint("claude-lint install-rules: error: --link has been removed. A rule file that is a symlink to a "
               "target outside the project is treated as external by Claude Code and a path-scoped one is never "
               "loaded, so linked rules silently did nothing. Copying is the only mode: run the command without "
               "--link (symlinks an earlier version created are replaced by copies).")
        return 2
    p = argparse.ArgumentParser(
        prog="claude-lint install-rules", formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Copy each of the plugin's rules/*.md into DIR/.claude/rules/, named\n"
                    f"{prefix}<rule>.md. Idempotent: an unedited copy is refreshed when the plugin's\n"
                    "rule changes; a file that was edited, or that claude-lint did not create, is\n"
                    "skipped and reported, and the command exits 1.\n\n"
                    "Copying is the only mode. A symlinked rule is not loaded by Claude Code when its\n"
                    "target is outside the project, so the old link option is gone; symlinks an\n"
                    "earlier version created are replaced by copies.")
    p.add_argument("--target", default=".", metavar="DIR", help="project directory (default: cwd)")
    p.add_argument("--copy", action="store_true", help="copy - the only mode; accepted for compatibility")
    p.add_argument("--dry-run", action="store_true", help="print what would happen and change nothing")
    p.add_argument("--check", action="store_true",
                   help="change nothing; print each rule whose installed copy is missing, out of date or "
                        "modified and exit 1 if there is one (for CI)")
    args = p.parse_args(argv)
    if not os.path.isdir(args.target):
        eprint(f"claude-lint: error: target is not a directory: {args.target}")
        return 2
    problems = install_rules(args.target, dry_run=args.dry_run, check=args.check)
    return 1 if problems else 0


COMMANDS = {"rules": cmd_rules, "fields": cmd_fields, "check-injection": cmd_check_injection,
            "drift": cmd_drift, "classify": cmd_classify, "hook": cmd_hook,
            "install-rules": cmd_install_rules}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in COMMANDS:
        return COMMANDS[argv[0]](argv[1:])
    return cmd_lint(argv)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
