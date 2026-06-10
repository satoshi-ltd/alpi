"""``host.tools.list`` verb — introspect the agent tool registry."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import server as host_server
from alpi.host import tools as host_tools_mod


@pytest.fixture
def short_tmp():
    d = Path(tempfile.mkdtemp(prefix="alp-host-tools-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
async def test_tools_list_returns_registered_tools(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    srv = host_server.Server(home=home)
    host_tools_mod.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.tools.list",
        "params": {"profile": "default"},
    })
    tools = resp["result"]["tools"]
    assert isinstance(tools, list)
    assert len(tools) > 0

    by_name = {t["name"]: t for t in tools}
    for expected in ("read_file", "write_file", "terminal", "memory", "skill"):
        assert expected in by_name, f"missing tool {expected}"
        entry = by_name[expected]
        assert entry["description"]
        assert "parameters" in entry
        assert entry["parameters"]["type"] == "object"
        assert entry["category"], f"missing category for {expected}"

    assert by_name["read_file"]["category"] == "Filesystem"
    assert by_name["web_fetch"]["category"] == "Web"
    assert by_name["memory"]["category"] == "Memory"
    assert by_name["terminal"]["category"] == "System"
    assert by_name["search_workspace"]["category"] == "Workspace"
    assert by_name["recall_sessions"]["category"] == "Memory"
    assert by_name["workgroup_post"]["category"] == "Collab"
    assert by_name["notify"]["category"] == "Comms"


@pytest.mark.asyncio
async def test_every_builtin_tool_has_a_real_category(short_tmp: Path) -> None:
    """A tool rename silently rots the prefix map and the tool falls into "Other" — keep the fallback for genuinely unknown names but never for the builtin registry."""
    home = short_tmp / "h"
    home.mkdir()
    srv = host_server.Server(home=home)
    host_tools_mod.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.tools.list",
        "params": {"profile": "default"},
    })
    uncategorized = [
        t["name"] for t in resp["result"]["tools"] if t["category"] == "Other"
    ]
    assert not uncategorized, f"tools missing from _CATEGORIES: {uncategorized}"


@pytest.mark.asyncio
async def test_tools_list_filters_subaction_variants(short_tmp: Path) -> None:
    """Tool variants with a colon in the name (e.g. ``memory:add``) are
    sub-action shorthands the LLM never sees as separate tools; the UI
    should only list the parent."""
    home = short_tmp / "h"
    home.mkdir()
    srv = host_server.Server(home=home)
    host_tools_mod.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.tools.list",
        "params": {},
    })
    names = [t["name"] for t in resp["result"]["tools"]]
    for name in names:
        assert ":" not in name, f"sub-action variant leaked into list: {name}"


@pytest.mark.asyncio
async def test_tools_list_marks_denied_tools(short_tmp: Path, monkeypatch) -> None:
    """Tools listed in ``tools.deny`` of the profile config are returned with ``denied: true`` so the UI can mute / strike them — they are NOT removed (operator wants to see what's been switched off)."""
    from alpi import home as home_mod

    root = short_tmp / ".alpi"
    profile = "workhorse"
    phome = root / "profiles" / profile
    phome.mkdir(parents=True)
    (phome / "config.yaml").write_text(
        "model: openai/gpt-5.4-mini\n"
        "tools:\n"
        "  deny:\n"
        "    - terminal\n"
        "    - web_fetch\n"
    )
    monkeypatch.setattr(home_mod, "_ROOT", root)

    srv = host_server.Server(home=short_tmp / "h")
    (short_tmp / "h").mkdir()
    host_tools_mod.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.tools.list",
        "params": {"profile": profile},
    })
    by_name = {t["name"]: t for t in resp["result"]["tools"]}
    assert by_name["terminal"]["denied"] is True
    assert by_name["web_fetch"]["denied"] is True
    assert by_name["read_file"]["denied"] is False


@pytest.mark.asyncio
async def test_tools_list_default_when_no_profile_config(short_tmp: Path) -> None:
    """No config file = no deny filter; every tool is returned with ``denied: false``."""
    srv = host_server.Server(home=short_tmp / "h")
    (short_tmp / "h").mkdir()
    host_tools_mod.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.tools.list",
        "params": {"profile": "nonexistent"},
    })
    for t in resp["result"]["tools"]:
        assert t["denied"] is False
