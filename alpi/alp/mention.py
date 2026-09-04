"""``@peer rest…`` shortcut parsing + execution.

The ``@peer`` gesture is typed from a chat surface — the TUI
(``alpi/tui/app.py``) or the desktop/mobile apps over the host plane —
and routes the rest of the message to the peer without firing the
local LLM.

This module is the shared entry point so the semantics match: same parsing
rules, same resolution rules, same error shapes. The ``peer`` tool
(``alpi/tools/peer.py``) uses the same executor so LLM-invoked
calls and direct ``@``-mentions hit the same code path.

Detection rules (relaxed in v0.2.96 as ALP.3.1):

- The ``@`` may appear anywhere in the text, but it must be
  preceded by whitespace or be at the very start. That single
  boundary keeps email addresses (``hello@soyjavi.com``) from
  ever matching.
- The peer-id token after ``@`` is ``[A-Za-z0-9_-]+``.
- A ``home`` Path may be passed; when given, the parser also
  requires the matched id to resolve to a pinned peer. That filters
  false positives like ``@property`` or ``@deprecated`` in code
  snippets — they look syntactically right but aren't peers, so the
  caller falls through to the LLM instead of trying to route an
  ``@property`` mention.
- The "prompt" is the original text with the ``@<peer>`` token (and
  its boundary whitespace) removed. ``"hey @alice can you check?"``
  yields ``prompt="hey can you check?"``. A bare mention with no
  surrounding text yields ``None``.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from pathlib import Path

from alpi import config as cfg_mod
from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp.keys import Keypair, load_or_generate


# Boundary ``(?:^|\s)`` excludes ``email@example.com``; trailing
# ``\b`` keeps ``@alice,`` from greedily eating the comma into the id.
_MENTION_RE = re.compile(r"(?:^|\s)@([A-Za-z0-9_-]+)\b")


@dataclass
class Mention:
    peer_id: str
    prompt: str


@dataclass
class Result:
    ok: bool
    reply: str = ""
    error: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    transient: bool = False


def _link_timeouts(
    home: Path,
    idle_override: float | None,
    max_duration_override: float | None,
) -> tuple[float, float]:
    defaults = cfg_mod.DEFAULT_CONFIG["alp"]
    alp = cfg_mod.load(home).alp

    def _value(key: str, override: float | None) -> float:
        raw = override if override is not None else alp.get(key, defaults[key])
        try:
            value = float(raw)
            return value if value >= 0 else float(defaults[key])
        except (TypeError, ValueError):
            return float(defaults[key])

    return (
        _value("link_idle_timeout_s", idle_override),
        _value("link_max_duration_s", max_duration_override),
    )


async def _cancel(
    home: Path,
    peer: peers_mod.Peer,
    sender: Keypair,
    session_id: str,
) -> bool:
    params = {"session_id": session_id} if session_id else {}
    try:
        if peer.address is not None:
            result = await alp_client.call_peer(
                home=home,
                peer_id=peer.id,
                sender=sender,
                method="link.cancel",
                params=params,
                timeout=alp_client.PING_TIMEOUT_SECONDS,
            )
        else:
            result = await alp_client.call(
                socket_path=peers_mod.local_socket_path(peer),
                sender=sender,
                recipient_pubkey_b64=peer.pubkey,
                method="link.cancel",
                params=params,
                timeout=alp_client.PING_TIMEOUT_SECONDS,
            )
    except Exception:  # noqa: BLE001
        return False
    return bool(result.get("cancelled"))


def parse(text: str, home: Path | None = None) -> Mention | None:
    """Return a ``Mention`` if ``text`` contains a valid ``@<peer>``
    token (anywhere, with whitespace boundary), otherwise ``None``.

    When ``home`` is given, the matched id must also resolve to a
    pinned peer in that profile's ``peers.yaml`` — so an ``@property``
    in a code snippet falls through to the LLM instead of erroring on
    a missing peer.
    """
    if not text:
        return None
    m = _MENTION_RE.search(text)
    if m is None:
        return None
    peer_id = m.group(1)
    if home is not None and peers_mod.get_by_id(home, peer_id) is None:
        return None
    # Strip only the boundary whitespace around the ``@<peer>`` token,
    # never internal runs — the prompt may be quoted code or
    # deliberately formatted text.
    before = text[: m.start()].rstrip()
    after = text[m.end():].lstrip()
    if before and after:
        prompt = before + " " + after
    else:
        prompt = before + after
    if not prompt:
        return None
    return Mention(peer_id=peer_id, prompt=prompt)


async def execute(
    home: Path,
    peer_id: str,
    prompt: str,
    *,
    timeout: float | None = None,
    max_duration: float | None = None,
) -> Result:
    """Run a single ``link.ask`` against a pinned peer.

    Routes to TCP/Noise (ALP.2) when the peer has ``address`` set,
    otherwise falls back to the intra-machine Unix socket (ALP.1).

    Returns a ``Result`` with ``ok=True`` + reply on success, or
    ``ok=False`` + human-readable error text otherwise. Never raises —
    callers render ``error`` directly to the user.
    """
    final: dict = {}
    async for frame in execute_stream(
        home,
        peer_id,
        prompt,
        timeout=timeout,
        max_duration=max_duration,
    ):
        if frame.get("kind") == "error":
            return Result(
                ok=False,
                error=str(frame.get("text") or "unknown error"),
                transient=frame.get("transient") is True,
            )
        if frame.get("kind") == "final":
            final = frame
    if not final:
        return Result(
            ok=False,
            error="peer closed link.ask without a final response",
            transient=True,
        )
    return Result(
        ok=True,
        reply=str(final.get("text") or "").strip(),
        tokens_in=int(final.get("tokens_in") or 0),
        tokens_out=int(final.get("tokens_out") or 0),
        cost=float(final.get("cost") or 0.0),
        transient=final.get("transient") is True,
    )


async def execute_stream(
    home: Path,
    peer_id: str,
    prompt: str,
    *,
    timeout: float | None = None,
    max_duration: float | None = None,
):
    """Streaming variant of ``execute``. Async generator that yields:

    - ``{"kind": "chunk", "text": "..."}`` for incremental tokens
    - ``{"kind": "final", "text": "...", "tokens_in": …, …}`` once at end
    - ``{"kind": "error", "text": "..."}`` on failure

    Callers (TUI, desktop host, mobile) consume chunks for live rendering
    and use the final frame for bookkeeping (cost, session_id, …).
    """
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        yield {"kind": "error", "text": f"no peer @{peer_id} pinned"}
        return

    sender = load_or_generate(home)
    idle_timeout, max_seconds = _link_timeouts(home, timeout, max_duration)
    params = {"prompt": prompt, "stream": True}
    session_id = ""
    started = time.monotonic()
    agen = None
    try:
        if peer.address is not None:
            host, _, port_s = peer.address.rpartition(":")
            if not host or not port_s.isdigit():
                yield {"kind": "error", "text": f"invalid peer address {peer.address!r}"}
                return
            agen = alp_client.call_tcp_stream(
                host=host,
                port=int(port_s),
                sender=sender,
                recipient_pubkey_b64=peer.pubkey,
                method="link.ask",
                params=params,
                timeout=idle_timeout,
                connect_timeout=alp_client.PING_TIMEOUT_SECONDS,
            )
        else:
            socket_path = peers_mod.local_socket_path(peer)
            if not socket_path.exists():
                yield {
                    "kind": "error",
                    "text": f"listener not running (`alpi -p {peer_id} alp start`)",
                    "transient": True,
                }
                return
            agen = alp_client.call_stream(
                socket_path=socket_path,
                sender=sender,
                recipient_pubkey_b64=peer.pubkey,
                method="link.ask",
                params=params,
                timeout=idle_timeout,
                connect_timeout=alp_client.PING_TIMEOUT_SECONDS,
            )
        while True:
            try:
                if max_seconds > 0:
                    remaining = max_seconds - (time.monotonic() - started)
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    result, stream = await asyncio.wait_for(anext(agen), timeout=remaining)
                else:
                    result, stream = await anext(agen)
            except StopAsyncIteration:
                yield {
                    "kind": "error",
                    "text": "peer closed link.ask without a final response",
                    "transient": True,
                }
                return
            if result.get("session_id"):
                session_id = str(result["session_id"])
            kind = "final" if stream != "chunk" else "chunk"
            payload = dict(result or {})
            payload["kind"] = kind
            yield payload
            if kind == "final":
                return
    except alp_client.TargetOffline as e:
        yield {
            "kind": "error", "text": f"target-offline: {e}",
            "transient": True,
        }
    except alp_client.RemoteError as e:
        yield {
            "kind": "error", "text": str(e),
            "transient": alp_client.is_transient_link_error(e),
        }
    except asyncio.TimeoutError:
        cancelled = await _cancel(home, peer, sender, session_id)
        if max_seconds > 0 and time.monotonic() - started >= max_seconds:
            reason = f"link.ask exceeded its {max_seconds:g}s maximum duration"
        elif session_id:
            reason = f"link.ask timed out after {idle_timeout:g}s without remote activity"
        else:
            reason = f"link.ask timed out after {idle_timeout:g}s waiting for the peer"
        suffix = "; remote turn cancelled" if cancelled else ""
        yield {"kind": "error", "text": reason + suffix, "transient": True}
    except Exception as e:  # noqa: BLE001
        detail = str(e).strip() or type(e).__name__
        yield {
            "kind": "error", "text": detail,
            "transient": alp_client.is_transient_link_error(e),
        }
    finally:
        if agen is not None:
            await agen.aclose()
