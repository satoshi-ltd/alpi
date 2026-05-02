# Desktop changelog

Release history for the Tauri desktop client. Tracked separately
from the alpi (CLI) [CHANGELOG.md](../CHANGELOG.md) — the two
products ship on their own cadence with their own version
schemes:

- alpi (CLI)  → ``vX.Y.Z`` (PyPI + GitHub release)
- desktop app → ``desktop-vX.Y.Z`` (GitHub release only)

The desktop app is a host-plane client of a local ``alpi``
daemon. Each release pins a minimum compatible alpi version.

## v0.1.0 — 2026-05-02 — first public desktop release

First Tauri client landed. Requires alpi ``v0.3.9`` or newer for
the host-plane control API.

- New Tauri 2 desktop client under ``desktop/`` — Rust + React + plain JS (no TypeScript). Talks to the daemon through the host plane on the local Unix socket; does not run an LLM, does not own tools, does not duplicate security.
- Settings: ``Services`` section with ``subsystems`` chips, ``gateways`` chips (disabled when ``gateway`` service is off), ALP identity / peers / workgroups, ``Schedule`` section with one row per job (Fire / Enable / Disable / Delete + state bullet).
- Subsystem toggles, TCP port edits, gateway saves auto-restart the daemon (``host.daemon.restart``) so the change applies without a manual nag.
- ``@<peer>`` mentions in chat go through the same host-plane shortcut, persisted as a real session turn so the desktop's tool card survives the round-trip.
- Tray icon, native window, signed auto-update through the Tauri updater (manifest at ``releases/download/desktop-latest/latest.json``, minisign-verified against the public key embedded in ``tauri.conf.json``).
