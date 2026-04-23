"""ALP — Alpi Link Protocol.

Reference implementation of the ALP specification (see
``docs/ALP.md``). Covers agent-to-agent communication between alpi
instances: intra-profile on the same machine over a Unix-domain
socket (this package, v0.3), inter-machine over Noise_XK-on-TCP
(v0.4), and shared rooms (v0.4+).
"""

from __future__ import annotations

PROTOCOL_VERSION = 1
"""The ALP protocol version this implementation speaks.

Senders tag every envelope with this value. Receivers reject
messages carrying an unknown version with error ``-32006``. A
bump is deliberate and lands alongside a changelog entry in
``docs/ALP.md``.
"""
