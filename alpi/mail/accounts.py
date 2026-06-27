"""Multi-account registry — config rows + per-account secrets/tokens.

One code path (used by host RPCs and the CLI wizard) for adding,
removing, listing and constructing email clients. Account identity is a
slug of the address; IMAP passwords live in ``.env`` under
``EMAIL__<ID>__PASSWORD``; Gmail tokens live at
``secrets/gmail_tokens/<id>.json``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from alpi import config as cfg_mod

_IMAP_ALLOWED_KEYS = (
    "type", "address", "imap_host", "imap_port", "smtp_host", "smtp_port",
)
_GMAIL_ALLOWED_KEYS = ("type", "address")

_SLUG_RE = re.compile(r"[^a-z0-9]+")
# Account ids must be slug-shaped — safe as a path segment + env-key fragment; anything else is rejected.
_ID_RE = re.compile(r"^[a-z0-9_]+$")


def slug(address: str) -> str:
    return _SLUG_RE.sub("_", (address or "").lower()).strip("_")


def valid_id(account_id: str) -> bool:
    return bool(account_id) and _ID_RE.match(account_id) is not None


def password_env_key(account_id: str) -> str:
    return f"EMAIL__{account_id.upper()}__PASSWORD"


def gmail_token_path(home: Path, account_id: str) -> Path:
    if not valid_id(account_id):
        raise ValueError(f"invalid account id {account_id!r}")
    return home / "secrets" / "gmail_tokens" / f"{account_id}.json"


def _accounts(home: Path) -> dict[str, dict[str, Any]]:
    cfg = cfg_mod.load(home)
    raw = (cfg.email or {}).get("accounts") or {}
    return {
        str(k): dict(v) for k, v in raw.items()
        if isinstance(v, dict) and valid_id(str(k))
    }


def _read_env(home: Path) -> dict[str, str]:
    from alpi.home import read_profile_env
    return read_profile_env(home)


def _configured(home: Path, account_id: str, account: dict[str, Any], env: dict[str, str]) -> bool:
    if account.get("type") == "gmail":
        return gmail_token_path(home, account_id).exists()
    return bool(env.get(password_env_key(account_id)))


def list_accounts(home: Path) -> list[dict[str, Any]]:
    env = _read_env(home)
    out = []
    for account_id, account in _accounts(home).items():
        out.append({
            "id": account_id,
            "type": str(account.get("type") or "imap"),
            "address": str(account.get("address") or ""),
            "configured": _configured(home, account_id, account, env),
        })
    out.sort(key=lambda r: r["id"])
    return out


def get_account(home: Path, account_id: str) -> dict[str, Any] | None:
    if not valid_id(account_id):
        return None
    account = _accounts(home).get(account_id)
    if account is None:
        return None
    return {"id": account_id, **account}


def client_for(home: Path, account_id: str):
    from alpi.mail.gmail import GmailClient, GmailError
    from alpi.mail.imap import ImapClient, ImapError

    if not valid_id(account_id):
        raise ImapError(f"invalid email account id {account_id!r}")
    account = _accounts(home).get(account_id)
    if account is None:
        raise ImapError(f"unknown email account {account_id!r}")
    if account.get("type") == "gmail":
        return GmailClient(home, account_id)
    password = _read_env(home).get(password_env_key(account_id), "")
    if not password:
        raise ImapError(
            f"IMAP password missing for {account_id!r} — set "
            f"{password_env_key(account_id)} in ~/.alpi/.env"
        )
    return ImapClient.from_account(account, password)


def add_imap(
    home: Path,
    *,
    address: str,
    password: str,
    imap_host: str,
    smtp_host: str,
    imap_port: int = 993,
    smtp_port: int = 587,
) -> str:
    from alpi.model_selector import _append_env

    account_id = slug(address)
    if not account_id:
        raise ValueError("address does not slugify to a valid id")
    cfg = cfg_mod.load(home)
    accounts = dict((cfg.email or {}).get("accounts") or {})
    _reject_collision(accounts, account_id, address, "imap")
    accounts[account_id] = {
        "type": "imap",
        "address": address,
        "imap_host": imap_host,
        "imap_port": int(imap_port),
        "smtp_host": smtp_host,
        "smtp_port": int(smtp_port),
    }
    cfg.email = {"accounts": accounts}
    cfg_mod.save(cfg)
    # Empty password on an update preserves the stored one (the editor sends "" for "unchanged").
    if password:
        _append_env(cfg.env_path, password_env_key(account_id), password)
    return account_id


def add_gmail(home: Path, *, address: str) -> str:
    account_id = slug(address)
    if not account_id:
        raise ValueError("address does not slugify to a valid id")
    cfg = cfg_mod.load(home)
    accounts = dict((cfg.email or {}).get("accounts") or {})
    _reject_collision(accounts, account_id, address, "gmail")
    accounts[account_id] = {"type": "gmail", "address": address}
    cfg.email = {"accounts": accounts}
    cfg_mod.save(cfg)
    return account_id


def _reject_collision(accounts: dict, account_id: str, address: str, type_: str) -> None:
    # Distinct addresses can slug to one id (john.doe@ vs john-doe@); same address+type is fine (reauth), anything else would clobber.
    existing = accounts.get(account_id)
    if not isinstance(existing, dict):
        return
    if (str(existing.get("address") or "").lower() != address.lower()
            or existing.get("type") != type_):
        raise ValueError(
            f"account id {account_id!r} already used by "
            f"{existing.get('address')!r} ({existing.get('type')}) — "
            "this address collides with it; remove the other first"
        )


def remove_account(home: Path, account_id: str) -> bool:
    from alpi.model_selector import _remove_env_key

    if not valid_id(account_id):
        return False
    cfg = cfg_mod.load(home)
    accounts = dict((cfg.email or {}).get("accounts") or {})
    account = accounts.pop(account_id, None)
    cfg.email = {"accounts": accounts}
    cfg_mod.save(cfg)
    _remove_env_key(cfg.env_path, password_env_key(account_id))
    token = gmail_token_path(home, account_id)
    if token.exists():
        try:
            token.unlink()
        except OSError:
            pass
    return account is not None
