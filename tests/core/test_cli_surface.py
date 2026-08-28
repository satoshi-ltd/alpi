"""Guardrails on what ``alpi --help`` shows the user.

The CLI is deliberately thin: everything configurable lives in
``alpi setup``, logs are unified under ``alpi logs``, and the
machine-wide lifecycle (install/start/stop/restart/status/uninstall)
lives under ``alpi daemon``. Per-profile services are toggled in
each profile's ``config.yaml`` (no CLI surface).
"""

from __future__ import annotations

from click.testing import CliRunner

from alpi import cli


def test_top_level_help_shows_only_canonical_commands() -> None:
    result = CliRunner().invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    out = result.output

    for name in ("chat", "setup", "doctor", "logs", "profile", "daemon",
                 "schedule", "peers", "workgroup", "release", "email",
                 "mcp", "providers", "sandbox", "voice", "outputs", "audit-log"):
        assert name in out, f"{name!r} missing from top-level --help"

    assert "runs" in out

    assert "\n  alp " not in out, "alp group should be gone"
    assert "\n  service " not in out, "service group should have been renamed to daemon"


def test_chat_help_does_not_expose_emit_events() -> None:
    result = CliRunner().invoke(cli.main, ["chat", "--help"])
    assert result.exit_code == 0
    assert "--once" in result.output
    assert "--emit-events" not in result.output


def test_chat_help_exposes_attach() -> None:
    result = CliRunner().invoke(cli.main, ["chat", "--help"])
    assert "--attach" in result.output


def test_chat_help_exposes_connection_id() -> None:
    result = CliRunner().invoke(cli.main, ["chat", "--help"])
    assert "--connection-id" in result.output


def test_run_once_delegated_calls_host_stream(monkeypatch, capsys) -> None:
    captured = {}

    async def fake_delegate(profile, connection_id, text, **kwargs):  # noqa: ANN001
        captured.update(profile=profile, connection_id=connection_id, text=text, **kwargs)
        return "pong", []

    monkeypatch.setattr(cli, "_host_chat_delegate", fake_delegate)
    cli._run_once_delegated("smith", "conn_test", "ping")
    assert captured["profile"] == "smith"
    assert captured["connection_id"] == "conn_test"
    assert captured["text"] == "ping"
    assert capsys.readouterr().out == "pong\n"


