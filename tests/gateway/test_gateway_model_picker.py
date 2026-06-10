"""Telegram /model picker tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from alpi.gateway.platforms import telegram as tg


def test_provider_keyboard_marks_current() -> None:
    providers = [
        {"slug": "openai",    "display": "OpenAI",    "list_models": lambda: []},
        {"slug": "anthropic", "display": "Anthropic", "list_models": lambda: []},
    ]
    kb = tg._provider_keyboard(providers, current="anthropic")
    flat = [btn for row in kb["inline_keyboard"] for btn in row]
    labels = [b["text"] for b in flat]
    assert any("✓ Anthropic" in lbl for lbl in labels)
    assert any(lbl == "OpenAI" for lbl in labels)
    assert any(b["callback_data"] == "mx" for b in flat)


def test_provider_keyboard_two_per_row() -> None:
    providers = [
        {"slug": f"p{i}", "display": f"P{i}", "list_models": lambda: []}
        for i in range(5)
    ]
    kb = tg._provider_keyboard(providers, current="")
    provider_rows = kb["inline_keyboard"][:-1]  # last row is Cancel
    # 5 providers → 2, 2, 1 per row.
    assert [len(r) for r in provider_rows] == [2, 2, 1]


def test_model_keyboard_drops_over_long_callback_payloads() -> None:
    class _M:
        def __init__(self, mid: str):
            self.id = mid
            self.display = mid
    # One fits, one blows the 60-byte budget.
    models = [
        _M("gpt-4o"),
        _M("a" * 80),
    ]
    kb = tg._model_keyboard("openai", models, current_model="")
    rows = kb["inline_keyboard"][:-1]
    labels = [btn["text"] for row in rows for btn in row]
    assert "gpt-4o" in labels
    assert not any(len(lbl) > 60 for lbl in labels)


def test_model_keyboard_marks_current() -> None:
    # Compare the full id and force one provider-prefixed id.
    class _M2:
        def __init__(self, mid: str, disp: str):
            self.id = mid
            self.display = disp
    models2 = [_M2("openai/a", "a"), _M2("openai/b", "b")]
    kb2 = tg._model_keyboard("openai", models2, current_model="openai/b")
    labels = [
        btn["text"]
        for row in kb2["inline_keyboard"][:-1] for btn in row
    ]
    assert "✓ b" in labels
    assert "a" in labels


def test_persist_model_writes_config_yaml(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"model": "openai/gpt-old"})
    )
    tg._persist_model(tmp_path, "anthropic", "anthropic/claude-sonnet-4-6")
    saved = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert saved["model"] == "anthropic/claude-sonnet-4-6"


def test_read_current_model_is_empty_when_config_has_no_model(tmp_path: Path) -> None:
    """Empty config means empty model."""
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({}))
    provider, model = tg._read_current_model(tmp_path)
    assert provider == ""
    assert model == ""


def test_read_current_model_parses_slash(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"model": "openai/gpt-4o"})
    )
    provider, model = tg._read_current_model(tmp_path)
    assert provider == "openai"
    assert model == "openai/gpt-4o"


class _FakeAsyncClient:
    def __init__(self, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **kw):
        class _R:
            status_code = 200
        return _R()


def test_callback_query_enforces_sender_pin(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    monkeypatch.setattr(tg.httpx, "AsyncClient", _FakeAsyncClient)
    persisted: list[tuple[str, str]] = []
    monkeypatch.setattr(tg, "_persist_model",
                        lambda home, slug, mid: persisted.append((slug, mid)))

    inst = tg.Telegram(tmp_path)
    inst.env = {"TELEGRAM_ALLOWED_USER_IDS": "7", "TELEGRAM_BOT_TOKEN": "x"}
    inst._token = "x"
    inst._model_picker["-100"] = {"msg_id": 1}
    cq = {"id": "c1", "data": "mm:openai:gpt-4o", "message": {"chat": {"id": -100}}}

    # A non-allowlisted group member's button press is rejected — no model change.
    asyncio.run(inst._handle_callback_query({**cq, "from": {"id": 999}}))
    assert persisted == []

    # The allowlisted sender's press goes through (harness sanity).
    asyncio.run(inst._handle_callback_query({**cq, "from": {"id": 7}}))
    assert persisted == [("openai", "gpt-4o")]
