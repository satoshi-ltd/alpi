from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from alpi.cli import logs_cmd, main as alpi_main


@pytest.fixture
def alpi_tree(tmp_path: Path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "service.log").write_text(
        "2026-06-22 10:00:00 INFO ROOT-SERVICE-MARKER\n"
    )

    mira_home = tmp_path / "profiles" / "mira"
    (mira_home / "logs").mkdir(parents=True)
    (mira_home / "logs" / "agent.log").write_text(
        "2026-06-22 10:00:00 INFO MIRA-AGENT-MARKER\n"
    )
    (mira_home / "logs" / "service.log").write_text(
        "2026-06-22 10:00:00 INFO MIRA-PHANTOM-SERVICE\n"
    )
    return tmp_path, mira_home


def test_source_service_reads_root_even_under_profile_flag(alpi_tree):
    root, mira_home = alpi_tree
    runner = CliRunner()
    with patch("alpi.home.alpi_root", return_value=root):
        result = runner.invoke(
            logs_cmd, ["--source", "service"], obj={"home": mira_home},
        )
    assert result.exit_code == 0, result.output
    assert "ROOT-SERVICE-MARKER" in result.output, (
        "logs --source service must read ~/.alpi/logs/service.log via alpi_root(), "
        "not the active profile's logs/"
    )
    assert "MIRA-PHANTOM-SERVICE" not in result.output, (
        "the per-profile service.log must NOT be selected — root-only contract"
    )


def test_source_agent_reads_active_profile(alpi_tree):
    root, mira_home = alpi_tree
    runner = CliRunner()
    with patch("alpi.home.alpi_root", return_value=root):
        result = runner.invoke(
            logs_cmd, ["--source", "agent"], obj={"home": mira_home},
        )
    assert result.exit_code == 0, result.output
    assert "MIRA-AGENT-MARKER" in result.output, (
        "logs --source agent must read the active profile's agent.log"
    )
    assert "ROOT-SERVICE-MARKER" not in result.output


def test_default_source_uses_active_profile(alpi_tree):
    root, mira_home = alpi_tree
    runner = CliRunner()
    with patch("alpi.home.alpi_root", return_value=root):
        result = runner.invoke(logs_cmd, [], obj={"home": mira_home})
    assert result.exit_code == 0, result.output
    assert "MIRA-AGENT-MARKER" in result.output
    assert "ROOT-SERVICE-MARKER" not in result.output, (
        "with no --source, logs read from the active profile only"
    )


def test_dash_p_belongs_to_root_group_not_to_logs():
    """`alpi logs -p mira ...` must NOT be accepted — `-p` is on the root command."""
    runner = CliRunner()
    result = runner.invoke(alpi_main, ["logs", "-p", "mira", "--help"])
    assert result.exit_code != 0, (
        "`-p` belongs to the root `alpi` group; `alpi logs -p mira ...` should fail at parse time"
    )
