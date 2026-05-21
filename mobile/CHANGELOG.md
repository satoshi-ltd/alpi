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

## v0.1.4 — 2026-05-21 — AX Local Notify (ambient notifications)

Requires alpi ``v0.5.8`` or newer. The mobile app now surfaces
events from your paired daemons as local notifications, even when
the app is closed — without using Apple/Google push infrastructure
and without any Satoshi-operated relay.

- Background polling via ``expo-background-task`` (iOS BGTaskScheduler,
  Android WorkManager) wakes the app every 15–60 min (system-paced).
  Each wake-up calls ``host.events.history`` over Tailscale across all
  paired connections and renders local notifications for new events.
- Notifiable kinds: ``wg.mention``, ``wg.done``, ``chat.turn_done``,
  ``approval.request``, ``schedule.done``, ``schedule.failed``,
  ``budget.threshold``. Everything else (plumbing events) is filtered
  out so the notification stream stays signal-only.
- ``chat.turn_done`` covers the canonical case: you kicked off a
  long-running research / multi-tool task in a profile, closed the
  app, and want a notification when it finishes. Only emitted for
  user-initiated turns that crossed a noise floor (any tool call OR
  ≥5s elapsed), so quick ``hola → hola`` exchanges don't ping.
- Foreground gating: while the app is active, ALN does NOT fire
  native notifications — the existing in-app event stream (toasts,
  modals, inbox refresh) handles those. Background-only delivery
  avoids duplicates and keeps the foreground experience uncluttered.
- Settings shows the OS notification permission as the single
  productive control (tap to request / status pill). The OS-level
  permission is the only gate: granting it activates ambient
  notifications; revoking it from iOS / Android settings is the only
  "off switch". No alpi-side toggle to keep out of sync. Dev builds
  also expose a "Test notifications" route under Settings for sample
  payload / deep-link checks; that route is hidden in production and
  redirects to home if accessed by URL.
- Background polling refuses to advance cursor when the OS
  permission is not granted — events stay re-fetchable until the
  user grants permission, so nothing is lost between revoke and
  re-grant cycles.
- Tapping a notification deep-links into the right screen: workgroup
  screen for mentions/dones, profile schedule for cron results.
- Seq-based cursor with idempotent dedup. Re-pulls of historical
  events do not re-notify. State is per-connection so two paired
  daemons stay independent.
- Dev-only "Test notifications" surface (``__DEV__`` gated, hidden
  from Settings in production, redirects to home if accessed by URL):
  one button per notifiable kind that fires a sample notification with
  a synthetic payload. Verifies styling, permission flow, and deep-
  link routing behavior. Native scheduling errors are NOT silently
  eaten — the dispatch result is surfaced via toast.
- Trade-off documented honestly: latency is 15–60 min on iOS
  (system decides), and delivery is opportunistic, not guaranteed.
  Instant alerts still belong on the Telegram/Matrix gateways.

## v0.1.3 — 2026-05-21 — reasoning effort in profile settings

Requires alpi ``v0.5.4`` or newer. On older daemons the row stays
hidden.

- Profile settings expose a reasoning effort sheet
  (``Default / Low / Medium / High``) right under the model picker,
  for OpenAI o-series, Claude 3.7+ / 4+, Gemini 2.5+, DeepSeek R1,
  and any OpenRouter route.
- The row only appears when the picked model supports reasoning;
  swapping to an unsupported model clears the value automatically.
- Mid-chat model overrides from the composer don't carry effort.

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
