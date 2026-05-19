"""`schedule(action="add")` auto-infers `no_agent=true` when the prompt starts with `python` / `python3` and the caller omitted the flag — the original abby/reminder failure mode (LLM model forgot the flag, daemon would have fired the shell command as a chat prompt)."""
from __future__ import annotations

from pathlib import Path

from alpi.tools.schedule import Schedule, _looks_like_shell_command


def _add(profile_home: Path, **kw):
    return Schedule().run(action="add", **kw)


# --------------------------------------------------------------------
# _looks_like_shell_command heuristic
# --------------------------------------------------------------------


def test_looks_like_shell_command_python_forms() -> None:
    assert _looks_like_shell_command("python3 /a/b.py x")
    assert _looks_like_shell_command("  python /a/b.py")
    assert _looks_like_shell_command("python3.11 /a/b.py")
    # Absolute python path on macOS / nix.
    assert _looks_like_shell_command("/usr/bin/python3 /a/b.py")


def test_looks_like_shell_command_rejects_normal_prompts() -> None:
    assert not _looks_like_shell_command("Send the daily summary at 9am")
    assert not _looks_like_shell_command("")
    assert not _looks_like_shell_command("   ")
    assert not _looks_like_shell_command("npm run build")
    assert not _looks_like_shell_command("Run the inbox-triage skill")


def test_looks_like_shell_command_rejects_python_prose() -> None:
    """A legitimate LLM prompt that incidentally begins with `python` must NOT be classified as a shell command — the second token decides. `python is a language, explain it` is prose ("is" is not a path); the agent path should still receive it."""
    assert not _looks_like_shell_command("python is a language, explain it")
    assert not _looks_like_shell_command("python and ruby are similar")
    assert not _looks_like_shell_command("python")  # single token, no second arg
    # Even with the looks-like name, a non-path second token disqualifies.
    assert not _looks_like_shell_command("python3 keeps surprising me")


def test_looks_like_shell_command_accepts_path_like_second_token() -> None:
    """The discriminator is "second token starts with /, ~, or ${ALPI_HOME}"."""
    assert _looks_like_shell_command("python3 /abs/path.py")
    assert _looks_like_shell_command("python3 ~/relative.py")
    assert _looks_like_shell_command("python3 ${ALPI_HOME}/skills/x/y/scripts/z.py")
    assert _looks_like_shell_command("python3 $ALPI_HOME/skills/x/y/scripts/z.py")


def test_looks_like_shell_command_skips_python_flags() -> None:
    """validate_no_agent_command accepts `python3 -u <script>`; the heuristic must skip flags and look at the first non-flag arg, otherwise valid jobs with `-u`, `-O`, `-B` etc. get dropped to the LLM path."""
    assert _looks_like_shell_command("python3 -u ${ALPI_HOME}/skills/x/y/scripts/z.py")
    assert _looks_like_shell_command("python3 -OO ${ALPI_HOME}/skills/x/y/scripts/z.py arg")
    assert _looks_like_shell_command("python3 -u -B /abs/script.py")


def test_looks_like_shell_command_handles_quoted_paths() -> None:
    """Naive `.split()` keeps quotes attached to the path token. Switching to `shlex` strips them so `python3 "${ALPI_HOME}/.../x.py"` is recognised."""
    assert _looks_like_shell_command('python3 "${ALPI_HOME}/skills/x/y/scripts/z.py"')
    assert _looks_like_shell_command("python3 '/abs/path with spaces/x.py'")
    assert _looks_like_shell_command('python3 -u "${ALPI_HOME}/skills/x/y/scripts/z.py"')


# --------------------------------------------------------------------
# add action — auto-inference end-to-end
# --------------------------------------------------------------------


def test_add_auto_infers_no_agent_when_prompt_is_python(
    tmp_home_no_env: Path,
) -> None:
    """Reproduce the abby/reminder failure mode (no_agent omitted) and assert the tool now auto-corrects."""
    script = (
        tmp_home_no_env / "skills" / "personal" / "reminder"
        / "scripts" / "say.py"
    )
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env python3\nprint('hi')\n")

    res = _add(
        tmp_home_no_env, kind="once", run_at="2099-01-01T09:00:00",
        prompt=f'python3 {script} "hola"',
    )
    assert res.ok, res.error
    assert "auto-inferred no_agent=true" in res.output

    import json
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert jobs[0]["no_agent"] is True


