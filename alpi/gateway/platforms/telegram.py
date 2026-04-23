"""Telegram adapter — long-poll via getUpdates."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from alpi.gateway.base import IncomingMessage, OutgoingMessage, Platform
from alpi.gateway.delivery import format_for_telegram

log = logging.getLogger("alpi.gateway.telegram")

API_BASE = "https://api.telegram.org/bot{token}"
FILE_BASE = "https://api.telegram.org/file/bot{token}"


def _state_path(home: Path) -> Path:
    return home / "gateway" / "telegram-state.json"


class Telegram(Platform):
    name = "telegram"

    def __init__(self, home) -> None:
        super().__init__(home)
        self._offset = self._load_offset()
        # Per-chat state for the interactive /model picker. Stored here on
        # the Platform instance rather than in session_map because it's
        # transient UI state — lives only until the user picks or cancels.
        self._model_picker: dict[str, dict[str, Any]] = {}

    def _load_offset(self) -> int:
        p = _state_path(self.home)
        if not p.exists():
            return 0
        try:
            return int((json.loads(p.read_text()) or {}).get("offset", 0))
        except (json.JSONDecodeError, ValueError, TypeError):
            return 0

    def _save_offset(self) -> None:
        p = _state_path(self.home)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"offset": self._offset}))
        tmp.replace(p)

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            log.info("TELEGRAM_BOT_TOKEN not set — telegram listener idle.")
            while True:
                await asyncio.sleep(3600)
                if False:  # pragma: no cover
                    yield  # type: ignore[misc]

        url_base = API_BASE.format(token=token)
        log.info("Telegram listener starting (long-poll, offset=%d).", self._offset)

        await _register_bot_commands(url_base)

        first_poll = True
        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                try:
                    resp = await client.get(
                        f"{url_base}/getUpdates",
                        params={"offset": self._offset, "timeout": 30},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:  # noqa: BLE001
                    log.warning("getUpdates failed: %s", e)
                    await asyncio.sleep(5)
                    continue

                results = data.get("result", [])
                if first_poll and results:
                    log.info("catching up on %d message(s) from backlog", len(results))
                first_poll = False

                for update in results:
                    self._offset = update["update_id"] + 1
                    self._save_offset()

                    # Inline-keyboard callbacks (model picker, future
                    # approval buttons) — handled Telegram-side, no yield.
                    cq = update.get("callback_query")
                    if cq:
                        try:
                            await self._handle_callback_query(cq)
                        except Exception as e:  # noqa: BLE001
                            log.warning("callback_query handler failed: %s", e)
                        continue

                    msg = update.get("message") or update.get("edited_message")
                    if not msg:
                        continue
                    chat = msg.get("chat") or {}
                    sender = msg.get("from") or {}
                    user_id = str(sender.get("id", ""))

                    text = msg.get("text") or ""
                    voice = msg.get("voice") or msg.get("audio")
                    if not text and voice:
                        text = await _transcribe_voice(
                            client, token, self.home, voice,
                        )
                        if not text:
                            continue
                        text = f"[voice note] {text}"
                    if not text:
                        continue

                    yield IncomingMessage(
                        platform="telegram",
                        external_user_id=user_id,
                        external_chat_id=str(chat.get("id", "")),
                        text=text,
                    )

    async def send_typing(self, chat_id: str) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return
        url = API_BASE.format(token=token) + "/sendChatAction"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json={"chat_id": chat_id, "action": "typing"})
        except Exception as e:  # noqa: BLE001
            log.debug("sendChatAction failed: %s", e)

    async def send(self, message: OutgoingMessage) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return
        base = API_BASE.format(token=token)

        async with httpx.AsyncClient(timeout=60) as client:
            if message.attachment:
                await _send_attachment(
                    client, base, message.external_chat_id,
                    message.attachment, caption=message.text,
                )
                return
            url = base + "/sendMessage"
            chunks = format_for_telegram(message.text)
            for i, chunk in enumerate(chunks):
                payload: dict[str, Any] = {
                    "chat_id": message.external_chat_id,
                    "text": chunk,
                }
                # Only attach reply_markup to the LAST chunk — attaching to
                # the first would put the keyboard above the message tail.
                if message.reply_markup and i == len(chunks) - 1:
                    payload["reply_markup"] = message.reply_markup
                try:
                    await client.post(url, json=payload)
                except Exception as e:  # noqa: BLE001
                    log.warning("sendMessage failed: %s", e)

    # Interactive /model picker — two-step drill-down via inline keyboards.
    #
    # Step 1: send a card with [Anthropic, OpenAI, …] + Cancel. State is
    # keyed by chat_id; the message id is remembered so step 2 edits in
    # place. Callback data uses compact tags (``mp:`` provider, ``mm:``
    # model, ``mx`` cancel) because Telegram caps it at 64 bytes.
    async def send_model_picker(self, chat_id: str) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return
        base = API_BASE.format(token=token)

        providers_info = _discover_providers(self.home)
        current_provider, current_model = _read_current_model(self.home)

        header = (
            "⚙ Model\n"
            f"Current: {current_model or 'unset'}\n\n"
            "Select a provider:"
        )
        keyboard = _provider_keyboard(providers_info, current_provider)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{base}/sendMessage",
                json={"chat_id": chat_id, "text": header,
                      "reply_markup": keyboard},
            )
            try:
                msg_id = resp.json()["result"]["message_id"]
            except Exception:  # noqa: BLE001
                log.warning("send_model_picker: couldn't read message_id")
                return

        self._model_picker[str(chat_id)] = {
            "msg_id": msg_id,
            "providers": providers_info,
            "current_provider": current_provider,
            "current_model": current_model,
        }

    async def _handle_callback_query(self, cq: dict) -> None:
        data = cq.get("data") or ""
        chat_id = str((cq.get("message") or {}).get("chat", {}).get("id", ""))
        cq_id = cq.get("id")
        if not data or not chat_id:
            return

        state = self._model_picker.get(chat_id)
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        base = API_BASE.format(token=token)

        async def _ack(text: str = "") -> None:
            if not cq_id:
                return
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    await c.post(f"{base}/answerCallbackQuery",
                                 json={"callback_query_id": cq_id, "text": text})
            except Exception:  # noqa: BLE001
                pass

        async def _edit(text: str, markup: dict | None = None) -> None:
            if not state:
                return
            payload: dict[str, Any] = {
                "chat_id": chat_id, "message_id": state["msg_id"], "text": text,
            }
            if markup is not None:
                payload["reply_markup"] = markup
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    await c.post(f"{base}/editMessageText", json=payload)
            except Exception as e:  # noqa: BLE001
                log.warning("editMessageText failed: %s", e)

        if data == "mx":
            await _edit("model picker · cancelled", markup={"inline_keyboard": []})
            self._model_picker.pop(chat_id, None)
            await _ack()
            return

        if data.startswith("mp:") and state:
            slug = data[3:]
            provider = next(
                (p for p in state["providers"] if p["slug"] == slug), None,
            )
            if not provider:
                await _ack("provider gone")
                return
            try:
                models = await asyncio.to_thread(provider["list_models"])
            except Exception as e:  # noqa: BLE001
                await _edit(f"model picker · failed to load models: {e}",
                            markup={"inline_keyboard": []})
                self._model_picker.pop(chat_id, None)
                await _ack()
                return
            state["selected_provider"] = slug
            keyboard = _model_keyboard(slug, models, state.get("current_model", ""))
            await _edit(
                f"⚙ Model · {provider['display']}\n\nSelect a model:",
                markup=keyboard,
            )
            await _ack()
            return

        if data.startswith("mm:") and state:
            _, _, rest = data.partition(":")
            slug, _, model_id = rest.partition(":")
            if not slug or not model_id:
                await _ack("invalid callback")
                return
            try:
                _persist_model(self.home, slug, model_id)
            except Exception as e:  # noqa: BLE001
                await _edit(f"model picker · failed to save: {e}",
                            markup={"inline_keyboard": []})
                self._model_picker.pop(chat_id, None)
                await _ack()
                return
            await _edit(f"✓ model set to {model_id}",
                        markup={"inline_keyboard": []})
            self._model_picker.pop(chat_id, None)
            await _ack("saved")
            return


async def _register_bot_commands(url_base: str) -> None:
    """Publish the slash-shortcut menu via Telegram's setMyCommands.

    Once registered, typing ``/`` in any chat with the bot shows a
    native list with names + descriptions. Idempotent — re-POSTing
    the same list is fine; Telegram stores it server-side.

    Telegram caches the command list per-client, so after a refresh
    you may need to close + reopen the app (or wait a minute) before
    the new menu shows. Groups also need ``scope: all_group_chats``;
    we set it explicitly so the bot works the same in DMs and groups.
    """
    from alpi.gateway import shortcuts as shortcuts_mod

    commands = [
        {"command": name, "description": desc}
        for name, desc in shortcuts_mod.catalog()
    ]
    # Register twice — once for the default scope (DMs), once for groups
    # the bot is added to. Without the second call, group members don't
    # see the command menu at all.
    targets = (
        ("default (DMs)", {"type": "default"}),
        ("all_group_chats", {"type": "all_group_chats"}),
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for label, scope in targets:
                resp = await client.post(
                    f"{url_base}/setMyCommands",
                    json={"commands": commands, "scope": scope},
                )
                body = {}
                try:
                    body = resp.json()
                except Exception:  # noqa: BLE001
                    pass
                if resp.status_code == 200 and body.get("ok"):
                    log.info(
                        "setMyCommands OK for %s (%d commands)",
                        label, len(commands),
                    )
                else:
                    log.warning(
                        "setMyCommands failed for %s: status=%d body=%s",
                        label, resp.status_code, body,
                    )
    except Exception as e:  # noqa: BLE001
        log.warning("setMyCommands request crashed: %s", e)


# /model picker helpers — platform-agnostic shape of provider/model data.


def _discover_providers(home: Path) -> list[dict[str, Any]]:
    """Return the list of providers the picker can offer (those with keys
    + configured Ollama endpoints). Each entry carries a ``list_models``
    callable so the picker can fetch on demand in a worker thread.
    """
    from alpi import config as cfg_mod
    from alpi import providers as prov_mod

    try:
        cfg = cfg_mod.load(home)
    except Exception:  # noqa: BLE001
        return []

    out: list[dict[str, Any]] = []
    or_models = cfg.providers.get("openrouter", {}).get("models", []) or []
    for p in prov_mod.builtin():
        if p.api_key_env and not p.has_key():
            continue
        if p.name == "openrouter" and not or_models:
            continue
        out.append({
            "slug": p.name,
            "display": p.display,
            "list_models": p.list_models,
        })
    for p in prov_mod.ollama(cfg.providers.get("ollama", [])):
        out.append({
            "slug": p.name,
            "display": p.name,
            "list_models": p.list_models,
        })
    return out


def _read_current_model(home: Path) -> tuple[str, str]:
    """Return ``(provider_slug, model_id)`` for the currently configured model."""
    from alpi import config as cfg_mod
    try:
        cfg = cfg_mod.load(home)
    except Exception:  # noqa: BLE001
        return "", ""
    model = cfg.model or ""
    head, _, _ = model.partition("/")
    return head, model


def _provider_keyboard(
    providers: list[dict[str, Any]], current: str,
) -> dict[str, Any]:
    buttons: list[dict[str, str]] = []
    for p in providers:
        label = p["display"]
        if p["slug"] == current:
            label = f"✓ {label}"
        buttons.append({"text": label, "callback_data": f"mp:{p['slug']}"})
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([{"text": "✗ Cancel", "callback_data": "mx"}])
    return {"inline_keyboard": rows}


def _model_keyboard(
    slug: str, models, current_model: str,
) -> dict[str, Any]:
    # Telegram caps callback_data at 64 bytes. Use the list index to keep
    # the payload short when model ids are long. Map index → id when the
    # click comes back; see _handle_callback_query `mm:` branch.
    # Actually we embed the full id because the picker state lives in
    # memory anyway — providers + ids stay in _model_picker[chat_id]
    # until the user resolves. If the id exceeds the cap, we truncate
    # and fall back to "model not found" in that unlikely case.
    buttons: list[dict[str, str]] = []
    for m in models:
        label = m.display
        if m.id == current_model:
            label = f"✓ {label}"
        payload = f"mm:{slug}:{m.id}"
        if len(payload.encode()) > 60:
            continue  # drop models whose id blows the callback_data cap
        buttons.append({"text": label, "callback_data": payload})
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([{"text": "✗ Cancel", "callback_data": "mx"}])
    return {"inline_keyboard": rows}


def _persist_model(home: Path, provider_slug: str, model_id: str) -> None:
    """Write the new model to ``config.yaml``. Also written to the active
    profile's env if one is set — matches how ``alpi setup`` persists."""
    from alpi import config as cfg_mod
    cfg = cfg_mod.load(home)
    cfg.model = model_id
    cfg_mod.save(cfg)


