"""ALP peer list — load/save/add/remove + capability check."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.alp import peers as peers_mod
from alpi.alp.peers import Peer


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    assert peers_mod.load(tmp_path) == []


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    p = Peer(
        id="home-server", pubkey="AAA=", alias="NAS",
        address="nas.local:7423", allow=["link.ping", "link.ask"],
    )
    peers_mod.save(tmp_path, [p])
    loaded = peers_mod.load(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].id == "home-server"
    assert loaded[0].allow == ["link.ping", "link.ask"]
    assert loaded[0].address == "nas.local:7423"


def test_save_trims_empty_optional_fields(tmp_path: Path) -> None:
    p = Peer(id="x", pubkey="AAA=", allow=["link.ping"])
    peers_mod.save(tmp_path, [p])
    text = peers_mod.path(tmp_path).read_text()
    assert "alias" not in text
    assert "address" not in text
    assert "budget" not in text


def test_get_by_id_and_pubkey(tmp_path: Path) -> None:
    peers_mod.save(tmp_path, [Peer(id="a", pubkey="PA==", allow=["link.ping"])])
    assert peers_mod.get_by_id(tmp_path, "a").pubkey == "PA=="
    assert peers_mod.get_by_pubkey(tmp_path, "PA==").id == "a"
    assert peers_mod.get_by_id(tmp_path, "missing") is None
    assert peers_mod.get_by_pubkey(tmp_path, "XX==") is None


def test_add_rejects_duplicate_id(tmp_path: Path) -> None:
    peers_mod.add(tmp_path, Peer(id="a", pubkey="P1==", allow=[]))
    with pytest.raises(ValueError, match="already exists"):
        peers_mod.add(tmp_path, Peer(id="a", pubkey="P2==", allow=[]))


def test_add_rejects_duplicate_pubkey(tmp_path: Path) -> None:
    peers_mod.add(tmp_path, Peer(id="a", pubkey="PA==", allow=[]))
    with pytest.raises(ValueError, match="pubkey already pinned"):
        peers_mod.add(tmp_path, Peer(id="b", pubkey="PA==", allow=[]))


def test_remove(tmp_path: Path) -> None:
    peers_mod.add(tmp_path, Peer(id="a", pubkey="PA==", allow=[]))
    assert peers_mod.remove(tmp_path, "a") is True
    assert peers_mod.load(tmp_path) == []
    assert peers_mod.remove(tmp_path, "a") is False


def test_may_call_is_fail_closed() -> None:
    p = Peer(id="a", pubkey="PA==", allow=[])
    assert p.may_call("link.ping") is False

    p2 = Peer(id="b", pubkey="PB==", allow=["link.ping"])
    assert p2.may_call("link.ping") is True
    assert p2.may_call("link.ask") is False


def test_malformed_yaml_returns_empty(tmp_path: Path) -> None:
    peers_mod.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    peers_mod.path(tmp_path).write_text("::: not yaml :::")
    assert peers_mod.load(tmp_path) == []


def test_entries_missing_required_fields_are_skipped(tmp_path: Path) -> None:
    peers_mod.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    peers_mod.path(tmp_path).write_text(
        "- id: a\n"
        "  pubkey: PA==\n"
        "  allow: [link.ping]\n"
        "- alias: orphan\n"
    )
    loaded = peers_mod.load(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].id == "a"


def test_local_socket_path_resolves_by_pubkey_first(tmp_path, monkeypatch) -> None:
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod

    root = tmp_path / ".alpi"
    root.mkdir()
    target = root / "profiles" / "real_name"
    target.mkdir(parents=True)
    target_kp = keys_mod.generate(target)
    monkeypatch.setattr(home_mod, "_ROOT", root)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    peer = Peer(
        id="totally_random_alias",
        pubkey=target_kp.pubkey_b64(),
        allow=["link.ping"],
    )
    assert peers_mod.local_socket_path(peer) == target / "alp" / "alp.sock"


def test_local_socket_path_falls_back_to_peer_id_when_pubkey_unknown(
    tmp_path, monkeypatch,
) -> None:
    from alpi import home as home_mod

    root = tmp_path / ".alpi"
    root.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", root)
    monkeypatch.delenv("ALPI_HOME", raising=False)

    peer = Peer(id="remote", pubkey="REMOTE_NOT_LOCAL", allow=["link.ping"])
    expected = root / "profiles" / "remote" / "alp" / "alp.sock"
    assert peers_mod.local_socket_path(peer) == expected


def test_local_socket_path_default_profile(tmp_path, monkeypatch) -> None:
    from alpi import home as home_mod

    root = tmp_path / ".alpi"
    root.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", root)
    monkeypatch.delenv("ALPI_HOME", raising=False)

    peer = Peer(id="default", pubkey="UNKNOWN", allow=["link.ping"])
    assert peers_mod.local_socket_path(peer) == root / "alp" / "alp.sock"


def test_local_socket_path_honors_alpi_home_on_fallback(
    tmp_path, monkeypatch,
) -> None:
    alt_root = tmp_path / "alt-root"
    alt_root.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(alt_root))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "noise"))

    peer = Peer(id="remote", pubkey="REMOTE_NOT_LOCAL", allow=["link.ping"])
    assert peers_mod.local_socket_path(peer) == alt_root / "profiles" / "remote" / "alp" / "alp.sock"

    peer_default = Peer(id="default", pubkey="UNKNOWN", allow=["link.ping"])
    assert peers_mod.local_socket_path(peer_default) == alt_root / "alp" / "alp.sock"


def test_local_socket_path_resolves_alias_by_pubkey_under_alpi_home(
    tmp_path, monkeypatch,
) -> None:
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod

    alt_root = tmp_path / "alt-root"
    real_target = alt_root / "profiles" / "real_name"
    real_target.mkdir(parents=True)
    target_kp = keys_mod.generate(real_target)

    monkeypatch.setenv("ALPI_HOME", str(alt_root))
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path / "noise-default")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "noise"))

    peer = Peer(
        id="completely_unrelated_alias",
        pubkey=target_kp.pubkey_b64(),
        allow=["link.ping"],
    )
    assert peers_mod.local_socket_path(peer) == real_target / "alp" / "alp.sock"


def test_local_socket_path_when_alpi_home_is_a_profile(
    tmp_path, monkeypatch,
) -> None:
    # The daemon dispatches workgroup turns with ALPI_HOME set to the *profile* home (e.g. ~/.alpi/profiles/vera). Peer routing must still see siblings under .../profiles/, not nest under self. Regression for v0.6.27 → v0.6.28: vera posting to prism would resolve to <vera>/profiles/prism/alp/alp.sock → ENOENT.
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod

    root = tmp_path / ".alpi"
    vera_home = root / "profiles" / "vera"
    prism_home = root / "profiles" / "prism"
    vera_home.mkdir(parents=True)
    prism_home.mkdir(parents=True)
    prism_kp = keys_mod.generate(prism_home)

    monkeypatch.setenv("ALPI_HOME", str(vera_home))
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path / "noise-default")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "noise"))

    peer = Peer(id="prism", pubkey=prism_kp.pubkey_b64(), allow=["link.ping"])
    assert peers_mod.local_socket_path(peer) == prism_home / "alp" / "alp.sock"

    # Fallback (unknown pubkey) also resolves to the sibling, not nested under self.
    peer_unknown = Peer(id="zeta", pubkey="UNKNOWN", allow=["link.ping"])
    assert peers_mod.local_socket_path(peer_unknown) == root / "profiles" / "zeta" / "alp" / "alp.sock"


def test_tool_policy_round_trips_and_normalises(tmp_path: Path) -> None:
    p = Peer(
        id="alexandra", pubkey="AAA=", allow=["link.ask"],
        tools={"allow": [" knowledge:search ", "knowledge:search", "github__*", "alpi_knowledge"]},
    )
    peers_mod.save(tmp_path, [p])

    loaded = peers_mod.load(tmp_path)[0]
    assert loaded.tools == {"allow": [" knowledge:search ", "knowledge:search", "github__*", "alpi_knowledge"]}
    assert loaded.allowed_tools() == frozenset({"knowledge:search", "github__*", "alpi_knowledge"})
    assert "tools:" in peers_mod.path(tmp_path).read_text()


def test_peers_without_a_tool_policy_save_no_tools_key(tmp_path: Path) -> None:
    peers_mod.save(tmp_path, [Peer(id="x", pubkey="AAA=", allow=["link.ping"])])
    assert "tools" not in peers_mod.path(tmp_path).read_text()
    assert peers_mod.load(tmp_path)[0].allowed_tools() is None


@pytest.mark.parametrize("tools_yaml", [
    "tools: terminal",
    "tools: false",
    "tools:",
    "tools:\n    allow: terminal",
    "tools:\n    allow:\n      a: b",
    "tools:\n    allow:",
    "tools:\n    alow: [read_file]",
    "tools:\n    allow: [read_file, 'bad name!']",
    "tools:\n    allow: [read_file, 7]",
    "tools:\n    allow: ['knowledge:']",
    "tools:\n    allow: ['knowledge:search:x']",
    "tools:\n    allow: ['knowledge:sea*']",
    "tools:\n    allow:\n      - knowledge: search",
    "tools:\n    deny: [terminal]",
    "tools:\n    deny: []",
    "tools:\n    allow: [read_file]\n    deny: [terminal]",
])
def test_a_malformed_tool_policy_is_an_error_not_an_empty_policy(tmp_path: Path, tools_yaml: str) -> None:
    peers_mod.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    peers_mod.path(tmp_path).write_text(
        f"- id: a\n  pubkey: AAA=\n  allow: [link.ask]\n  {tools_yaml}\n",
    )
    loaded = peers_mod.load(tmp_path)[0]
    with pytest.raises(peers_mod.PolicyError) as err:
        loaded.allowed_tools()
    assert "peer 'a'" in str(err.value)


def test_a_deny_list_from_0_15_18_says_what_replaced_it(tmp_path: Path) -> None:
    p = Peer(id="a", pubkey="AAA=", allow=["link.ask"], tools={"deny": ["write_file"]})
    with pytest.raises(peers_mod.PolicyError) as err:
        p.allowed_tools()
    assert "tools.allow" in str(err.value)


def test_absent_policy_means_no_policy_and_an_empty_allow_means_no_tool(tmp_path: Path) -> None:
    peers_mod.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    peers_mod.path(tmp_path).write_text(
        "- id: a\n  pubkey: AAA=\n  allow: [link.ask]\n"
        "- id: b\n  pubkey: BBB=\n  allow: [link.ask]\n  tools: {}\n"
        "- id: c\n  pubkey: CCC=\n  allow: [link.ask]\n  tools:\n    allow: []\n",
    )
    assert [p.allowed_tools() for p in peers_mod.load(tmp_path)] == [None, None, frozenset()]


def test_saving_keeps_a_malformed_policy_so_the_diagnostic_survives(tmp_path: Path) -> None:
    peers_mod.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    peers_mod.path(tmp_path).write_text(
        "- id: a\n  pubkey: AAA=\n  allow: [link.ask]\n  tools: terminal\n"
        "- id: n\n  pubkey: NNN=\n  allow: [link.ask]\n  tools:\n"
        "- id: b\n  pubkey: BBB=\n  allow: [link.ask]\n",
    )
    assert peers_mod.remove(tmp_path, "b") is True
    for peer_id in ("a", "n"):
        with pytest.raises(peers_mod.PolicyError):
            peers_mod.get_by_id(tmp_path, peer_id).allowed_tools()


def test_set_allowed_tools_rejects_entries_that_are_not_tool_names(tmp_path: Path) -> None:
    peers_mod.save(tmp_path, [Peer(id="a", pubkey="AAA=", allow=["link.ask"])])
    with pytest.raises(peers_mod.PolicyError):
        peers_mod.set_allowed_tools(tmp_path, "a", ["read_file", "rm -rf /"])
    assert peers_mod.get_by_id(tmp_path, "a").allowed_tools() is None


def test_set_allowed_tools_sets_empties_and_clears(tmp_path: Path) -> None:
    peers_mod.save(tmp_path, [Peer(id="a", pubkey="AAA=", allow=["link.ask"])])

    assert peers_mod.set_allowed_tools(tmp_path, "a", ["knowledge:search", "alpi_knowledge"]) is True
    assert peers_mod.get_by_id(tmp_path, "a").allowed_tools() == frozenset({"knowledge:search", "alpi_knowledge"})
    assert peers_mod.set_allowed_tools(tmp_path, "a", []) is True
    assert peers_mod.get_by_id(tmp_path, "a").allowed_tools() == frozenset()
    assert "allow: []" in peers_mod.path(tmp_path).read_text()
    assert peers_mod.set_allowed_tools(tmp_path, "a", None) is True
    assert peers_mod.get_by_id(tmp_path, "a").allowed_tools() is None
    assert "tools" not in peers_mod.path(tmp_path).read_text()
    assert peers_mod.set_allowed_tools(tmp_path, "ghost", ["x"]) is False


def test_setting_one_peers_policy_replaces_a_legacy_deny_and_keeps_the_others(tmp_path: Path) -> None:
    peers_mod.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    peers_mod.path(tmp_path).write_text(
        "- id: a\n  pubkey: AAA=\n  allow: [link.ask]\n  tools:\n    deny: [terminal]\n"
        "- id: b\n  pubkey: BBB=\n  allow: [link.ask]\n  tools:\n    alow: [read_file]\n",
    )
    assert peers_mod.set_allowed_tools(tmp_path, "a", ["knowledge:search"]) is True

    assert peers_mod.get_by_id(tmp_path, "a").allowed_tools() == frozenset({"knowledge:search"})
    with pytest.raises(peers_mod.PolicyError) as err:
        peers_mod.get_by_id(tmp_path, "b").allowed_tools()
    assert "alow" in str(err.value)
    assert "alow" in peers_mod.path(tmp_path).read_text()


def test_peers_cli_sets_shows_empties_and_clears_the_allowlist(tmp_path: Path, monkeypatch) -> None:
    import base64

    from click.testing import CliRunner

    from alpi import cli

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    run = lambda *args: CliRunner().invoke(cli.main, ["peers", *args])  # noqa: E731
    key = base64.b64encode(b"k" * 32).decode()

    added = run("add", "alexandra", key, "--allow-tools", "knowledge:search, alpi_knowledge")
    assert added.exit_code == 0, added.output
    assert "may run only 2 tool(s)" in added.output
    assert peers_mod.get_by_id(tmp_path, "alexandra").allowed_tools() == frozenset({"knowledge:search", "alpi_knowledge"})
    assert "alpi_knowledge, knowledge:search" in run("tools", "alexandra").output
    assert "knowledge:search" in run("list").output

    assert "may run no tool" in run("tools", "alexandra", "--allow", "").output
    assert peers_mod.get_by_id(tmp_path, "alexandra").allowed_tools() == frozenset()
    assert "may run no tool" in run("tools", "alexandra", "--allow", " , ").output
    assert peers_mod.get_by_id(tmp_path, "alexandra").allowed_tools() == frozenset()
    assert "may run no tool" in run("tools", "alexandra").output

    assert run("tools", "alexandra", "--allow", "x", "--clear").exit_code != 0
    assert "cleared" in run("tools", "alexandra", "--clear").output
    assert peers_mod.get_by_id(tmp_path, "alexandra").allowed_tools() is None
    assert "no tool policy" in run("tools", "alexandra").output

    bad = run("tools", "alexandra", "--allow", "rm -rf /")
    assert bad.exit_code != 0 and "tools.allow" in bad.output
    assert peers_mod.get_by_id(tmp_path, "alexandra").allowed_tools() is None


@pytest.mark.parametrize("given, expected", [
    (None, None),
    ("", frozenset()),
    ("   ", frozenset()),
    (" , ,, ", frozenset()),
    ("knowledge:search, ,alpi_knowledge", frozenset({"knowledge:search", "alpi_knowledge"})),
])
def test_peers_add_never_widens_access_for_an_explicitly_empty_allowlist(
    tmp_path: Path, monkeypatch, given: str | None, expected: frozenset[str] | None,
) -> None:
    import base64

    from click.testing import CliRunner

    from alpi import cli

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    args = ["peers", "add", "a", base64.b64encode(b"k" * 32).decode()]
    if given is not None:
        args += ["--allow-tools", given]
    added = CliRunner().invoke(cli.main, args)

    assert added.exit_code == 0, added.output
    assert peers_mod.get_by_id(tmp_path, "a").allowed_tools() == expected
    if expected == frozenset():
        assert "may run no tool" in added.output
    if expected is None:
        assert "tool" not in added.output


def test_parse_allow_arg_keeps_absent_apart_from_empty() -> None:
    assert peers_mod.parse_allow_arg(None) is None
    assert peers_mod.parse_allow_arg("") == []
    assert peers_mod.parse_allow_arg(" , ") == []
    assert peers_mod.parse_allow_arg("a, b:c ,a") == ["a", "b:c"]
    with pytest.raises(peers_mod.PolicyError):
        peers_mod.parse_allow_arg("a, b c")


def test_peers_cli_reports_a_legacy_deny_list_as_invalid(tmp_path: Path, monkeypatch) -> None:
    from click.testing import CliRunner

    from alpi import cli

    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    peers_mod.save(tmp_path, [Peer(id="a", pubkey="AAA=", allow=["link.ask"], tools={"deny": ["terminal"]})])

    shown = CliRunner().invoke(cli.main, ["peers", "tools", "a"])
    assert shown.exit_code != 0 and "refused until fixed" in shown.output and "tools.allow" in shown.output
    assert "INVALID" in CliRunner().invoke(cli.main, ["peers", "list"]).output
