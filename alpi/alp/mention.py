"""``@peer rest…`` shortcut parsing + execution.

The ``@peer`` gesture is used from two places:
- TUI input (``alpi/tui/app.py``): typed with a leading ``@``.
- Gateway inbound text (``alpi/gateway/run.py``): a user DM-ing ``@peer hi``
  from Telegram / email / webhook should route to the peer without
  firing the local LLM.

Both call through this module so the semantics match: same parsing
rules, same resolution rules, same error shapes. The ``peer`` tool
(``alpi/tools/peer.py``) uses the same executor so LLM-invoked calls
and direct ``@``-mentions hit the same code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp.keys import load_or_generate


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


def parse(text: str) -> Mention | None:
    """Return a ``Mention`` if ``text`` starts with a valid ``@handle prompt``
    gesture, otherwise ``None``.

    Rules:
    - Must start with ``@`` at position 0 — no leading whitespace.
    - ``@handle`` must be followed by whitespace + non-empty prompt.
    - Empty prompt or missing handle → ``None``.

    The strict leading-``@`` rule is what keeps ``oye manda un email a
    hello@soyjavi.com`` from triggering anything.
    """
    if not text.startswith("@") or len(text) < 2:
        return None
    body = text[1:]
    parts = body.split(maxsplit=1)
    if len(parts) != 2:
        return None
    peer_id = parts[0].strip()
    prompt = parts[1].strip()
    if not peer_id or not prompt:
        return None
    return Mention(peer_id=peer_id, prompt=prompt)


def _target_home(peer_id: str) -> Path:
    if peer_id == "default":
        return Path.home() / ".alpi"
    return Path.home() / ".alpi" / "profiles" / peer_id


async def execute(home: Path, peer_id: str, prompt: str, *, timeout: float = 300.0) -> Result:
    """Run a single ``link.ask`` against a pinned peer over ALP.1 (Unix socket).

    Returns a ``Result`` with ``ok=True`` + reply on success, or
    ``ok=False`` + human-readable error text otherwise. Never raises —
    callers render ``error`` directly to the user.
    """
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        return Result(ok=False, error=f"no peer @{peer_id} pinned")
    if peer.address is not None:
        return Result(ok=False, error=f"@{peer_id} is remote — ALP.2 pending")

    socket_path = _target_home(peer_id) / "alp" / "alp.sock"
    if not socket_path.exists():
        return Result(
            ok=False,
            error=f"listener not running (`alpi -p {peer_id} alp start`)",
        )

    try:
        sender = load_or_generate(home)
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
