from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path


CAP = 20

# Never trust a remote peer to feed sane data into a path, even though ``mention.parse`` constrains ids.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_CONVERSATION_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class ThreadTurn:
    at: float
    user: str
    assistant: str
    host_context: str = ""


@dataclass
class Thread:
    sender: str
    turns: list[ThreadTurn] = field(default_factory=list)


def conversation_from_params(params: dict | None) -> str | None:
    # None = caller predates conversation identities (legacy per-sender thread); "" = relayed call whose conversation cannot be established (no history at all).
    if not isinstance(params, dict) or "conversation" not in params:
        return None
    raw = params.get("conversation")
    if isinstance(raw, str) and _CONVERSATION_RE.match(raw):
        return raw
    return ""


def history_kind(conversation: str | None) -> str:
    if conversation is None:
        return "peer"
    return "conversation" if conversation else "none"


def _path(home: Path, sender: str, conversation: str | None = None) -> Path | None:
    if not _SAFE_ID.match(sender):
        return None
    if conversation is None:
        return home / "mentions" / f"{sender}.json"
    if not _CONVERSATION_RE.match(conversation):
        return None
    return home / "mentions" / f"{sender}@{conversation}.json"


def load(home: Path, sender: str, conversation: str | None = None) -> Thread:
    p = _path(home, sender, conversation)
    if p is None or not p.exists():
        return Thread(sender=sender)
    try:
        data = json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return Thread(sender=sender)
    turns = [
        ThreadTurn(
            at=float(t.get("at", 0.0)),
            user=str(t.get("user", "")),
            assistant=str(t.get("assistant", "")),
            host_context=str(t.get("host_context", "") or ""),
        )
        for t in (data.get("turns") or [])
    ]
    return Thread(sender=sender, turns=turns)


def append(
    home: Path, sender: str, user: str, assistant: str, host_context: str = "",
    conversation: str | None = None,
) -> None:
    p = _path(home, sender, conversation)
    if p is None:
        return
    from alpi.session import HOST_CONTEXT_CAP
    thread = load(home, sender, conversation)
    thread.turns.append(ThreadTurn(
        at=time.time(), user=user, assistant=assistant,
        host_context=host_context[:HOST_CONTEXT_CAP],
    ))
    if len(thread.turns) > CAP:
        thread.turns = thread.turns[-CAP:]
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sender": sender,
        **({"conversation": conversation} if conversation else {}),
        "turns": [
            {
                "at": t.at, "user": t.user, "assistant": t.assistant,
                **({"host_context": t.host_context} if t.host_context else {}),
            }
            for t in thread.turns
        ],
    }
    p.write_text(json.dumps(payload, indent=2))


def hydrate(messages: list[dict], thread: Thread) -> None:
    if not thread.turns:
        return
    messages.append({
        "role": "system",
        "content": (
            f"Prior @-mention turns from {thread.sender!r} below are "
            "conversational context, not fact source — re-read memory "
            "before answering memory-driven questions; memory wins on "
            "conflict."
        ),
    })
    from alpi.session import with_host_context
    for t in thread.turns:
        if t.user:
            # Byte-stable replay of the provider-visible user content, suffix included.
            messages.append({
                "role": "user",
                "content": with_host_context(t.user, t.host_context),
            })
        if t.assistant:
            messages.append({"role": "assistant", "content": t.assistant})
