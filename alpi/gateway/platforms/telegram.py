"""Telegram adapter."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from alpi.gateway import breaker as _breaker
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
        self._token = self.env.get("TELEGRAM_BOT_TOKEN", "").strip() or None
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
        token = self._token
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
        last_error_class: str | None = None
        error_streak = 0
        last_streak_log = 0.0
        conflict_announced = False
        SUMMARY_INTERVAL_SEC = 300.0
        breaker = _breaker.for_home(self.home)
        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                if breaker.should_skip("telegram"):
                    await asyncio.sleep(30)
                    continue
                try:
                    resp = await client.get(
                        f"{url_base}/getUpdates",
                        params={"offset": self._offset, "timeout": 30},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:  # noqa: BLE001
                    error_class = type(e).__name__
                    is_conflict = "409" in str(e)
                    now = asyncio.get_running_loop().time()
                    if is_conflict:
                        # 409 means another process owns the long-poll — not a real
                        # upstream failure. Don't escalate the breaker.
                        if not conflict_announced:
                            log.warning(
                                "Telegram bot already polled by another process (409 Conflict). "
                                "Inbound paused; outbound still works. "
                                "Stop the other instance (other machine / container) or rotate the bot token to recover."
                            )
                            conflict_announced = True
                        await asyncio.sleep(60)
                        continue
                    if error_class != last_error_class:
                        log.warning("getUpdates failed: %s", e)
                        last_error_class = error_class
                        error_streak = 1
                        last_streak_log = now
                    else:
                        error_streak += 1
                        if now - last_streak_log >= SUMMARY_INTERVAL_SEC:
                            log.warning(
                                "getUpdates still failing (%s, %d repeats in last %.0fs)",
                                error_class, error_streak, now - last_streak_log,
                            )
                            error_streak = 0
                            last_streak_log = now
                    prev, curr = breaker.record_failure("telegram", str(e))
                    if prev != curr:
                        st = breaker.state_of("telegram")
                        _breaker.emit_state_event(
                            self.home, "telegram", prev, curr,
                            reason=str(e), disabled_until=st.disabled_until,
                        )
                    await asyncio.sleep(5)
                    continue
                last_error_class = None
                error_streak = 0
                if conflict_announced:
                    log.info("Telegram polling recovered (409 cleared).")
                    conflict_announced = False
                prev, curr = breaker.record_success("telegram")
                if prev != curr:
                    _breaker.emit_state_event(self.home, "telegram", prev, curr)

                results = data.get("result", [])
                if first_poll and results:
                    log.info("catching up on %d message(s) from backlog", len(results))
                first_poll = False

                for update in results:
                    self._offset = update["update_id"] + 1
                    self._save_offset()

                    # Callback buttons are handled in Telegram.
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
        token = self._token
        if not token:
            return
        url = API_BASE.format(token=token) + "/sendChatAction"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json={"chat_id": chat_id, "action": "typing"})
        except Exception as e:  # noqa: BLE001
            log.debug("sendChatAction failed: %s", e)

    async def send(self, message: OutgoingMessage) -> None:
        token = self._token
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
                is_last = i == len(chunks) - 1
                markup = message.reply_markup if is_last else None
                await _send_text_chunk(
                    client, url, message.external_chat_id, chunk, markup,
                )

    # Two-step inline /model picker.
    async def send_model_picker(self, chat_id: str) -> None:
        token = self._token
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
        token = self._token or ""
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


async def _send_text_chunk(
    client: httpx.AsyncClient, url: str, chat_id: str,
    text: str, reply_markup: dict | None,
) -> None:
    """Send one chunk as MarkdownV2, then plain text on parse errors."""
    from alpi.gateway.platforms._md2 import to_markdown_v2

    rendered = to_markdown_v2(text)
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": rendered,
        "parse_mode": "MarkdownV2",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        resp = await client.post(url, json=payload)
    except Exception as e:  # noqa: BLE001
        log.warning("sendMessage failed: %s", e)
        return
    if resp.status_code == 200:
        return

    # Retry plain text only on Markdown parse errors.
    body = {}
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        pass
    desc = (body.get("description") or "")
    if resp.status_code == 400 and "parse" in desc.lower():
        log.info("sendMessage: markdown parse failed (%s), retrying as plain", desc)
        fallback: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            fallback["reply_markup"] = reply_markup
        try:
            await client.post(url, json=fallback)
        except Exception as e:  # noqa: BLE001
            log.warning("sendMessage fallback failed: %s", e)
        return

    log.warning(
        "sendMessage: status=%d body=%s", resp.status_code, desc or body,
    )


async def _register_bot_commands(url_base: str) -> None:
    """Publish the slash-shortcut menu."""
    from alpi.gateway import shortcuts as shortcuts_mod

    commands = [
        {"command": name, "description": desc}
        for name, desc in shortcuts_mod.catalog()
    ]
    # Register for DMs and groups.
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


    # `/model` picker helpers.


def _discover_providers(home: Path) -> list[dict[str, Any]]:
    """Return providers the picker can offer."""
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
    """Return the current ``(provider_slug, model_id)``."""
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
    # Keep callback payloads short.
    buttons: list[dict[str, str]] = []
    for m in models:
        label = m.display
        if m.id == current_model:
            label = f"✓ {label}"
        payload = f"mm:{slug}:{m.id}"
        if len(payload.encode()) > 60:
            continue
        buttons.append({"text": label, "callback_data": payload})
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([{"text": "✗ Cancel", "callback_data": "mx"}])
    return {"inline_keyboard": rows}


def _persist_model(home: Path, provider_slug: str, model_id: str) -> None:
    """Write the selected model to `config.yaml`."""
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

    from alpi.gateway.platforms._md2 import to_markdown_v2

    data: dict[str, str] = {"chat_id": chat_id}
    if caption:
        data["caption"] = to_markdown_v2(caption[:1024])
        data["parse_mode"] = "MarkdownV2"

    try:
        with p.open("rb") as fh:
            files = {field: (p.name, fh)}
            resp = await client.post(base + endpoint, data=data, files=files)
        if resp.status_code == 400 and caption:
            try:
                desc = resp.json().get("description", "")
            except Exception:  # noqa: BLE001
                desc = ""
            if "parse" in desc.lower():
                log.info(
                    "telegram %s: markdown parse failed, retrying as plain",
                    endpoint,
                )
                data.pop("parse_mode", None)
                data["caption"] = caption[:1024]
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
