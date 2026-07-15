import shutil
import tempfile
from pathlib import Path

import pytest

from alpi import home as home_mod
from alpi.host.connection_context import ConnectionContext, use
from alpi.tools._paths import resolve_path

MEMBER = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="member")

PRIVATE_AREA = (
    "host/connections.yaml",
    "alp/secrets/alp_key",
    "secrets/gmail_tokens/x.json",
    "gateway/telegram.token",
    "memories/MEMORY.md",
    "schedule/jobs.json",
    "sessions/other.json",
)
WRITE_ONLY_DENIED = ("alp/peers.yaml", "logs/ledger.json", "outputs/outputs.jsonl")


@pytest.fixture
def home(monkeypatch):
    base = Path(tempfile.mkdtemp(prefix="alp-cfgarea-", dir="/tmp"))
    d = base / ".alpi"
    d.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", d)
    try:
        yield d
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.parametrize("rel", PRIVATE_AREA)
def test_member_read_of_private_area_refused(home, rel):
    with use(MEMBER):
        with pytest.raises(ValueError, match="member"):
            resolve_path(str(home / rel), for_write=False)


@pytest.mark.parametrize("rel", PRIVATE_AREA + WRITE_ONLY_DENIED)
def test_member_write_into_private_area_refused(home, rel):
    with use(MEMBER):
        with pytest.raises(ValueError, match="member"):
            resolve_path(str(home / rel), for_write=True)


def test_member_may_read_alp_transcripts(home):
    t = home / "alp" / "workgroups" / "wg1" / "transcript.jsonl"
    with use(MEMBER):
        assert resolve_path(str(t), for_write=False) == t.resolve()
    with use(MEMBER):
        with pytest.raises(ValueError, match="member"):
            resolve_path(str(t), for_write=True)


def test_member_workspace_access_allowed(home):
    work = home.parent / "work" / "notes.txt"
    with use(MEMBER):
        assert resolve_path(str(work), for_write=True) == work.resolve()
        assert resolve_path(str(work), for_write=False) == work.resolve()


@pytest.mark.parametrize("rel", PRIVATE_AREA)
def test_admin_unrestricted(home, rel):
    assert resolve_path(str(home / rel), for_write=True) == (home / rel).resolve()
    assert resolve_path(str(home / rel), for_write=False) == (home / rel).resolve()


def test_email_download_attachment_is_treated_as_a_write(home):
    from alpi.tools import email as email_mod
    called = {"n": 0}

    class StubClient:
        def download_attachment(self, **kw):
            called["n"] += 1

    with use(MEMBER):
        with pytest.raises(ValueError, match="member"):
            email_mod._dispatch(StubClient(), "download_attachment", {
                "uid": "1", "attachment_name": "a.pdf",
                "dest_path": str(home / "alp" / "a.pdf"),
            })
    assert called["n"] == 0


def test_member_cross_profile_escalation_refused(home):
    other = home / "profiles" / "other" / "host" / "connections.yaml"
    with use(MEMBER):
        with pytest.raises(ValueError, match="member"):
            resolve_path(str(other), for_write=False)
        with pytest.raises(ValueError, match="member"):
            resolve_path(str(other), for_write=True)