def test_run_once_forwards_attachments(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    captured = {}

    class FakeEngine:
        def __init__(self, *, home, cfg):  # noqa: ANN001
            self.session = SimpleNamespace(id="x", subdir="sessions")

        def run_turn(self, text, emit, *, persist_inflight=True, attachments=None, **kw):  # noqa: ANN001
            captured["text"] = text
            captured["attachments"] = attachments

        def request_interrupt(self, reason="unknown"):
            return None

    monkeypatch.setattr(cli, "Engine", FakeEngine)
    monkeypatch.setattr(cli, "_bootstrap", lambda h: None)
    monkeypatch.setattr(cli.config, "load", lambda h: SimpleNamespace(model="x"))
    img = tmp_path / "room.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    cli._run_once(tmp_path, "improve it", attach=(str(img),))

    assert captured["text"] == "improve it"
    assert captured["attachments"][0]["path"].endswith("room.png")
    assert captured["attachments"][0]["name"] == "room.png"


def test_daemon_help_lists_lifecycle_verbs() -> None:
    result = CliRunner().invoke(cli.main, ["daemon", "--help"])
    assert result.exit_code == 0
    for sub in ("start", "stop", "restart", "status", "install", "uninstall"):
        assert sub in result.output


def test_schedule_help_lists_only_operational_verbs() -> None:
    """After unification, lifecycle moved to ``alpi daemon``; the
    ``schedule`` group keeps ``list``, ``run-once`` and ``fire``."""
    result = CliRunner().invoke(cli.main, ["schedule", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "run-once", "fire"):
        assert sub in result.output
    for gone in ("start", "stop", "restart", "status", "install", "uninstall"):
        assert f"\n  {gone}" not in result.output, f"schedule {gone} should be gone"


def test_dropped_commands_are_gone() -> None:
    for argv in (
        ["alp"],
        ["schedule", "start"],
        ["schedule", "stop"],
        ["schedule", "restart"],
    ):
        result = CliRunner().invoke(cli.main, argv)
        assert result.exit_code != 0, f"{argv} should not exist"


def test_profile_subcommands_include_remove() -> None:
    result = CliRunner().invoke(cli.main, ["profile", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "create", "remove"):
        assert sub in result.output


def test_logs_help_lists_source_filter() -> None:
    result = CliRunner().invoke(cli.main, ["logs", "--help"])
    assert result.exit_code == 0
    assert "--source" in result.output
    assert "--follow" in result.output or "-f" in result.output


# Workspace validation — fail fast before the orchestrator loops


# Workspace validation moved per-profile / per-subsystem. The central
# daemon supervises every profile under ``~/.alpi`` and a bad
# workspace on one profile no longer blocks the whole start — the
# affected subsystems log + skip, siblings keep running. The previous
# ``test_service_start_rejects_*`` tests gated on the old per-profile
# workspace check at ``service start`` and have been removed.


def test_workgroup_launch_is_text_only() -> None:
    result = CliRunner().invoke(cli.main, ["workgroup", "launch", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.output
    assert "--assets" not in result.output


def test_workgroup_recipes_lists_saved_recipes(tmp_path, monkeypatch) -> None:
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "hotel.yaml").write_text("hub: mira\nname: Hotel factory\n")
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "_bootstrap", lambda _home: None)

    result = CliRunner().invoke(cli.main, ["workgroup", "recipes"])

    assert result.exit_code == 0
    assert result.output == "hotel  Hotel factory\n"


def test_workgroup_recipes_lists_valid_entries_and_warns_for_invalid(
    tmp_path, monkeypatch,
) -> None:
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "hotel.yaml").write_text("hub: mira\nname: Hotel factory\n")
    (recipes / "broken.yaml").write_text("hub: mira\n")
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "_bootstrap", lambda _home: None)

    result = CliRunner().invoke(cli.main, ["workgroup", "recipes"])

    assert result.exit_code == 0
    assert "hotel  Hotel factory" in result.output
    assert "saved recipe 'broken' ignored" in result.output


def test_workgroup_launch_rejects_binary_input(tmp_path) -> None:
    recipe = tmp_path / "r.yaml"
    recipe.write_text("hub: mira\nmembers: [scout]\ninputs:\n  brief: {dest: brief.md}\n")
    binary = tmp_path / "photo.jpg"
    binary.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\xfe\xab")
    result = CliRunner().invoke(cli.main, [
        "workgroup", "launch", "--recipe", str(recipe), "--input", f"brief={binary}",
    ])
    assert result.exit_code != 0
    assert "text-only" in result.output
    assert "Traceback" not in result.output


def test_workgroup_launch_resolves_saved_recipe_id(tmp_path, monkeypatch) -> None:
    profile_home = tmp_path
    recipes = profile_home / "recipes"
    recipes.mkdir(parents=True)
    (recipes / "hotel.yaml").write_text("hub: mira\nname: hotel\n")
    captured = {}

    async def launch(home, yaml, params, **kwargs):
        captured.update(home=home, yaml=yaml, params=params, kwargs=kwargs)
        return {"workgroup_id": "wg-hotel", "project_path": None}

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "_bootstrap", lambda _home: None)
    from alpi.host import recipes as host_recipes
    monkeypatch.setattr(host_recipes, "launch", launch)

    result = CliRunner().invoke(cli.main, ["workgroup", "launch", "--recipe", "hotel"])

    assert result.exit_code == 0
    assert result.output == "launched wg-hotel\n"
    assert captured == {
        "home": profile_home,
        "yaml": "hub: mira\nname: hotel\n",
        "params": {},
        "kwargs": {
            "briefing_override": None,
            "recipe_id": "hotel",
            "inputs": {},
        },
    }
