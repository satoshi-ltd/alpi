"""Unit tests for ``alpi.updater``.

PyPI is mocked at the ``httpx.Client`` level so the suite stays
offline. The autouse ``_disable_update_check`` fixture in conftest
ensures importing alpi never spawns the background thread either.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alpi import updater


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the cache to a tmp dir so each test starts clean."""
    cache = tmp_path / "cache" / "update_check.json"
    monkeypatch.setattr(updater, "_cache_path", lambda: cache)
    return tmp_path


@pytest.fixture(autouse=True)
def _outside_a_container(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    monkeypatch.delenv("ALPI_DEPLOY_RUNTIME", raising=False)
    monkeypatch.setattr(updater, "_installer_memo", None)


def _write_cache(home: Path, latest: str, current: str,
                 checked_at: str | None = None) -> None:
    p = updater._cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "latest_version": latest,
        "current_version": current,
        "checked_at": checked_at or updater._utcnow_iso(),
    }))


# version comparison


def test_update_now_offline_returns_not_ok(fake_home: Path, monkeypatch) -> None:
    monkeypatch.setattr(updater, "_fetch_pypi_version", lambda: None)
    res = updater.update_now()
    assert res["ok"] is False and res["updated"] is False and res["reason"] == "offline"


def test_update_now_up_to_date(fake_home: Path, monkeypatch) -> None:
    monkeypatch.setattr(updater, "__version__", "0.9.5")
    monkeypatch.setattr(updater, "_fetch_pypi_version", lambda: "0.9.5")
    res = updater.update_now()
    assert res["ok"] is True and res["updated"] is False and res["reason"] == "up-to-date"


def test_update_now_source_install_is_manual(fake_home: Path, monkeypatch) -> None:
    monkeypatch.setattr(updater, "__version__", "0.9.4")
    monkeypatch.setattr(updater, "_fetch_pypi_version", lambda: "0.9.5")
    monkeypatch.setattr(updater, "_detect_installer", lambda: "source")
    res = updater.update_now()
    assert res["ok"] is False and res["updated"] is False
    assert res["reason"] == "manual" and res["installer"] == "source"


def test_update_now_runs_upgrade_and_reports_updated(fake_home: Path, monkeypatch) -> None:
    monkeypatch.setattr(updater, "__version__", "0.9.4")
    monkeypatch.setattr(updater, "_fetch_pypi_version", lambda: "0.9.5")
    monkeypatch.setattr(updater, "_detect_installer", lambda: "uv")
    ran = {}

    def fake_run(cmd, **kw):
        ran["cmd"] = cmd
        return MagicMock(returncode=0, stderr="")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    res = updater.update_now()
    assert res["ok"] is True and res["updated"] is True
    assert res["installer"] == "uv" and res["latest"] == "0.9.5"
    assert ran["cmd"] == ["uv", "tool", "upgrade", "alpi-agent"]


def test_update_now_failed_upgrade_returns_reason(fake_home: Path, monkeypatch) -> None:
    monkeypatch.setattr(updater, "__version__", "0.9.4")
    monkeypatch.setattr(updater, "_fetch_pypi_version", lambda: "0.9.5")
    monkeypatch.setattr(updater, "_detect_installer", lambda: "uv")
    monkeypatch.setattr(updater.subprocess, "run",
                        lambda cmd, **kw: MagicMock(returncode=1, stderr="boom"))
    res = updater.update_now()
    assert res["ok"] is False and res["updated"] is False and res["reason"] == "boom"


def test_is_newer_handles_double_digit_patches() -> None:
    """The classic gotcha: lexical sort puts 0.2.10 before 0.2.9."""
    assert updater._is_newer("0.2.10", "0.2.9") is True
    assert updater._is_newer("0.2.9", "0.2.10") is False


def test_is_newer_same_version() -> None:
    assert updater._is_newer("0.2.94", "0.2.94") is False


def test_is_newer_invalid_strings_return_false() -> None:
    """Bad PyPI payloads must under-report rather than badge."""
    assert updater._is_newer("not-a-version", "0.2.94") is False
    assert updater._is_newer("", "0.2.94") is False


# cache I/O


def test_load_cache_missing_returns_none(fake_home: Path) -> None:
    assert updater._load_cache() is None


def test_load_cache_corrupt_returns_none(fake_home: Path) -> None:
    p = updater._cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not valid json")
    assert updater._load_cache() is None


