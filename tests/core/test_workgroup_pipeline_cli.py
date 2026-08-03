"""Console parity for named pipelines: listing, the active run, and `workgroup trigger`."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi import cli
from alpi import home as home_mod
from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer

_CHAINS = {
    "setup": ["setup", "build", "qa"],
    "media-update": ["media-update", "media-qa"],
}
_STEPS = {
    "setup": {"owner": "scout", "task": "gather the brief"},
    "build": {"owner": "pixel", "task": "build it"},
    "qa": {"owner": "lens", "task": "audit it"},
    "media-update": {"owner": "muse", "task": "map the supplied media"},
    "media-qa": {"owner": "lens", "task": "audit the rebuild"},
}
_EXPECTED_CHAINS = {k: tuple(v) for k, v in _CHAINS.items()}


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-wg-cli-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _hub(home: Path, *, launch: str | None = "setup", owners=("scout", "pixel", "lens", "muse")):
    home.mkdir(parents=True, exist_ok=True)
    kp = load_or_generate(home)
    pubkeys = []
    for name in owners:
        member_home = home.parent / name
        member_home.mkdir(parents=True, exist_ok=True)
        pk = load_or_generate(member_home).pubkey_b64()
        from alpi.alp import peers as peers_mod
        peers_mod.add(home, Peer(id=name, pubkey=pk, allow=["workgroup.post"]))
        pubkeys.append(pk)
    return wg_mod.create(
        home, name="factory", hub_kp=kp, member_pubkeys=pubkeys,
        pipelines=_CHAINS, launch_pipeline=launch, pipeline_steps=_STEPS,
    )


def _run(monkeypatch, home: Path, args: list[str]):
    monkeypatch.setattr(home_mod, "_ROOT", home)
    monkeypatch.setenv("ALPI_HOME", str(home))
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    return CliRunner().invoke(cli.main, args)


def test_show_prints_every_pipeline_with_the_launch_marker(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    out = _run(monkeypatch, home, ["workgroup", "show", wg.meta.id]).output
    assert "Pipelines" in out
    flat = " ".join(out.split())
    assert "setup setup → build → qa launch" in flat
    assert "media-update media-update → media-qa" in flat
    assert flat.count("launch") == 1


def test_show_reports_a_launchless_workgroup_as_such(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, launch=None)
    out = _run(monkeypatch, home, ["workgroup", "show", wg.meta.id]).output
    assert "no launch pipeline" in out
    assert "deliberation" not in out


def test_list_annotates_pipelines_and_the_selector(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "hub"
    _hub(home, launch=None)
    out = _run(monkeypatch, home, ["workgroup", "list"]).output
    assert "pipelines: 2 · launch: none" in out


@pytest.mark.asyncio
async def test_show_prints_the_transcript_selected_run_not_the_launch_chain(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    await wc.trigger_pipeline(home, wg.meta.id, "media-update")
    out = _run(monkeypatch, home, ["workgroup", "show", wg.meta.id]).output
    assert "Active pipeline: media-update [running]" in out
    assert "media-update current" in out


def test_trigger_publishes_the_declared_opener(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    result = _run(monkeypatch, home, ["workgroup", "trigger", wg.meta.id, "media-update"])
    assert result.exit_code == 0, result.output
    assert "triggered media-update · opened #media-update at seq 1" in result.output

    from alpi.host import workgroup as host_wg
    posts = host_wg.decrypt_transcript(home, wg.meta.id)
    assert [p["body"] for p in posts] == ["@muse #task #media-update · map the supplied media"]


def test_trigger_surfaces_the_daemon_rejection_verbatim(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    result = _run(monkeypatch, home, ["workgroup", "trigger", wg.meta.id, "nope"])
    assert result.exit_code != 0
    assert "pipeline-unknown" in result.output

    from alpi.host import workgroup as host_wg
    assert host_wg.decrypt_transcript(home, wg.meta.id) == []


@pytest.mark.parametrize("chain", ["setup, build", ""])
def test_update_has_no_pipeline_option(short_tmp: Path, monkeypatch, chain: str) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    result = _run(
        monkeypatch, home,
        ["workgroup", "update", wg.meta.id, "--pipeline", chain],
    )
    assert result.exit_code != 0
    assert "No such option" in result.output and "--pipeline" in result.output
    reloaded = wg_mod.load(home, wg.meta.id)
    assert reloaded.meta.pipelines == _EXPECTED_CHAINS
    assert reloaded.meta.launch_pipeline == "setup"


@pytest.mark.parametrize("command", ["create", "update"])
def test_pipelines_are_not_editable_from_the_console(command: str) -> None:
    out = CliRunner().invoke(cli.main, ["workgroup", command, "--help"]).output
    assert "--pipeline" not in out


def test_trigger_is_reachable_from_the_workgroup_group() -> None:
    out = CliRunner().invoke(cli.main, ["workgroup", "--help"]).output
    assert "trigger" in out


def test_setup_menu_exposes_pipelines_and_trigger(short_tmp: Path) -> None:
    from alpi.alp import workgroup_setup as wg_setup

    home = short_tmp / "hub"
    wg = _hub(home, launch=None)
    assert wg_setup._pipelines_summary(wg.meta) == "2 · launch: none"
    reloaded = wg_mod.load(home, wg.meta.id)
    reloaded.meta.launch_pipeline = "setup"
    assert wg_setup._pipelines_summary(reloaded.meta) == "2 · launch: setup"


def test_subscriber_show_lists_the_hydrated_chains(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "member"
    home.mkdir(parents=True)
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_abc", name="factory", hub_id="mira", hub_pubkey="HUB",
    )
    sub.absorb_pipeline_state({
        "pipelines": {k: list(v) for k, v in _CHAINS.items()},
        "launch_pipeline": "setup",
        "pipeline_mode": True,
        "phase_map": {"setup": {"owner": "scout", "task": "gather the brief"}},
    })
    sub_mod.upsert(home, sub)
    out = _run(monkeypatch, home, ["workgroup", "show", "wg_abc"]).output
    assert "Pipelines" in out
    assert "media-update → media-qa" in out
    assert "launch" in out


def test_trigger_prints_the_run_it_stopped(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    first = _run(monkeypatch, home, ["workgroup", "trigger", wg.meta.id, "setup"])
    assert first.exit_code == 0, first.output
    assert "stopped" not in first.output
    result = _run(monkeypatch, home, ["workgroup", "trigger", wg.meta.id, "media-update"])
    assert result.exit_code == 0, result.output
    assert "stopped setup (running at #setup) · preempted open #setup" in result.output
    assert "triggered media-update · opened #media-update" in result.output


def test_trigger_help_states_the_one_at_a_time_rule() -> None:
    out = CliRunner().invoke(cli.main, ["workgroup", "trigger", "--help"]).output
    flat = " ".join(out.split())
    assert "Pipelines run one at a time" in flat
    assert "preempting an open task" in flat


def test_create_makes_a_deliberation_workgroup(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "hub"
    home.mkdir(parents=True, exist_ok=True)
    load_or_generate(home)
    result = _run(monkeypatch, home, [
        "workgroup", "create", "adhoc", "--quorum-timeout", "120",
    ])
    assert result.exit_code == 0, result.output
    assert "deliberation" in result.output
    wgs = wg_mod.list_workgroups(home)
    assert len(wgs) == 1
    assert wgs[0].meta.pipelines == {}
    assert wgs[0].meta.launch_pipeline is None
    assert wgs[0].meta.quorum_timeout_seconds == 120
