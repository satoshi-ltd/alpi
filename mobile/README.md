# mobile — Alpi companion (Expo / React Native)

Expo app that pairs with one or more `alpi` daemons over the host-plane
WebSocket and surfaces the daily companion flows: inbox, chats with
profiles, workgroups, profile settings.

Desktop (`/desktop`, Tauri) is the reference for behavior and visual
language. Mobile is intentionally less dense — bottom sheets replace
dropdowns, long forms become navigation screens — but the `host.*` verb
contract is shared. No new daemon verbs were added; only an additive
event (`wg.post`) so mobile can refresh transcripts without the
filesystem watcher desktop relies on via Tauri.

## Setup

```bash
cd mobile
npm install
npm start                  # then press i (iOS sim) or a (Android emulator),
                           # or scan the QR with Expo Go on a physical device
npm test                   # node tests + vitest run — 76 cases across rpc, store, events, watchdog, EndpointProvider, useChatStream
npm run expo:doctor        # npx expo-doctor
```

Prerequisites on the alpi side:
- `alpi daemon start` running.
- Host-plane TCP listener enabled (`alpi setup → Connections → Network`).
- A pairing QR (or `alpi://` URL) generated on the desktop / TUI.

The QR / URL encodes daemon IP, TCP port, profile, and a device token.
The mobile app persists pairings via `expo-secure-store` and can hold
multiple paired daemons.

## What works today

- **Pairing.** Camera QR scan. On `auth-failed` the bridge in
  `app/_layout.jsx::AuthFailedBridge` forgets ONLY the failing endpoint
  (never global unpair) and routes to `/pair` only if it was the active
  daemon and no other paired daemons remain.
- **Multi-connection.** Persist many paired daemons; switch the active
  one from the `ConnectionSheet`. Per-connection probe status
  (online / offline / disabled / auth-failed / probing).
- **Inbox.** Profiles + workgroups sorted by recency (unread float to
  top), pinned strip up top, long-press for pin/settings actions,
  pull-to-refresh, FAB → ComposeSheet.
- **Profile chat.** Streamed responses (`host.chat.send`) with tool
  rows, cancel via `host.chat.cancel`; latest session auto-loaded;
  session switcher via SessionsSheet; keyboard avoidance + inverted
  FlatList; markdown body rendering via `src/components/RichText.jsx`.
- **Workgroups.** Encrypted transcript via `host.workgroup.transcript`;
  post via `host.workgroup.post`; live refresh on `wg.post` / `wg.done`
  events; own-vs-others side via pubkey match; workgroup settings:
  pause/resume, briefing edit, budget edit, members list, add member,
  kick, leave/delete.
- **Profile settings.** Overview, model picker (PickerRow), budget,
  workspace, accent, subsystem toggles (schedule/alp/workgroups),
  email, identity, peers, schedule, sandbox, voice,
  MCP add/remove, providers (Ollama-first, then cloud keys),
  brain (skills, memories, tools), storage breakdown, delete profile.
- **Live events.** Single `host.events.subscribe` stream at app root
  (`EventsProvider`) with exponential-backoff reconnect and
  `host.events.history` backfill on each reconnect.

## Known gaps

- **Voice messages.** The mic button in the composer is intentionally
  inert (toast: "Voice messages coming soon"). Audio capture / STT is
  not implemented; `RECORD_AUDIO` permission is NOT declared.
- **Pending peer invites surface.** `host.peers.pending_list` exists in
  the providers screen but inbound `peer.invite` toasts/banners aren't
  surfaced yet on the inbox.
- **Voice test button.** No `host.voice.test` verb. Desktop plays a
  sample via local Tauri command; mobile would need a daemon verb that
  streams synthesized audio.
- **Connections section.** Self-pairing from mobile to add new devices —
  not typical, deferred.
- **Web export.** `npx expo export --platform web` fails (no `react-dom`
  / `react-native-web`). Mobile is iOS + Android only.

## Architecture

- `app/` — file-based routing via expo-router. `_layout.jsx` mounts the
  provider tree (Theme → Endpoint → Events → Toast). Routes:
  - `index.jsx` (Inbox)
  - `chat/[id].jsx` (profile chat)
  - `wg/[id].jsx`, `wg/[id]/{settings,briefing,budget,member}.jsx`,
    `wg/new.jsx`
  - `profile/[id]/{settings,identity}.jsx`,
    `profile/[id]/{providers,peers,schedule,mcp,brain/*,email}/…`
  - `pair.jsx`, `paired.jsx`, `onboarding.jsx`, `biometric.jsx`