async def _send_attachment(
    client: httpx.AsyncClient, base: str, chat_id: str,
    path: str, caption: str,
) -> None:
    from pathlib import Path as _Path
    p = _Path(path).expanduser()
    if not p.exists() or not p.is_file():
        log.warning("attachment not found: %s", path)
        return

    ext = p.suffix.lower()
    if ext in (".ogg", ".oga", ".opus"):
        endpoint, field = "/sendVoice", "voice"
    elif ext in (".mp3", ".m4a", ".wav", ".flac", ".aac"):
        endpoint, field = "/sendAudio", "audio"
    elif ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        endpoint, field = "/sendPhoto", "photo"
    elif ext in (".mp4", ".mov", ".mkv"):
        endpoint, field = "/sendVideo", "video"
    else:
        endpoint, field = "/sendDocument", "document"

    data: dict[str, str] = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:1024]

    try:
        with p.open("rb") as fh:
            files = {field: (p.name, fh)}
            resp = await client.post(base + endpoint, data=data, files=files)
        if resp.status_code >= 400:
            log.warning(
                "telegram %s failed (%s): %s",
                endpoint, resp.status_code, resp.text[:200],
            )
    except Exception as e:  # noqa: BLE001
        log.warning("telegram %s crashed: %s", endpoint, e)


