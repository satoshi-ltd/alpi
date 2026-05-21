# Mobile changelog

Release history for the Expo / React Native mobile client.
Tracked separately from the alpi (CLI) [CHANGELOG.md](../CHANGELOG.md)
and the desktop client [CHANGELOG.md](../desktop/CHANGELOG.md) —
the three products ship on their own cadence with their own
version schemes:

- alpi (CLI)  → ``vX.Y.Z`` (PyPI + GitHub release)
- desktop app → ``desktop-vX.Y.Z`` (GitHub release only)
- mobile app  → ``mobile-vX.Y.Z`` (EAS build only)

The mobile app is a host-plane client of one or more remote
``alpi`` daemons over Tailscale. Each release pins a minimum
compatible alpi version.

## v0.1.2 — 2026-05-21 — approval sheet for caution commands

Requires alpi ``v0.5.1`` or newer. On older daemons the sheet stays
dormant.

- Caution commands (recursive `rm`, `sudo`, force-push, …) now open a
  sheet with four choices: allow once, allow this session, always,
  deny. Previously these only worked from the TUI.
- Opening the app mid-prompt or switching to a daemon that already
  has a pending prompt shows it immediately.
- The sheet pops automatically if another paired client answers
  first.

## v0.1.1 — 2026-05-21 — endpoint switch hardening + skeleton polish

Requires alpi ``v0.4.52`` or newer. No daemon contract change.

- Endpoint switching no longer renders the new daemon header over the
  previous daemon's data. ``usePolledCall`` resets snapshots
  synchronously on cache-key changes, guards stale listeners, and
  ``useProfile`` clears heavy profile detail when the endpoint changes.
- Inbox, sessions, and chat loading states now use skeletons that match
  the final row/message geometry. ``SkeletonBar`` provides the shared
  native-driver pulse primitive.
- Tool calls now match desktop behavior: adjacent same-name calls group
  behind one ``×N`` row with per-call status dots and expandable
  children.
- Added endpoint-switch tests for stale query data and profile detail
  bleed. 78/78 tests pass.

## v0.1.0 — 2026-05-20 — first cut (SDK 55, design tokens, workgroup flow, 76 tests)

First public mobile release. Expo SDK 55 + React Native 0.83 +
React 19.2 on the New Architecture. Establishes the host-plane
client surface (chat, sessions sheet, workgroup detail), the
design-token system shared in spirit with desktop, and the
endpoint-context plumbing that talks to remote ``alpi`` daemons
over Tailscale-authenticated WebSocket.

Foundations for everything that follows ship in this release:
``EndpointProvider`` with per-endpoint WS pool dropping on
switch, the module-level cache in ``useDaemonData`` keyed by
``(endpoint.id, method, params)``, ``ChatSkeleton``, secure
token storage via ``expo-secure-store``, pairing via QR
scanning, biometric unlock, and the initial 76-test vitest +
node-runner suite covering RPC framing, schedule formatting,
read-state, profile-readiness, and the chat send watchdog.
