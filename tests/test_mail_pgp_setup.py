"""Wizard step that runs after IMAP/Gmail setup to optionally enable
PGP signing/encryption."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from alpi.mail import pgp_setup


_GPG_COLON_OUTPUT = (
    "sec:u:4096:1:ABCDEF1234567890:1700000000:::u:::scESC:::+:::23::0:\n"
    "fpr:::::::::AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:\n"
    "uid:u::::1700000000::ABC123::Alice <alice@example.com>::::::::::0:\n"
    "sec:u:4096:1:0123456789ABCDEF:1700000001:::u:::scESC:::+:::23::0:\n"
    "fpr:::::::::BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB:\n"
    "uid:u::::1700000001::DEF456::Bob <bob@example.com>::::::::::0:\n"
)


def test_list_secret_keys_parses_colon_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pgp_setup.shutil, "which", lambda _: "/usr/bin/gpg")

    class _R:
        returncode = 0
        stdout = _GPG_COLON_OUTPUT

    monkeypatch.setattr(pgp_setup.subprocess, "run", lambda *a, **k: _R())
    keys = pgp_setup._list_secret_keys()
    assert keys == [
        ("A" * 40, "Alice <alice@example.com>"),
        ("B" * 40, "Bob <bob@example.com>"),
    ]


def test_list_secret_keys_empty_when_gpg_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pgp_setup.shutil, "which", lambda _: None)
    assert pgp_setup._list_secret_keys() == []


def test_write_email_cfg_creates_block(tmp_path: Path) -> None:
    pgp_setup._write_email_cfg(tmp_path, "0xABC", True)
    data = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert data["email"] == {
        "signing_key": "0xABC",
        "encrypt_when_pubkey_available": True,
    }


def test_write_email_cfg_preserves_other_keys(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"model": "anthropic/claude-opus", "tui": {"accent": "#abc"}})
    )
    pgp_setup._write_email_cfg(tmp_path, "0xABC", False)
    data = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert data["model"] == "anthropic/claude-opus"
    assert data["tui"] == {"accent": "#abc"}
    assert data["email"]["signing_key"] == "0xABC"


def test_write_email_cfg_clears_block_on_empty(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"model": "x", "email": {"signing_key": "0xOLD"}})
    )
    pgp_setup._write_email_cfg(tmp_path, "", False)
    data = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert "email" not in data
    assert data["model"] == "x"


def test_maybe_offer_skips_silently_when_gpg_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pgp_setup.shutil, "which", lambda _: None)
    pgp_setup.maybe_offer(tmp_path)
    assert not (tmp_path / "config.yaml").exists()


def test_maybe_offer_skips_when_no_secret_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pgp_setup.shutil, "which", lambda _: "/usr/bin/gpg")

    class _R:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(pgp_setup.subprocess, "run", lambda *a, **k: _R())
    pgp_setup.maybe_offer(tmp_path)
    assert not (tmp_path / "config.yaml").exists()


def test_try_brew_install_skips_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pgp_setup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(pgp_setup.shutil, "which", lambda _: "/usr/bin/brew")
    assert pgp_setup._try_brew_install() is False


def test_try_brew_install_skips_when_no_brew(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pgp_setup.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(pgp_setup.shutil, "which", lambda _: None)
    assert pgp_setup._try_brew_install() is False


def test_try_brew_install_runs_brew_on_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pgp_setup.platform, "system", lambda: "Darwin")
    which_results = {"brew": "/opt/homebrew/bin/brew", "gpg": "/opt/homebrew/bin/gpg"}
    monkeypatch.setattr(pgp_setup.shutil, "which", lambda name: which_results.get(name))
    monkeypatch.setattr(pgp_setup.ui, "confirm", lambda *a, **k: True)

    calls: list[list[str]] = []

    class _R:
        returncode = 0
        stderr = ""

    def _run(cmd, **kwargs):
        calls.append(list(cmd))
        return _R()

    monkeypatch.setattr(pgp_setup.subprocess, "run", _run)
    assert pgp_setup._try_brew_install() is True
    assert calls == [["brew", "install", "gnupg"]]


def test_try_brew_install_user_declines(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pgp_setup.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(pgp_setup.shutil, "which", lambda _: "/opt/homebrew/bin/brew")
    monkeypatch.setattr(pgp_setup.ui, "confirm", lambda *a, **k: False)
    called = []
    monkeypatch.setattr(pgp_setup.subprocess, "run", lambda *a, **k: called.append(1))
    assert pgp_setup._try_brew_install() is False
    assert not called


def test_maybe_offer_swallows_unexpected_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_home):
        raise RuntimeError("simulated yaml corruption")
    monkeypatch.setattr(pgp_setup, "_maybe_offer", _boom)
    pgp_setup.maybe_offer(tmp_path)


def test_maybe_offer_no_pgp_does_not_touch_config_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "config.yaml").write_text("model: anthropic/claude-opus\n")
    monkeypatch.setattr(pgp_setup.shutil, "which", lambda _: None)
    monkeypatch.setattr(pgp_setup.platform, "system", lambda: "Linux")
    pgp_setup.maybe_offer(tmp_path)
    assert (tmp_path / "config.yaml").read_text() == "model: anthropic/claude-opus\n"


def test_missing_gpg_hint_mentions_distro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pgp_setup.platform, "system", lambda: "Linux")
    assert "apt" in pgp_setup._missing_gpg_hint()
    monkeypatch.setattr(pgp_setup.platform, "system", lambda: "Windows")
    assert "Gpg4win" in pgp_setup._missing_gpg_hint()
    monkeypatch.setattr(pgp_setup.platform, "system", lambda: "Darwin")
    assert "gnupg" in pgp_setup._missing_gpg_hint().lower()
