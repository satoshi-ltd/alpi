from pathlib import Path

from click.testing import CliRunner

from alpi import cli, runs
from alpi.core.run_context import RunContext


def test_runs_list_and_show(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    context = RunContext("run-one", tmp_path, tmp_path, "default", "user", "s", "host")
    runs.start(context, model="model-a", input_text="hello")
    runs.finish(context, "completed")
    runner = CliRunner()

    listed = runner.invoke(cli.main, ["runs", "list"])
    assert listed.exit_code == 0
    assert "run-one" in listed.output
    assert "completed" in listed.output

    shown = runner.invoke(cli.main, ["runs", "show", "run-one", "--json"])
    assert shown.exit_code == 0
    assert '"input": "hello"' in shown.output
