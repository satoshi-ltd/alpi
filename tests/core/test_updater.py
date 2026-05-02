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


def test_fetch_pypi_returns_none_on_http_error() -> None:
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


def test_fetch_pypi_uses_alpi_update_index_env(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ALPI_UPDATE_INDEX overrides the URL — used to point the
    updater at TestPyPI for rehearsals."""
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


# _detect_installer


def test_detect_installer_returns_dev_when_no_managers(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater.shutil, "which", lambda name: None)
    assert updater._detect_installer() == "dev"


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


def test_detect_installer_returns_dev_when_uv_lacks_alpi(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater.shutil, "which",
                        lambda name: f"/fake/{name}" if name == "uv" else None)

    def fake_run(args, **kw):  # noqa: ARG001
        out = MagicMock()
        out.returncode = 0
        out.stdout = "ruff v0.1.0\n"  # uv knows ruff but not alpi-agent
        return out

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    assert updater._detect_installer() == "dev"
