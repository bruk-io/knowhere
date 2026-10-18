"""Tests for hooks/context.py.

The first half tests the logic with plain values. The second half runs the hook as a
subprocess, the way Claude Code does, against throwaway git repositories and a
throwaway temp directory. Set HOOK_PYTHON to run the hook under another interpreter.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import context  # noqa: E402
from context import Mode, Rule  # noqa: E402

HOOK_PYTHON = os.environ.get("HOOK_PYTHON", sys.executable)
OWNERS = ("github.com/bruk-io/", "github.com/brukhabtu/")


# --- logic ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "globs", "expected"),
    [
        ("/repo/src/app/core.py", ("**/*.py",), True),
        ("core.py", ("**/*.py",), True),
        ("/repo/src/app/core.pyc", ("**/*.py",), False),
        ("/repo/pyproject.toml", ("**/pyproject.toml",), True),
        ("/repo/tests/unit/test_core.py", ("**/tests/**/*.py",), True),
        ("/repo/tests/test_core.py", ("**/tests/**/*.py",), True),
        ("/repo/src/test_core.py", ("**/test_*.py",), True),
        ("/repo/src/contest.py", ("**/test_*.py", "**/conftest.py"), False),
        ("/repo/.claude/rules/py/style.md", ("**/.claude/rules/**",), True),
        ("/repo/.claude/worktrees/a/README.md", ("**/.claude/rules/**",), False),
        ("/repo/.claude/settings.local.json", ("**/.claude/settings*.json",), True),
        ("/repo/skills/x/SKILL.md", ("**/SKILL.md",), True),
        ("C:\\repo\\src\\core.py", ("**/*.py",), True),
    ],
)
def test_matches(path: str, globs: tuple[str, ...], expected: bool) -> None:
    assert context.matches(path, globs) is expected


def test_parse_rule_reads_paths_commands_and_mode() -> None:
    text = (
        '---\npaths:\n  - "**/*.py"\n  - "**/pyproject.toml"\ncommands:\n  - backlog\n'
        "mode: owner\n---\n# Python\n\nBody.\n"
    )
    rule = context.parse_rule("python", text)
    expected = Rule(
        "python", ("**/*.py", "**/pyproject.toml"), ("backlog",), True, "# Python\n\nBody."
    )
    assert rule == expected


def test_parse_rule_without_frontmatter_matches_nothing() -> None:
    rule = context.parse_rule("plain", "# Plain\n")
    assert rule.paths == () and rule.commands == () and rule.owner_only is False


@pytest.mark.parametrize("key", ["paths", "commands"])
def test_parse_rule_refuses_an_inline_list(key: str) -> None:
    with pytest.raises(context.RuleError, match="must be a list"):
        context.parse_rule("bad", "---\n%s: **/*.py, **/*.toml\n---\nBody\n" % key)


@pytest.mark.parametrize(
    ("command", "words"),
    [
        ("backlog task list", ("backlog",)),
        ("FOO=1 backlog task edit 5 -s Done", ("backlog",)),
        ("cd x && backlog board", ("cd", "backlog")),
        ('echo "backlog" | grep x', ("echo", "grep")),
        ("npm test; /usr/local/bin/backlog x", ("npm", "backlog")),
        ("cd repo\nbacklog task list", ("cd", "backlog")),
        ("sh -c 'backlog board'", ("sh", "backlog")),
        ('echo "unbalanced', ("echo",)),
    ],
)
def test_command_words(command: str, words: tuple[str, ...]) -> None:
    assert context.command_words(command) == words


@pytest.mark.parametrize(
    "remote",
    [
        "git@github.com:bruk-io/bunk.git",
        "https://github.com/bruk-io/bunk.git",
        "ssh://git@github.com/bruk-io/bunk.git",
    ],
)
def test_normalise_remote_gives_one_form(remote: str) -> None:
    assert context.normalise_remote(remote) == "github.com/bruk-io/bunk.git"


def test_parse_owners_skips_comments_and_blanks() -> None:
    assert context.parse_owners("# mine\n\ngithub.com/a/  # trailing\ngithub.com/b/\n") == (
        "github.com/a/",
        "github.com/b/",
    )


def test_repo_mode() -> None:
    assert context.repo_mode("git@github.com:bruk-io/bunk.git", OWNERS) is Mode.OWNER
    assert context.repo_mode("git@github.com:Bruk-IO/bunk.git", OWNERS) is Mode.OWNER
    assert context.repo_mode("https://github.corp.ebay.com/live/ios_core", OWNERS) is Mode.GUEST
    assert context.repo_mode(None, OWNERS) is Mode.OWNER


def test_rules_for_filters_seen_and_matches_files_or_commands() -> None:
    python = Rule("python", ("**/*.py",), (), True, "p")
    board = Rule("board", ("**/backlog/**",), ("backlog",), False, "b")
    rules = (python, board)
    file = context.Touch("/r/a.py", (), "/r")
    assert context.rules_for(rules, file, frozenset()) == (python,)
    assert context.rules_for(rules, file, frozenset({"python"})) == ()
    assert context.rules_for(
        rules, context.Touch("/r/backlog/tasks/t.md", (), "/r"), frozenset()
    ) == (board,)
    assert context.rules_for(rules, context.Touch(None, ("cd", "backlog"), "/r"), frozenset()) == (
        board,
    )
    assert context.rules_for(rules, context.Touch(None, ("git",), "/r"), frozenset()) == ()


def test_in_mode_drops_owner_rules_for_guests() -> None:
    python = Rule("python", ("**/*.py",), (), True, "p")
    board = Rule("board", ("**/backlog/**",), ("backlog",), False, "b")
    assert context.in_mode((python, board), Mode.GUEST) == (board,)
    assert context.in_mode((python, board), Mode.OWNER) == (python, board)


def test_every_shipped_rule_loads_strictly() -> None:
    names = sorted(p.stem for p in (ROOT / "rules").glob("*.md"))
    rules = tuple(context.parse_rule(n, (ROOT / "rules" / (n + ".md")).read_text()) for n in names)
    assert [r.name for r in rules] == [
        "code-design",
        "python",
        "python-tests",
        "python-tests-e2e",
        "python-tests-integration",
        "python-tests-unit",
    ]
    assert all((r.paths or r.commands) and r.body for r in rules)
    assert {r.name for r in rules if r.owner_only} == {
        "code-design",
        "python",
        "python-tests",
        "python-tests-e2e",
        "python-tests-integration",
        "python-tests-unit",
    }


# --- the hook as Claude Code runs it ---------------------------------------------------


def make_repo(path: Path, remote: str | None) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", remote], check=True)
    return path


@pytest.fixture
def owned(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "owned", "git@github.com:bruk-io/bunk.git")


@pytest.fixture
def guest(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "guest", "https://github.corp.ebay.com/live/ios_core.git")


def run_hook(
    tmp_path: Path, payload: dict | str, **env_extra: str
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, TMPDIR=str(tmp_path / "tmp"), CLAUDE_PLUGIN_ROOT=str(ROOT), **env_extra)
    (tmp_path / "tmp").mkdir(exist_ok=True)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [HOOK_PYTHON, str(ROOT / "hooks" / "context.py")],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )


def start(cwd: Path, source: str = "startup", session: str = "s1") -> dict:
    return {
        "hook_event_name": "SessionStart",
        "session_id": session,
        "cwd": str(cwd),
        "source": source,
    }


def touch(cwd: Path, file: str, session: str = "s1", **extra: str) -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "session_id": session,
        "cwd": str(cwd),
        "tool_name": "Read",
        "tool_input": {"file_path": str(cwd / file)},
        **extra,
    }


def bash(cwd: Path, command: str, session: str = "s1") -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "session_id": session,
        "cwd": str(cwd),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def injected(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return ""
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PostToolUse"
    return str(output["additionalContext"])


def test_session_start_in_owned_repo(tmp_path: Path, owned: Path) -> None:
    result = run_hook(tmp_path, start(owned))
    assert result.returncode == 0
    assert result.stdout.startswith("[philosophy] Repository mode: owner.")
    assert "# Standing constraints" in result.stdout
    assert "{plugin_root}" not in result.stdout
    assert str(ROOT / "docs" / "engineering-philosophy.md") in result.stdout
    assert (ROOT / "docs" / "engineering-philosophy.md").exists()


def test_session_start_in_guest_repo(tmp_path: Path, guest: Path) -> None:
    result = run_hook(tmp_path, start(guest))
    assert (
        "Repository mode: guest (origin: github.corp.ebay.com/live/ios_core.git)" in result.stdout
    )
    assert "# Standing constraints" in result.stdout


def test_subagent_start_gets_the_constraints(tmp_path: Path, owned: Path) -> None:
    payload = {
        "hook_event_name": "SubagentStart",
        "session_id": "s1",
        "cwd": str(owned),
        "agent_id": "worker-1",
        "agent_type": "general-purpose",
    }
    result = run_hook(tmp_path, payload)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "SubagentStart"
    assert output["additionalContext"].startswith("[philosophy] Repository mode: owner.")
    assert "# Standing constraints" in output["additionalContext"]
    assert "{plugin_root}" not in output["additionalContext"]


def test_subagent_start_in_guest_repo_says_so(tmp_path: Path, guest: Path) -> None:
    payload = {"hook_event_name": "SubagentStart", "session_id": "s1", "cwd": str(guest)}
    output = json.loads(run_hook(tmp_path, payload).stdout)["hookSpecificOutput"]
    assert "Repository mode: guest" in output["additionalContext"]


def test_session_start_outside_git_is_owner(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert "Repository mode: owner." in run_hook(tmp_path, start(plain)).stdout


def test_python_rule_arrives_once_per_session(tmp_path: Path, owned: Path) -> None:
    first = injected(run_hook(tmp_path, touch(owned, "src/core.py")))
    assert "[philosophy] rule python\n" in first and "## Floor and tools" in first
    assert "[philosophy] rule code-design\n" in first
    assert "python-tests" not in first
    assert injected(run_hook(tmp_path, touch(owned, "src/other.py"))) == ""
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "src/core.py", session="s2")))


def test_test_file_gets_both_python_rules(tmp_path: Path, owned: Path) -> None:
    text = injected(run_hook(tmp_path, touch(owned, "tests/unit/test_core.py")))
    assert "[philosophy] rule python\n" in text and "[philosophy] rule python-tests\n" in text


def test_a_test_file_gets_only_its_own_layer_rule(tmp_path: Path, owned: Path) -> None:
    unit = injected(run_hook(tmp_path, touch(owned, "tests/unit/test_core.py")))
    assert "[philosophy] rule python-tests-unit\n" in unit
    assert "python-tests-integration" not in unit and "python-tests-e2e" not in unit
    later = injected(run_hook(tmp_path, touch(owned, "tests/integration/test_flow.py")))
    assert "[philosophy] rule python-tests-integration\n" in later
    assert "python-tests-unit" not in later


def test_compact_lets_rules_load_again(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, touch(owned, "a.py")))
    assert injected(run_hook(tmp_path, touch(owned, "a.py"))) == ""
    run_hook(tmp_path, start(owned, source="compact"))
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "a.py")))


def test_startup_with_a_reused_session_id_reloads_rules(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, touch(owned, "a.py")))
    run_hook(tmp_path, start(owned, source="startup"))
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "a.py")))


def test_resume_does_not_reload_rules(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, touch(owned, "a.py")))
    run_hook(tmp_path, start(owned, source="resume"))
    assert injected(run_hook(tmp_path, touch(owned, "a.py"))) == ""


def test_subagent_gets_its_own_copy(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, touch(owned, "a.py")))
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "a.py", agent_id="worker-1")))
    assert injected(run_hook(tmp_path, touch(owned, "a.py", agent_id="worker-1"))) == ""


def test_guest_repo_gets_no_code_rules(tmp_path: Path, guest: Path) -> None:
    assert injected(run_hook(tmp_path, touch(guest, "src/core.py"))) == ""
    assert injected(run_hook(tmp_path, touch(guest, "tests/test_core.py"))) == ""
    assert injected(run_hook(tmp_path, touch(guest, "app/main.ts"))) == ""


def test_mode_follows_the_file_not_the_session(tmp_path: Path, owned: Path, guest: Path) -> None:
    from_owned = touch(owned, "x")
    from_owned["tool_input"] = {"file_path": str(guest / "src" / "core.py")}
    assert injected(run_hook(tmp_path, from_owned)) == ""
    from_guest = touch(guest, "x")
    from_guest["tool_input"] = {"file_path": str(owned / "src" / "new" / "core.py")}
    assert "rule python" in injected(run_hook(tmp_path, from_guest))


def test_git_runs_only_when_an_owner_rule_matched(tmp_path: Path, owned: Path) -> None:
    fake = tmp_path / "bin"
    fake.mkdir()
    log = tmp_path / "git-calls"
    (fake / "git").write_text("#!/bin/sh\necho called >> %s\nexit 1\n" % log)
    (fake / "git").chmod(0o755)
    path = "%s:%s" % (fake, os.environ["PATH"])
    run_hook(tmp_path, touch(owned, "README.md"), PATH=path)
    run_hook(tmp_path, touch(owned, "backlog/tasks/task-1 - X.md"), PATH=path)
    assert not log.exists()
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "a.py"), PATH=path))
    assert log.read_text().count("called") == 1


def test_guest_mode_is_cached_per_directory(tmp_path: Path, guest: Path) -> None:
    fake = tmp_path / "bin"
    fake.mkdir()
    log = tmp_path / "git-calls"
    real_git = subprocess.run(
        ["sh", "-c", "command -v git"], capture_output=True, text=True
    ).stdout.strip()
    (fake / "git").write_text('#!/bin/sh\necho called >> %s\nexec %s "$@"\n' % (log, real_git))
    (fake / "git").chmod(0o755)
    path = "%s:%s" % (fake, os.environ["PATH"])
    for _ in range(3):
        assert injected(run_hook(tmp_path, touch(guest, "src/core.py"), PATH=path)) == ""
    assert log.read_text().count("called") == 1


def test_rule_is_delivered_even_when_markers_cannot_be_written(tmp_path: Path, owned: Path) -> None:
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / "claude-philosophy-plugin").write_text(
        "a file where the marker directory goes"
    )
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "a.py")))
    assert "rule python" in injected(run_hook(tmp_path, touch(owned, "a.py")))


def test_other_commands_deliver_nothing(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, bash(owned, "git status && echo backlog"))) == ""


def test_unrelated_file_injects_nothing(tmp_path: Path, owned: Path) -> None:
    assert injected(run_hook(tmp_path, touch(owned, "README.md"))) == ""
    assert injected(run_hook(tmp_path, touch(owned, ".claude/worktrees/a/notes.md"))) == ""


def test_tool_without_a_file_injects_nothing(tmp_path: Path, owned: Path) -> None:
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "cwd": str(owned),
        "tool_input": {},
    }
    assert injected(run_hook(tmp_path, payload)) == ""


def test_bad_input_never_breaks_the_session(tmp_path: Path) -> None:
    result = run_hook(tmp_path, "this is not json")
    assert result.returncode == 0
    assert result.stdout == ""
    assert "[philosophy] hook skipped" in result.stderr