def test_add_auto_infer_still_validates_path(tmp_home_no_env: Path) -> None:
    """Auto-inference must run path validation — a wrong path still fails fast at add time, not at fire time. This is the OTHER abby failure mode: hardcoding the absolute path of the wrong profile."""
    res = _add(
        tmp_home_no_env, kind="once", run_at="2099-01-01T09:00:00",
        prompt='python3 /tmp/outside_skills/say.py "x"',
    )
    assert not res.ok
    # Validator message comes from validate_no_agent_command — anchored on "skills/".
    assert "skills" in (res.error or "")


def test_add_respects_explicit_no_agent_false(tmp_home_no_env: Path) -> None:
    """If the caller explicitly passes no_agent=False, the heuristic must NOT override — that path is the agent-driven escape hatch (e.g. the user really wants the LLM to receive a Python-looking literal text)."""
    res = _add(
        tmp_home_no_env, kind="once", run_at="2099-01-01T09:00:00",
        prompt='python3 some words pretending to be a shell command',
        no_agent=False,
    )
    # _validate_prompt threat scanner only blocks specific patterns; this passes.
    assert res.ok, res.error
    assert "auto-inferred" not in res.output
    import json
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert "no_agent" not in jobs[0]


def test_add_respects_explicit_no_agent_true(tmp_home_no_env: Path) -> None:
    """Explicit no_agent=True takes the same path as the inference but doesn't claim auto-inference in the output (the user gave the answer)."""
    script = (
        tmp_home_no_env / "skills" / "personal" / "reminder"
        / "scripts" / "say.py"
    )
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env python3\nprint('hi')\n")

    res = _add(
        tmp_home_no_env, kind="once", run_at="2099-01-01T09:00:00",
        prompt=f'python3 {script}',
        no_agent=True,
    )
    assert res.ok, res.error
    assert "auto-inferred" not in res.output


def test_add_auto_infers_with_python_flag(tmp_home_no_env: Path) -> None:
    """End-to-end: `python3 -u <skills_script>` (flag between python and script) without `no_agent` still infers True and persists. Real users add `-u` for unbuffered logging."""
    script = (
        tmp_home_no_env / "skills" / "personal" / "reminder"
        / "scripts" / "say.py"
    )
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env python3\nprint('hi')\n")

    res = _add(
        tmp_home_no_env, kind="once", run_at="2099-01-01T09:00:00",
        prompt=f'python3 -u {script} "hi"',
    )
    assert res.ok, res.error
    assert "auto-inferred no_agent=true" in res.output

    import json
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert jobs[0]["no_agent"] is True


def test_add_python_prose_prompt_falls_through_to_agent_path(
    tmp_home_no_env: Path,
) -> None:
    """End-to-end version of the prose discriminator: a scheduled job whose prompt happens to start with `python` but is prose (no path-like second token) must NOT auto-infer no_agent. It's accepted as an agent prompt — the threat scanner is the only filter — and persists WITHOUT `no_agent: true`."""
    res = _add(
        tmp_home_no_env, kind="cron", expression="0 9 * * *",
        prompt="python is a language, explain it to me",
    )
    assert res.ok, res.error
    assert "auto-inferred" not in res.output
    import json
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert "no_agent" not in jobs[0]  # stayed on the agent path


def test_add_normal_prompt_unchanged(tmp_home_no_env: Path) -> None:
    """Sanity: a regular agent prompt is NOT touched by the heuristic — auto-inference must be opt-in via shell-command lookalike."""
    res = _add(
        tmp_home_no_env, kind="cron", expression="0 9 * * *",
        prompt="Send a daily greeting to the user.",
    )
    assert res.ok, res.error
    assert "auto-inferred" not in res.output
    import json
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert "no_agent" not in jobs[0]
