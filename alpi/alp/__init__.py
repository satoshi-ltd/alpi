"""ALP — Alpi Link Protocol.

Reference implementation of the ALP specification (see
``docs/ALP.md``). Covers agent-to-agent communication between alpi
instances: intra-profile on the same machine over a Unix-domain
socket, inter-machine over Noise_XK-on-TCP, and shared workgroups.
"""

from __future__ import annotations

PROTOCOL_VERSION = 1
"""Receivers silent-drop envelopes with any other version (no wire error)."""
