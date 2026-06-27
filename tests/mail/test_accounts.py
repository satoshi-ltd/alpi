"""Multi-account registry — slug, add/list/remove, per-account paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.mail import accounts as accounts_mod
from alpi.mail.gmail import GmailClient
from alpi.mail.imap import ImapClient, ImapError


@pytest.mark.parametrize(
    "address,expected",
    [
        ("Me@Work.com", "me_work_com"),
        ("me@gmail.com", "me_gmail_com"),
        ("a.b+tag@sub.example.co", "a_b_tag_sub_example_co"),
        ("__weird__@x.com__", "weird_x_com"),
        ("UPPER@CASE.COM", "upper_case_com"),
    ],
)
def test_slug(address: str, expected: str) -> None:
    assert accounts_mod.slug(address) == expected


def test_password_env_key() -> None:
    assert accounts_mod.password_env_key("me_work_com") == "EMAIL__ME_WORK_COM__PASSWORD"


def test_gmail_token_path(tmp_path: Path) -> None:
    p = accounts_mod.gmail_token_path(tmp_path, "me_gmail_com")
    assert p == tmp_path / "secrets" / "gmail_tokens" / "me_gmail_com.json"


def test_add_imap_then_list_then_remove(tmp_path: Path) -> None:
    account_id = accounts_mod.add_imap(
        tmp_path,
        address="Me@Work.com",
        password="app-pw",
        imap_host="imap.work.com",
        smtp_host="smtp.work.com",
        imap_port=993,
        smtp_port=587,
    )
    assert account_id == "me_work_com"

    rows = accounts_mod.list_accounts(tmp_path)
    assert rows == [{
        "id": "me_work_com", "type": "imap",
        "address": "Me@Work.com", "configured": True,
    }]

    env_key = accounts_mod.password_env_key(account_id)
    assert f"{env_key}=app-pw" in (tmp_path / ".env").read_text()

    account = accounts_mod.get_account(tmp_path, account_id)
    assert account["imap_host"] == "imap.work.com"
    assert account["smtp_port"] == 587

    client = accounts_mod.client_for(tmp_path, account_id)
    assert isinstance(client, ImapClient)
    assert client.address == "Me@Work.com"
    assert client.password == "app-pw"

    assert accounts_mod.remove_account(tmp_path, account_id) is True
    assert accounts_mod.list_accounts(tmp_path) == []
    assert env_key not in (tmp_path / ".env").read_text()


def test_imap_not_configured_until_password_present(tmp_path: Path) -> None:
    account_id = accounts_mod.add_imap(
        tmp_path, address="me@x.com", password="pw",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
    accounts_mod.remove_account(tmp_path, account_id)
    accounts_mod.add_imap(
        tmp_path, address="me@x.com", password="",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
    rows = accounts_mod.list_accounts(tmp_path)
    assert rows[0]["configured"] is False
    with pytest.raises(ImapError):
        accounts_mod.client_for(tmp_path, account_id)


def test_gmail_account_uses_per_account_token(tmp_path: Path) -> None:
    account_id = accounts_mod.add_gmail(tmp_path, address="me@gmail.com")
    assert account_id == "me_gmail_com"

    rows = accounts_mod.list_accounts(tmp_path)
    assert rows[0]["configured"] is False  # no token yet

    p = accounts_mod.gmail_token_path(tmp_path, account_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}")

    rows = accounts_mod.list_accounts(tmp_path)
    assert rows[0]["configured"] is True

    client = accounts_mod.client_for(tmp_path, account_id)
    assert isinstance(client, GmailClient)
    assert client.account_id == account_id

    accounts_mod.remove_account(tmp_path, account_id)
    assert not p.exists()


def test_valid_id() -> None:
    assert accounts_mod.valid_id("me_work_com")
    assert accounts_mod.valid_id("a1_2")
    for bad in ("", "../x", "x/y", "x\\y", ".hidden", "Me", "a-b", "a.b", "a b"):
        assert not accounts_mod.valid_id(bad), bad


@pytest.mark.parametrize("bad", ["../x", "x/y", "x\\y", ".hidden", "", "UP", "a-b"])
def test_invalid_id_rejected_everywhere(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        accounts_mod.gmail_token_path(tmp_path, bad)
    assert accounts_mod.get_account(tmp_path, bad) is None
    assert accounts_mod.remove_account(tmp_path, bad) is False
    with pytest.raises(ImapError):
        accounts_mod.client_for(tmp_path, bad)


def test_remove_invalid_id_deletes_nothing_outside_token_dir(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets"
    secrets.mkdir(parents=True)
    sentinel = secrets / "keep.json"
    sentinel.write_text("{}")
    assert accounts_mod.remove_account(tmp_path, "../keep") is False
    assert accounts_mod.remove_account(tmp_path, "gmail_tokens/../keep") is False
    assert sentinel.exists()


def test_slug_collision_rejects_distinct_address_allows_reauth(tmp_path: Path) -> None:
    accounts_mod.add_imap(
        tmp_path, address="john.doe@example.com", password="a",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
    # john-doe@ slugs to the same id — must not silently clobber john.doe@.
    with pytest.raises(ValueError):
        accounts_mod.add_imap(
            tmp_path, address="john-doe@example.com", password="b",
            imap_host="imap.x.com", smtp_host="smtp.x.com",
        )
    # Re-adding the exact same address is fine (reauth / update).
    accounts_mod.add_imap(
        tmp_path, address="john.doe@example.com", password="c",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
    rows = accounts_mod.list_accounts(tmp_path)
    assert len(rows) == 1 and rows[0]["address"] == "john.doe@example.com"


def test_slug_collision_rejected_across_types(tmp_path: Path) -> None:
    accounts_mod.add_imap(
        tmp_path, address="me@x.com", password="a",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
    with pytest.raises(ValueError):
        accounts_mod.add_gmail(tmp_path, address="me@x.com")


def test_add_imap_empty_password_preserves_existing(tmp_path: Path) -> None:
    accounts_mod.add_imap(
        tmp_path, address="me@x.com", password="orig-pw",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
    # Edit the same account with empty password + changed host — password preserved.
    accounts_mod.add_imap(
        tmp_path, address="me@x.com", password="",
        imap_host="imap2.x.com", smtp_host="smtp.x.com",
    )
    env = accounts_mod._read_env(tmp_path)
    assert env[accounts_mod.password_env_key("me_x_com")] == "orig-pw"
    acct = accounts_mod.get_account(tmp_path, "me_x_com")
    assert acct["imap_host"] == "imap2.x.com"
    assert accounts_mod.list_accounts(tmp_path)[0]["configured"] is True


def test_two_accounts_isolated(tmp_path: Path) -> None:
    accounts_mod.add_imap(
        tmp_path, address="work@x.com", password="w",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
    accounts_mod.add_imap(
        tmp_path, address="home@y.com", password="h",
        imap_host="imap.y.com", smtp_host="smtp.y.com",
    )
    ids = {r["id"] for r in accounts_mod.list_accounts(tmp_path)}
    assert ids == {"work_x_com", "home_y_com"}
    work = accounts_mod.client_for(tmp_path, "work_x_com")
    home = accounts_mod.client_for(tmp_path, "home_y_com")
    assert work.password == "w"
    assert home.password == "h"
