from __future__ import annotations

from pathlib import Path

import pytest

from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate
from alpi.host.connection_context import ConnectionContext, use
from alpi.tools import _state, get
from alpi.tools.workgroup_file import WorkgroupFileTool
import alpi.tools.workgroup_file as tool_mod


def _local_workgroup(home: Path):
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(home, name="files", hub_kp=kp, member_pubkeys=[])
    return wg


def test_workgroup_file_is_registered() -> None:
    assert get("workgroup_file") is WorkgroupFileTool


def test_description_explains_markers_and_avoids_inline_contents() -> None:
    description = WorkgroupFileTool.description
    assert "#file" in description
    assert "sha256" in description
    assert "rediscover older files" in description
    assert "Never paste file contents" in description


def test_list_reports_available_files(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    wg = _local_workgroup(home)
    source = tmp_path / "brief.md"
    source.write_text("# Hotel\n\nComplete brief.")
    monkeypatch.setattr(tool_mod, "get_home", lambda: home)
    sent = WorkgroupFileTool().run(
        action="send",
        wg_id=wg.meta.id,
        path=str(source),
        note="hotel briefing",
    )

    listed = WorkgroupFileTool().run(action="list", wg_id=wg.meta.id)

    digest = sent.output.split("sha256:", 1)[1].splitlines()[0]
    assert listed.ok
    assert "1 workgroup file:" in listed.output
    assert "brief.md" in listed.output
    assert f"sha256:{digest}" in listed.output
    assert "hotel briefing" in listed.output


def test_list_reports_empty_workgroup(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    wg = _local_workgroup(home)
    monkeypatch.setattr(tool_mod, "get_home", lambda: home)

    result = WorkgroupFileTool().run(action="list", wg_id=wg.meta.id)

    assert result.ok
    assert result.output == "no workgroup files"


def test_send_and_get_roundtrip_without_overwrite(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    wg = _local_workgroup(home)
    source = tmp_path / "report.bin"
    source.write_bytes(b"\x00\x01workgroup")
    destination = tmp_path / "download.bin"
    destination.write_bytes(b"keep")
    monkeypatch.setattr(tool_mod, "get_home", lambda: home)

    sent = WorkgroupFileTool().run(
        action="send",
        wg_id=wg.meta.id,
        path=str(source),
        note="binary deliverable",
    )
    digest = sent.output.split("sha256:", 1)[1].splitlines()[0]
    received = WorkgroupFileTool().run(
        action="get",
        wg_id=wg.meta.id,
        sha256=digest,
        dest=str(destination),
    )

    assert sent.ok
    assert "#file report.bin" in sent.output
    assert received.ok
    assert destination.read_bytes() == b"keep"
    assert (tmp_path / "download-1.bin").read_bytes() == source.read_bytes()


def test_send_accepts_exact_current_turn_staged_attachment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    wg = _local_workgroup(home)
    staged = home / "host" / "attachments" / "tmp" / "abc" / "scan.fit"
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"opaque input")
    monkeypatch.setattr(tool_mod, "get_home", lambda: home)
    monkeypatch.setattr("alpi.home.get_home", lambda: home)
    _state.set_turn_attachments([
        {"name": staged.name, "path": str(staged), "mime": "application/octet-stream"},
    ])

    with use(ConnectionContext(connection_id="c1", role="member")):
        result = WorkgroupFileTool().run(
            action="send",
            wg_id=wg.meta.id,
            path=str(staged),
        )

    assert result.ok
    assert "scan.fit" in result.output


def test_send_rejects_non_attachment_member_private_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    wg = _local_workgroup(home)
    private = home / "host" / "token"
    private.parent.mkdir()
    private.write_text("secret")
    monkeypatch.setattr(tool_mod, "get_home", lambda: home)
    monkeypatch.setattr("alpi.home.get_home", lambda: home)
    _state.reset_turn_attachments()

    with use(ConnectionContext(connection_id="c1", role="member")):
        result = WorkgroupFileTool().run(
            action="send",
            wg_id=wg.meta.id,
            path=str(private),
        )

    assert not result.ok
    assert "members cannot read" in result.error


def test_get_surfaces_missing_blob(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    wg = _local_workgroup(home)
    monkeypatch.setattr(tool_mod, "get_home", lambda: home)

    result = WorkgroupFileTool().run(
        action="get",
        wg_id=wg.meta.id,
        sha256="a" * 64,
        dest=str(tmp_path / "missing.bin"),
    )

    assert not result.ok
    assert "file-not-found" in result.error
    assert not (tmp_path / "missing.bin").exists()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"action": "send", "wg_id": "wg_x"}, "path required"),
        ({"action": "get", "wg_id": "wg_x"}, "sha256 required"),
        ({"action": "other", "wg_id": "wg_x"}, "action must be list, send, or get"),
    ],
)
def test_validates_action_arguments(kwargs, message) -> None:
    result = WorkgroupFileTool().run(**kwargs)

    assert not result.ok
    assert message in result.error