def test_load_cache_missing_fields_returns_none(fake_home: Path) -> None:
    p = updater._cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"checked_at": "2026-04-26T10:00:00Z"}))
    assert updater._load_cache() is None


def test_save_then_load_roundtrip(fake_home: Path) -> None:
    updater._save_cache("0.2.95", "0.2.94")
    cache = updater._load_cache()
    assert cache is not None
    assert cache["latest_version"] == "0.2.95"
    assert cache["current_version"] == "0.2.94"
    assert cache["checked_at"]


# TTL


def test_is_cache_fresh_within_ttl(fake_home: Path) -> None:
    cache = {
        "latest_version": "0.2.95", "current_version": "0.2.94",
        "checked_at": updater._utcnow_iso(),
    }
    assert updater._is_cache_fresh(cache) is True


def test_is_cache_fresh_past_ttl(fake_home: Path) -> None:
    old = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(hours=24)
    cache = {
        "latest_version": "0.2.95", "current_version": "0.2.94",
        "checked_at": old.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    assert updater._is_cache_fresh(cache) is False


def test_is_cache_fresh_missing_timestamp() -> None:
    assert updater._is_cache_fresh({"latest_version": "0.2.95"}) is False


# available_update


def test_available_update_returns_none_when_no_cache(
        fake_home: Path) -> None:
    assert updater.available_update() is None


def test_available_update_returns_version_when_newer(
        fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "__version__", "0.2.94")
    _write_cache(fake_home, latest="0.2.95", current="0.2.94")
    assert updater.available_update() == "0.2.95"


def test_available_update_returns_none_when_current(
        fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "__version__", "0.2.95")
    _write_cache(fake_home, latest="0.2.95", current="0.2.95")
    assert updater.available_update() is None


def test_available_update_returns_none_when_dev_ahead_of_pypi(
        fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dev install case: editable __version__ leads PyPI's number.
    The badge must NOT appear or the dev sees their own work as 'an
    update' to install over themselves."""
    monkeypatch.setattr(updater, "__version__", "0.3.0")
    _write_cache(fake_home, latest="0.2.94", current="0.3.0")
    assert updater.available_update() is None


# refresh_cache_if_stale


def test_refresh_cache_if_stale_skips_when_fresh(
        fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_cache(fake_home, latest="0.2.95", current="0.2.94")
    fake_fetch = MagicMock(return_value="9.9.9")
    monkeypatch.setattr(updater, "_fetch_pypi_version", fake_fetch)
    updater.refresh_cache_if_stale()
    fake_fetch.assert_not_called()


def test_refresh_cache_if_stale_writes_when_stale(
        fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(hours=24)
    _write_cache(
        fake_home, latest="0.2.94", current="0.2.94",
        checked_at=old.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    monkeypatch.setattr(updater, "_fetch_pypi_version",
                        lambda: "0.2.95")
    monkeypatch.setattr(updater, "__version__", "0.2.94")
    updater.refresh_cache_if_stale()
    cache = updater._load_cache()
    assert cache["latest_version"] == "0.2.95"
    assert cache["current_version"] == "0.2.94"


def test_refresh_cache_if_stale_silent_on_network_failure(
        fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Network failure must NOT corrupt the cache or raise."""
    monkeypatch.setattr(updater, "_fetch_pypi_version", lambda: None)
    updater.refresh_cache_if_stale()  # no exception
    assert updater._load_cache() is None


# trigger_background_check_if_enabled


def test_trigger_skipped_under_env_var(
        fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPI_SKIP_UPDATE_CHECK", "1")
    fake_thread = MagicMock()
    monkeypatch.setattr(updater.threading, "Thread", fake_thread)
    updater.trigger_background_check_if_enabled()
    fake_thread.assert_not_called()


def test_trigger_spawns_daemon_thread_when_enabled(
        fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_SKIP_UPDATE_CHECK", raising=False)
    started = []

    class _FakeThread:
        def __init__(self, **kw):
            started.append(kw)

        def start(self):
            started[-1]["started"] = True

    monkeypatch.setattr(updater.threading, "Thread", _FakeThread)
    updater.trigger_background_check_if_enabled()
    assert started and started[0]["daemon"] is True
    assert started[0]["target"] is updater.refresh_cache_if_stale


# _fetch_pypi_version


def test_fetch_pypi_returns_version_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_has_outbound", lambda: True)
    fake_response = MagicMock()
    fake_response.json.return_value = {"info": {"version": "0.2.95"}}
    fake_response.raise_for_status.return_value = None

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):  # noqa: ARG002
            return fake_response

    with patch.object(updater, "httpx") as fake_httpx:
        fake_httpx.Client = _FakeClient
        assert updater._fetch_pypi_version() == "0.2.95"


def test_fetch_pypi_returns_none_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "_has_outbound", lambda: True)
    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = RuntimeError("500")

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):  # noqa: ARG002
            return fake_response

    with patch.object(updater, "httpx") as fake_httpx:
        fake_httpx.Client = _FakeClient
        assert updater._fetch_pypi_version() is None


def test_fetch_pypi_returns_none_when_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(updater, "_has_outbound", lambda: False)
    called = {"httpx": False}

    class _BoomClient:
        def __init__(self, *a, **kw):
            called["httpx"] = True
            raise AssertionError("httpx must not be invoked when offline")

    with patch.object(updater, "httpx") as fake_httpx:
        fake_httpx.Client = _BoomClient
        assert updater._fetch_pypi_version() is None
    assert called["httpx"] is False


def test_fetch_pypi_uses_alpi_update_index_env(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ALPI_UPDATE_INDEX overrides the updater URL."""
    monkeypatch.setattr(updater, "_has_outbound", lambda: True)
    monkeypatch.setenv(
        "ALPI_UPDATE_INDEX",
        "https://test.pypi.org/pypi/alpi-agent/json",
    )
    seen_url: list[str] = []
    fake_response = MagicMock()
    fake_response.json.return_value = {"info": {"version": "0.2.95"}}
    fake_response.raise_for_status.return_value = None

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            seen_url.append(url)
            return fake_response

    with patch.object(updater, "httpx") as fake_httpx:
        fake_httpx.Client = _FakeClient
        updater._fetch_pypi_version()

    assert seen_url == ["https://test.pypi.org/pypi/alpi-agent/json"]


def test_has_outbound_uses_host_from_pypi_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ALPI_UPDATE_INDEX",
        "https://my.mirror.local:8443/pypi/alpi-agent/json",
    )
    seen: list[tuple[str, int]] = []

    class _OK:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_create_connection(addr, timeout):  # noqa: ARG001
        seen.append(addr)
        return _OK()

    monkeypatch.setattr(
        "alpi.updater.socket.create_connection", fake_create_connection,
    )
    assert updater._has_outbound() is True
    assert seen == [("my.mirror.local", 8443)]


def test_has_outbound_falls_back_to_443_for_https(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ALPI_UPDATE_INDEX",
        "https://test.pypi.org/pypi/alpi-agent/json",
    )
    seen: list[tuple[str, int]] = []

    class _OK:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(
        "alpi.updater.socket.create_connection",
        lambda addr, timeout: (seen.append(addr) or _OK()),
    )
    assert updater._has_outbound() is True
    assert seen == [("test.pypi.org", 443)]


def test_has_outbound_returns_false_when_connect_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(addr, timeout):  # noqa: ARG001
        raise OSError("offline")
    monkeypatch.setattr("alpi.updater.socket.create_connection", boom)
    assert updater._has_outbound() is False


# _detect_installer


def test_detect_installer_returns_source_when_no_managers(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater.shutil, "which", lambda name: None)
    assert updater._detect_installer() == "source"


def test_detect_installer_returns_uv_when_listed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater.shutil, "which",
                        lambda name: f"/fake/{name}" if name == "uv" else None)

    def fake_run(args, **kw):  # noqa: ARG001
        out = MagicMock()
        out.returncode = 0
        out.stdout = "alpi-agent v0.2.94\n"
        return out

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    assert updater._detect_installer() == "uv"


def test_detect_installer_returns_pipx_when_only_pipx(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        updater.shutil, "which",
        lambda name: f"/fake/{name}" if name in ("pipx",) else None,
    )

    def fake_run(args, **kw):  # noqa: ARG001
        out = MagicMock()
        out.returncode = 0
        out.stdout = "alpi-agent\n"
        return out

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    assert updater._detect_installer() == "pipx"


def test_detect_installer_returns_source_when_uv_lacks_alpi(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater.shutil, "which",
                        lambda name: f"/fake/{name}" if name == "uv" else None)

    def fake_run(args, **kw):  # noqa: ARG001
        out = MagicMock()
        out.returncode = 0
        out.stdout = "ruff v0.1.0\n"  # uv knows ruff but not alpi-agent
        return out

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    assert updater._detect_installer() == "source"


def test_detect_installer_names_docker_without_asking_a_package_manager(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.setattr(updater.shutil, "which", lambda name: pytest.fail("asked a package manager"))
    assert updater._detect_installer() == "docker"


def test_a_scheduled_turn_inside_docker_is_still_docker(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "cron")
    monkeypatch.setenv("ALPI_DEPLOY_RUNTIME", "docker")
    assert updater._detect_installer() == "docker"


@pytest.mark.parametrize(("kind", "expected"), [
    ("uv", True), ("pipx", True), ("docker", False), ("source", False),
])
def test_only_package_manager_installs_update_themselves(kind: str, expected: bool) -> None:
    assert updater.can_self_update(kind) is expected


def test_manual_hint_fills_in_the_version_for_docker_and_not_for_source() -> None:
    assert updater.manual_hint("docker", "0.16.18") == (
        "Set the image tag to 0.16.18 in docker-compose.yml, then docker compose up -d."
    )
    assert updater.manual_hint("source", "0.16.18") == "Run git pull and restart the daemon."


def test_install_kind_is_detected_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(updater, "_installer_memo", None)
    monkeypatch.setattr(updater, "_probe_installer", lambda: calls.append(1) or ("uv", True))
    assert updater.install_kind() == updater.install_kind() == "uv"
    assert calls == [1]


def test_update_now_in_docker_is_manual_and_runs_nothing(fake_home: Path, monkeypatch) -> None:
    monkeypatch.setattr(updater, "__version__", "0.9.4")
    monkeypatch.setattr(updater, "_fetch_pypi_version", lambda: "0.9.5")
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.setattr(updater.subprocess, "run", lambda *a, **k: pytest.fail("ran a command"))
    res = updater.update_now()
    assert res["reason"] == "manual" and res["installer"] == "docker"


@pytest.mark.parametrize(("kind", "needle"), [
    ("docker", "Set the image tag to 0.9.5 in docker-compose.yml"),
    ("source", "Run git pull and restart the daemon."),
])
def test_alpi_update_prints_the_shared_hint_when_it_cannot_update(
        fake_home: Path, monkeypatch, capsys, kind: str, needle: str) -> None:
    from alpi import ui

    printed = []
    monkeypatch.setattr(updater, "__version__", "0.9.4")
    monkeypatch.setattr(updater, "_fetch_pypi_version", lambda: "0.9.5")
    monkeypatch.setattr(updater, "_detect_installer", lambda: kind)
    monkeypatch.setattr(ui._console, "print", lambda *a, **k: printed.append(" ".join(map(str, a))))

    assert updater.do_update(check_only=False, yes=True) == 0
    assert any(needle in line for line in printed)


def test_a_package_manager_that_times_out_is_not_remembered_as_a_source_install(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater.shutil, "which", lambda name: f"/fake/{name}" if name == "uv" else None)

    def hang(args, **kw):  # noqa: ARG001
        raise updater.subprocess.TimeoutExpired(args, 10)

    monkeypatch.setattr(updater.subprocess, "run", hang)
    assert updater.install_kind() == "source"
    assert updater._installer_memo is None

    def answer(args, **kw):  # noqa: ARG001
        return MagicMock(returncode=0, stdout="alpi-agent v1\n")

    monkeypatch.setattr(updater.subprocess, "run", answer)
    assert updater.install_kind() == "uv"


def test_a_source_install_is_remembered_when_every_manager_answered(
        monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(updater.shutil, "which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        updater.subprocess, "run",
        lambda args, **kw: calls.append(args) or MagicMock(returncode=0, stdout="ruff v1\n"),
    )
    assert updater.install_kind() == updater.install_kind() == "source"
    assert len(calls) == 2


def test_alpi_update_check_prints_the_hint_when_it_cannot_update(
        fake_home: Path, monkeypatch) -> None:
    from alpi import ui

    printed = []
    monkeypatch.setattr(updater, "__version__", "0.9.4")
    monkeypatch.setattr(updater, "_fetch_pypi_version", lambda: "0.9.5")
    monkeypatch.setattr(updater, "_detect_installer", lambda: "docker")
    monkeypatch.setattr(ui._console, "print", lambda *a, **k: printed.append(" ".join(map(str, a))))

    assert updater.do_update(check_only=True, yes=False) == 0
    assert any("Set the image tag to 0.9.5" in line for line in printed)
    assert not any("without --check" in line for line in printed)
