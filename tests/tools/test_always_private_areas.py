import shutil
import tempfile
from pathlib import Path

import pytest

from alpi import home as home_mod
from alpi import tools
from alpi.host.connection_context import ConnectionContext, use
from alpi.tools._paths import is_read_denied, resolve_path

ADMIN = ConnectionContext(connection_id="host", source="local", role="admin")

NO_ACCESS = (
    "secrets/gmail_tokens/a.json",
    "alp/secrets/alp_key",
    "host/connections.yaml",
)
WRITE_DENIED = (
    "schedule/jobs.json",
    "memories/AGENT.md",
    "logs/ledger.json",
    "runs/0123456789abcdef0123456789abcdef.jsonl",
    "sessions/s1.json",
    "recipes/r.yaml",
    "alp/peers.yaml",
)


@pytest.fixture(params=["default", "profile", "plain-name", "nested"])
def home(request, monkeypatch):
    base = Path(tempfile.mkdtemp(prefix="alp-private-", dir="/tmp")).resolve()
    root = {"plain-name": base / "alpi-data", "nested": base / ".alpi" / "data"}.get(request.param, base / ".alpi")
    root.mkdir(parents=True)
    monkeypatch.setattr(home_mod, "_ROOT", root)
    ws = base / "ws"
    ws.mkdir()
    target = root
    if request.param == "profile":
        target = root / "profiles" / "ana"
        target.mkdir(parents=True)
        monkeypatch.setenv("ALPI_PROFILE", "ana")
    (target / "config.yaml").write_text(f"workspace: {ws}\n")
    monkeypatch.chdir(ws)
    try:
        yield target
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def ws(home) -> Path:
    return Path(next(line.split(": ", 1)[1] for line in (home / "config.yaml").read_text().splitlines() if line.startswith("workspace")))


def _make(home: Path, rel: str) -> Path:
    p = home / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")
    return p


@pytest.mark.parametrize("rel", NO_ACCESS)
def test_an_admin_turn_cannot_read_or_write_credential_areas(home, rel):
    p = _make(home, rel)
    with use(ADMIN):
        for write in (False, True):
            with pytest.raises(ValueError):
                resolve_path(str(p), for_write=write)
        assert is_read_denied(p)


@pytest.mark.parametrize("rel", WRITE_DENIED)
def test_an_admin_turn_cannot_write_daemon_owned_areas_but_can_read_them(home, rel):
    p = _make(home, rel)
    with use(ADMIN):
        with pytest.raises(ValueError):
            resolve_path(str(p), for_write=True)
        assert resolve_path(str(p)) == p.resolve()
        assert not is_read_denied(p)


def test_staged_chat_attachments_stay_readable_but_not_writable(home):
    p = _make(home, "host/attachments/tmp/abc/photo.png")
    with use(ADMIN):
        assert resolve_path(str(p)) == p.resolve()
        assert not is_read_denied(p)
        with pytest.raises(ValueError):
            resolve_path(str(p), for_write=True)


@pytest.mark.parametrize("tool,key", [("read_file", None), ("write_file", "content"), ("edit_file", "old_string"), ("delete_file", None)])
def test_file_tools_refuse_the_connections_store(home, tool, key):
    store = _make(home, "host/connections.yaml")
    args = {"path": str(store)}
    if key == "content":
        args["content"] = "connections: []"
    if key == "old_string":
        args.update(old_string="x", new_string="y")
    with use(ADMIN):
        result = tools.execute(tool, args)
    assert result.ok is False
    assert store.read_text() == "x"


def test_search_never_returns_a_credential_file(home):
    _make(home, "secrets/gmail_tokens/a.json").write_text("REFRESH-TOKEN-VALUE")
    with use(ADMIN):
        result = tools.execute("search", {"pattern": "REFRESH-TOKEN-VALUE", "path": str(home)})
    assert "REFRESH-TOKEN-VALUE" not in f"{result.output}{result.error}"


def test_a_workspace_symlink_into_a_private_area_is_refused(home, ws):
    store = _make(home, "host/connections.yaml")
    link = ws / "link.yaml"
    link.symlink_to(store)
    with use(ADMIN):
        for write in (False, True):
            with pytest.raises(ValueError):
                resolve_path(str(link), for_write=write)


def test_email_download_cannot_land_in_a_private_area(home):
    from alpi.tools import email as email_mod
    called = {"n": 0}

    class StubClient:
        def download_attachment(self, **kw):
            called["n"] += 1

    with use(ADMIN):
        with pytest.raises(ValueError):
            email_mod._dispatch(StubClient(), "download_attachment", {
                "uid": "1", "attachment_name": "a.pdf",
                "dest_path": str(home / "host" / "connections.yaml"),
            })
    assert called["n"] == 0


@pytest.mark.parametrize("form", ["host/attachments/../connections.yaml", "host//connections.yaml", "host/connections.yaml/", "HOST/connections.yaml"])
def test_path_spellings_do_not_get_around_the_gate(home, form):
    _make(home, "host/connections.yaml")
    with use(ADMIN):
        with pytest.raises(ValueError):
            resolve_path(str(home) + "/" + form)


def test_an_attachments_symlink_to_host_is_refused(home):
    _make(home, "host/connections.yaml")
    (home / "host" / "attachments").symlink_to(home / "host" / "other", target_is_directory=True)
    (home / "host" / "other").mkdir()
    link = home / "host" / "attachments" / "connections.yaml"
    (home / "host" / "other" / "connections.yaml").write_text("x")
    with use(ADMIN):
        with pytest.raises(ValueError):
            resolve_path(str(link))


@pytest.mark.parametrize("rel,tool", [("memories/AGENT.md", "memory"), ("schedule/jobs.json", "schedule")])
def test_a_refused_write_names_the_tool_that_owns_the_area(home, rel, tool):
    p = _make(home, rel)
    with use(ADMIN):
        result = tools.execute("write_file", {"path": str(p), "content": "y"})
    assert result.ok is False
    assert f"`{tool}`" in result.error
    assert p.read_text() == "x"


def test_the_memory_tool_still_writes_agent_md(home):
    with use(ADMIN):
        result = tools.execute("memory", {"action": "add", "target": "AGENT.md", "content": "Your name is Clara"})
    assert result.ok, result.error
    assert "Clara" in (home / "memories" / "AGENT.md").read_text()


def test_the_member_fence_keeps_its_wider_list(home):
    member = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="member")
    p = _make(home, "mentions/alexandra.json")
    with use(member):
        with pytest.raises(ValueError, match="member"):
            resolve_path(str(p))
    with use(ADMIN):
        assert resolve_path(str(p)) == p.resolve()


def test_ordinary_workspace_files_are_untouched(home, ws):
    p = ws / "notes.md"
    p.write_text("n")
    with use(ADMIN):
        assert resolve_path(str(p), for_write=True) == p.resolve()
