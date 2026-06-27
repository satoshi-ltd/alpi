"""Optional PGP wizard step run after IMAP/Gmail credentials land.
Reads the local ``gpg`` keyring, lets the user pick a signing key,
and writes the result to the profile's ``config.yaml`` under
``email.signing_key`` / ``email.encrypt_when_pubkey_available``.

No-op when gpg is not installed or the keyring has no secret keys —
the inbound/outbound mail path stays plaintext.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from alpi import ui


def _list_secret_keys() -> list[tuple[str, str]]:
    if not shutil.which("gpg"):
        return []
    try:
        out = subprocess.run(
            ["gpg", "--list-secret-keys", "--with-colons", "--fingerprint"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    keys: list[tuple[str, str]] = []
    fp = ""
    for line in out.stdout.splitlines():
        parts = line.split(":")
        if not parts:
            continue
        if parts[0] == "sec":
            fp = ""
        elif parts[0] == "fpr" and not fp:
            fp = parts[9] if len(parts) > 9 else ""
        elif parts[0] == "uid" and fp and len(parts) > 9:
            keys.append((fp, parts[9]))
            fp = ""
    return keys


def _read_yaml(home: Path) -> dict[str, Any]:
    cfg_path = home / "config.yaml"
    if not cfg_path.exists():
        return {}
    return yaml.safe_load(cfg_path.read_text()) or {}


def _write_email_cfg(home: Path, signing_key: str, encrypt: bool) -> Path:
    cfg_path = home / "config.yaml"
    data = _read_yaml(home)
    if signing_key:
        data["email"] = {
            "signing_key": signing_key,
            "encrypt_when_pubkey_available": bool(encrypt),
        }
    else:
        data.pop("email", None)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return cfg_path


def _try_brew_install() -> bool:
    if platform.system() != "Darwin" or not shutil.which("brew"):
        return False
    if not ui.confirm("Install gnupg via brew now?", default=True):
        return False
    try:
        proc = subprocess.run(
            ["brew", "install", "gnupg"],
            capture_output=True, text=True, timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        ui.fail(f"brew install gnupg failed: {e}")
        return False
    if proc.returncode != 0:
        ui.fail(
            f"brew install gnupg failed (exit {proc.returncode}). "
            f"{(proc.stderr or '').splitlines()[-1] if proc.stderr else ''}"
        )
        return False
    return shutil.which("gpg") is not None


def _missing_gpg_hint() -> str:
    sysname = platform.system()
    if sysname == "Linux":
        return (
            "PGP: skipped — gpg not installed. "
            "Install with `sudo apt install gnupg` (or your distro's package "
            "manager) and re-run setup."
        )
    if sysname == "Windows":
        return (
            "PGP: skipped — gpg not installed. "
            "Install Gpg4win from https://gpg4win.org and re-run setup."
        )
    return (
        "PGP: skipped — gpg not installed. "
        "Install gnupg and re-run setup to enable signed/encrypted email."
    )


def maybe_offer(home: Path) -> None:
    try:
        _maybe_offer(home)
    except Exception as e:  # noqa: BLE001
        # Never break the email wizard because the PGP step misbehaved
        # — IMAP/Gmail credentials are already saved by this point.
        ui.warn(f"PGP step skipped: {e}")
        ui._console.print("")


def _maybe_offer(home: Path) -> None:
    current = (_read_yaml(home).get("email") or {})
    current_key = str(current.get("signing_key") or "")
    current_encrypt = bool(current.get("encrypt_when_pubkey_available"))

    if not shutil.which("gpg"):
        if not _try_brew_install():
            ui.dim(_missing_gpg_hint())
            ui._console.print("")
            return

    keys = _list_secret_keys()
    if not keys:
        ui.dim(
            "PGP: skipped — no secret keys in your gpg keyring. "
            "Run `gpg --full-generate-key` and re-run setup to enable."
        )
        ui._console.print("")
        return

    ui._console.print("")
    if not ui.confirm(
        "Enable PGP signing on outbound email?",
        default=bool(current_key),
    ):
        if current_key:
            _write_email_cfg(home, "", False)
            ui.ok("PGP signing disabled.")
        return

    items: list[Any] = [
        (uid, fp, fp[-16:]) for fp, uid in keys
    ]
    items.append(None)
    items.append(("Skip — keep plaintext for now", "", ""))
    selected = ui.menu(
        ui.crumb("setup", "email", "pgp"),
        items,
        subtitle="pick the secret key alpi will sign with",
        home=home,
        close="Skip",
    )
    if not selected:
        return

    encrypt = ui.confirm(
        "Also encrypt when the recipient's public key is available?",
        default=current_encrypt,
    )

    cfg_path = _write_email_cfg(home, selected, encrypt)
    ui.saved_and_wait(cfg_path)