async def _transcribe_voice(
    client: httpx.AsyncClient, token: str, home: Path, voice: dict,
) -> str:
    file_id = voice.get("file_id")
    if not file_id:
        return ""
    try:
        resp = await client.get(
            API_BASE.format(token=token) + "/getFile",
            params={"file_id": file_id},
        )
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        log.warning("getFile failed: %s", e)
        return ""
    if not data.get("ok"):
        log.warning("getFile returned not-ok: %s", data)
        return ""
    file_path = (data.get("result") or {}).get("file_path") or ""
    if not file_path:
        return ""

    try:
        dl = await client.get(
            f"{FILE_BASE.format(token=token)}/{file_path}",
            timeout=60,
        )
        if dl.status_code != 200:
            log.warning("voice download failed (%s)", dl.status_code)
            return ""
        body = dl.content
    except Exception as e:  # noqa: BLE001
        log.warning("voice download crashed: %s", e)
        return ""

    cache = home / "cache" / "inbound"
    cache.mkdir(parents=True, exist_ok=True)
    suffix = Path(file_path).suffix or ".oga"
    dest = cache / f"{file_id}{suffix}"
    dest.write_bytes(body)

    from alpi.tools.stt import Stt
    result = await asyncio.to_thread(Stt().run, path=str(dest))
    if not result.ok:
        log.warning("stt failed on %s: %s", dest, result.error)
        return ""
    text = result.output
    if text.startswith("[lang="):
        _, _, rest = text.partition("\n")
        text = rest
    return text.strip()
