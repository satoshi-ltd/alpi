"""``@peer rest…`` shortcut parsing + execution.

The ``@peer`` gesture is used from two places:
- TUI input (``alpi/tui/app.py``): typed anywhere in the message.
- Gateway inbound text (``alpi/gateway/run.py``): a user DM-ing
  ``hey @peer can you…`` from Telegram / email / webhook routes to
  the peer without firing the local LLM.

Both call through this module so the semantics match: same parsing
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

import re
from dataclasses import dataclass
from pathlib import Path

from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp.keys import load_or_generate


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


def parse(text: str, home: Path | None = None) -> Mention | None:
    """Return a ``Mention`` if ``text`` contains a valid ``@<peer>``
    token (anywhere, with whitespace boundary), otherwise ``None``.

    When ``home`` is given, the matched id must also resolve to a
    pinned peer in that profile's ``peers.yaml`` — used by the TUI
    and the gateway so an ``@property`` in a code snippet falls
    through to the LLM instead of erroring on a missing peer.
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


def _target_home(peer_id: str, pubkey: str = "") -> Path:
    from alpi import home as home_mod
    match = home_mod.find_home_by_pubkey(pubkey) if pubkey else None
    if match is not None:
        return match
    if peer_id == "default":
        return Path.home() / ".alpi"
    return Path.home() / ".alpi" / "profiles" / peer_id


async def execute(home: Path, peer_id: str, prompt: str, *, timeout: float = 300.0) -> Result:
    """Run a single ``link.ask`` against a pinned peer.

    Routes to TCP/Noise (ALP.2) when the peer has ``address`` set,
    otherwise falls back to the intra-machine Unix socket (ALP.1).

    Returns a ``Result`` with ``ok=True`` + reply on success, or
    ``ok=False`` + human-readable error text otherwise. Never raises —
    callers render ``error`` directly to the user.
    """
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        return Result(ok=False, error=f"no peer @{peer_id} pinned")

    sender = load_or_generate(home)
    try:
        if peer.address is not None:
            reply = await alp_client.call_peer(
                home=home,
                peer_id=peer_id,
                sender=sender,
                method="link.ask",
                params={"prompt": prompt},
                timeout=timeout,
            )
        else:
            socket_path = _target_home(peer_id, peer.pubkey) / "alp" / "alp.sock"
            if not socket_path.exists():
                return Result(
                    ok=False,
                    error=f"listener not running (`alpi -p {peer_id} alp start`)",
                )
            reply = await alp_client.call(
                socket_path=socket_path,
                sender=sender,
                recipient_pubkey_b64=peer.pubkey,
                method="link.ask",
                params={"prompt": prompt},
                timeout=timeout,
            )
    except alp_client.TargetOffline as e:
        return Result(ok=False, error=f"target-offline: {e}")
    except alp_client.RemoteError as e:
        return Result(ok=False, error=str(e))
    except Exception as e:  # noqa: BLE001
        return Result(ok=False, error=str(e))

    return Result(
        ok=True,
        reply=str(reply.get("text") or "").strip(),
        tokens_in=int(reply.get("tokens_in") or 0),
        tokens_out=int(reply.get("tokens_out") or 0),
        cost=float(reply.get("cost") or 0.0),
    )


async def execute_stream(
    home: Path, peer_id: str, prompt: str, *, timeout: float = 300.0,
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
    params = {"prompt": prompt, "stream": True}
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
                timeout=timeout,
            )
        else:
            socket_path = _target_home(peer_id, peer.pubkey) / "alp" / "alp.sock"
            if not socket_path.exists():
                yield {
                    "kind": "error",
                    "text": f"listener not running (`alpi -p {peer_id} alp start`)",
                }
                return
            agen = alp_client.call_stream(
                socket_path=socket_path,
                sender=sender,
                recipient_pubkey_b64=peer.pubkey,
                method="link.ask",
                params=params,
                timeout=timeout,
            )
        async for result, stream in agen:
            kind = "final" if stream != "chunk" else "chunk"
            payload = dict(result or {})
            payload["kind"] = kind
            yield payload
    except alp_client.TargetOffline as e:
        yield {"kind": "error", "text": f"target-offline: {e}"}
    except alp_client.RemoteError as e:
        yield {"kind": "error", "text": str(e)}
    except Exception as e:  # noqa: BLE001
        yield {"kind": "error", "text": str(e)}
