"""Tests for home.get_home / profile resolution."""

from __future__ import annotations

from pathlib import Path

from alpi import home


def test_default_is_home_alpi(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    assert home.get_home() == Path.home() / ".alpi"


def test_alpi_home_env_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    assert home.get_home() == tmp_path


def test_alpi_root_strips_profile_suffix(monkeypatch, tmp_path: Path) -> None:
    # Daemon dispatch sets ALPI_HOME to the profile dir. alpi_root() must return the real root so peer scans see siblings.
    root = tmp_path / ".alpi"
    profile = root / "profiles" / "vera"
    profile.mkdir(parents=True)
    monkeypatch.setenv("ALPI_HOME", str(profile))
    assert home.alpi_root() == root


def test_alpi_root_passthrough_when_not_profile(monkeypatch, tmp_path: Path) -> None:
    # Relocated installs (containers, custom roots) still work.
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    assert home.alpi_root() == tmp_path


def test_named_profile_goes_to_subdir(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    assert home.get_home("work") == Path.home() / ".alpi" / "profiles" / "work"


def test_ensure_home_creates_subtree(tmp_path: Path) -> None:
    home.ensure_home(tmp_path)
    for sub in ("memories", "sessions", "skills", "recipes", "schedule/output", "logs"):
        assert (tmp_path / sub).is_dir()


def test_alpi_profile_env_resolves(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.setenv("ALPI_PROFILE", "work")
    assert home.get_home() == Path.home() / ".alpi" / "profiles" / "work"


def test_explicit_flag_beats_env(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.setenv("ALPI_PROFILE", "work")
    # Explicit argument wins.
    assert home.get_home("personal") == Path.home() / ".alpi" / "profiles" / "personal"


def test_get_home_ignores_unknown_files_at_root(tmp_path: Path, monkeypatch) -> None:
    # Nothing on disk should influence resolution — only env + argument.
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    (tmp_path / "some-random-marker").write_text("x")
    assert home.get_home() == tmp_path


# Active-home contextvar for concurrent daemon turns.


def test_active_home_overrides_env(monkeypatch, tmp_path: Path) -> None:
    """Bound context beats env vars."""
    monkeypatch.setenv("ALPI_HOME", "/from/env")
    monkeypatch.setenv("ALPI_PROFILE", "from-env")
    token = home.set_active_home(tmp_path)
    try:
        assert home.get_home() == tmp_path
    finally:
        home.reset_active_home(token)
    # After reset, env resolution takes over again.
    assert home.get_home() == Path("/from/env")


def test_active_home_isolated_per_thread(tmp_path: Path, monkeypatch) -> None:
    """ContextVar isolation keeps concurrent turns on their own home."""
    import threading

    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    a_home = tmp_path / "a"
    b_home = tmp_path / "b"
    a_home.mkdir()
    b_home.mkdir()

    # Barrier makes both threads set their context before either reads.
    barrier = threading.Barrier(2)
    seen: dict[str, Path] = {}

    def worker(name: str, h: Path) -> None:
        token = home.set_active_home(h)
        barrier.wait(timeout=2)
        seen[name] = home.get_home()
        home.reset_active_home(token)

    t1 = threading.Thread(target=worker, args=("a", a_home))
    t2 = threading.Thread(target=worker, args=("b", b_home))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert seen == {"a": a_home, "b": b_home}