- `src/lib/rpc.js` — pooled WebSocket per `(ip, port, token)` for unary
  RPCs (one persistent socket multiplexes every `call`, IDs route the
  reply), plus a dedicated socket per `callStream`. Streams accept an
  optional `cancelMethod` so chat cancels via `host.chat.cancel` and
  events.subscribe just tears down the socket. `dropEndpointPool(endpoint)`
  is wired into `EndpointProvider.{setActive,forget,unpair}` so stale
  sockets release on connection switch.
- `src/lib/EndpointProvider.jsx` — multi-connection context:
  `connections`, `activeId`, `endpoint`, `call`, `callStream`, `setActive`,
  `addConnection`, `forget`, `unpair`, `probeState`. Auth-failed is
  handled by `AuthFailedBridge` in `app/_layout.jsx` (not by this
  provider — needs router + toast context).
- `src/lib/store.js`, `src/lib/pins.js`, `src/lib/readState.js` —
  SecureStore-backed local state (connections, pins, per-daemon read
  pointers). Writes coalesce via debounced flush where bursts are
  expected (readState).
- `src/hooks/useDaemonData.js` — shared module-level cache for `host.*`
  reads. Every consumer subscribes to the same cache entry by `(method,
  params)`; any `refresh()` propagates to all subscribers (fixes
  "created elsewhere, doesn't show here" stale-list bugs).
- `src/hooks/useEvents.js` — `EventsProvider` (one host.events.subscribe,
  reconnect + backfill) + `useEventEffect(kinds, fn)`.
- `src/hooks/useChatSend.js` — chat streaming with rAF-batched
  `assistant_delta` flushes (1 render per frame regardless of token rate).
- `src/components/` — design-system primitives: Button, Field, Pill, Row,
  Sheet, PickerRow, Toast, ScreenHeader, Diamond, Dot, Glyph, RichText,
  Swipeable, Switch, Banner, ActionSheet, TypedConfirm…
- `src/features/` — composite components: ChatHeader, Bubble, MarkerCard,
  ThinkingDots, ToolCallRow, MessageActionsSheet, Composer; inbox
  features (InboxRow, PinnedRow, ConnHeader, RowContextSheet,
  SegmentedFilter); sheets (Model, Voice, Accent, Budget, Workspace,
  Sessions, Compose, Connection, Settings, Activity).
- `src/theme/` — design tokens (`space`, `radii`, `fontSizes`,
  `lineHeights`, `fonts`, `alpha`, `motion`, `palettes`, `shadows`,
  `mobile`) live in `tokens.js` and are imported directly. Theme-
  dependent values (`colors`, `shadow`) come from `useTheme()`.
  `accents.js` exports `profileAccents` + `accentForProfile()` + a
  picker palette `namedAccents`.

## Performance notes

- Hot-path components (`InboxRow`, `TurnBlock`, `WgItem`, `MarkerCard`,
  `Bubble`) are `memo()`d with module-level `StyleSheet.create` and
  stable `useCallback` handlers / `useMemo` data so token streaming
  doesn't re-render the whole list.
- `useChatSend` buffers `assistant_delta` and flushes on
  `requestAnimationFrame` — chat re-renders ≤60Hz regardless of token
  rate.
- `useDaemonData` dedupes in-flight requests by `(endpoint.id, method,
  params)` so a burst of mounts (inbox + ComposeSheet + chat opening at
  once) reuses a single WebSocket call.
- Inbox FlatList uses `getItemLayout` (rows are constant 64.5px) for
  zero-cost layout measurement on long lists.

## Coding rules specific to mobile

- No TypeScript. JS + JSX only; React 19.2 / RN 0.83 / Expo SDK 55
  (New Architecture mandatory).
- No new `host.*` verbs unless the daemon has no equivalent. The daemon
  is the contract — mobile adapts.
- Reuse design-system primitives in `src/components/`. If a primitive
  doesn't exist for a recurring pattern, add it.
- English copy only in user-visible strings.
- Modals over dropdowns. Bottom sheets over modals when picking from a
  list. PickerRow for vertical option lists (accent dot for selected).
- Every async action surfaces loading / error / empty states.
- Destructive actions go through `TypedConfirm`.
- Theme-aware styles inline OR `StyleSheet.create` at module scope.
  Mass migration to one or the other is churn — use what fits the
  surface (hot-path = StyleSheet, one-off screens = inline).
