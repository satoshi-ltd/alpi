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

## v0.1.25 — 2026-05-29 — task sheet reads skips correctly

- **Skips read correctly.** One member passing on a round no longer
  marks the whole task as skipped or counts it resolved — the task
  stays active until the hub closes it.
- **No phantom tasks.** A message that both opens and closes a task is
  shown as plain text instead of a stray entry in the sheet.
- **Cleaner working indicator.** Active tasks show a single pulsing dot
  — tasks sheet, header, and `#working` posts — so tasks read as just
  working, done, or skipped.

## v0.1.24 — 2026-05-29 — task slugs + denied tools

- **Composer enforces `#task #<slug>`.** Workgroup composer validates
  as you type: Send button disabled and an inline warning shows
  until a valid `#<slug>` follows. `#task` without a slug is no
  longer treated as a task anywhere in the workgroup UI — parser and
  `buildTasks` match the new alpi protocol gate. TasksSheet reads
  the slug straight from the post.
- **Denied tools shown muted.** Tools blocked by `tools.deny` in the
  profile's `config.yaml` now show up struck-through with a `DENIED`
  label in the profile's tools list. Opening one shows a banner
  explaining the agent doesn't have access. Previously every
  registered tool looked available regardless.

## v0.1.23 — 2026-05-29 — workgroup transcript polish

Brings the workgroup transcript to parity with desktop and fixes the
"WORKING that never ages" bug on mobile.

- `#task` cards now show the full briefing under the title; `#done`,
  `#working`, and `#skip` render the entire body in markdown
  (paragraphs, lists, bold) instead of clipping to the marker line.
- Slug-aware tasks: `#task #my-slug ...` highlights the slug in bold
  and uses it as the task id in the tasks sheet.
- Stale `#working` (later post from same peer **or** a `#done`/`#skip`
  closure) shows a `WORK` label with a static dot; active `#working`
  pulses the hub-colored diamond.
- Workgroup header now puts a hub-colored diamond next to `@hub_id` in
  the meta line.
- Workgroup messages: borderless bubbles, equal tint for hub and
  members, body rendered with markdown — same look as desktop.

## v0.1.22 — 2026-05-28 — member role surface + restart daemon

Closes the member role on mobile and brings the daemon restart button
that landed on desktop. No device management on mobile — that stays a
desktop-only admin console by design.

- New `useActiveRole` / `useCanAdminEarly` / `useIsAdmin` hooks on top
  of `host.version.role`. AdminGuard wraps every host-settings route
  (`profile/[id]/*` layout + `wg/[id]/{settings,briefing,member}` +
  `/profile/new` + `/wg/new`). Pending probe state renders null so
  admin RPCs don't fire on first mount.
- Member visual gates: gear icons in chat headers, "+ New profile / +
  New workgroup" in ComposeSheet, the inbox row Settings action, and
  the chat empty-state CTA all hide. Empty hero swaps copy to "Ask
  the host admin…".
- New **Restart daemon** row in profile `Settings → Service`
  (admin-only), typed-confirm sheet asking for the word `restart`.
- Approval sheet eyebrow renamed `SANDBOX` → `ALERT` in danger red.

Requires alpi ≥ 0.6.29.

## v0.1.21 — 2026-05-28 — alpi 0.6.28 pairing surface

Cosmetic alignment with the alpi 0.6.28 per-device profile scope
rollout. Mobile's role on this surface stays as token consumer —
admin / scope management lives in the TUI and desktop until `UX.5`
brings parity to mobile.

- Pairing URL `v=2` placeholder dropped from the input field hint
  and parser comment; the parser was already version-agnostic so
  existing paired devices keep working.
- A scoped-member token receives `-32001 forbidden` on out-of-scope
  RPCs via the daemon-side gate. No mobile UI change needed; the
  existing error path surfaces it as a toast.

## v0.1.20 — 2026-05-27 — peers screen refreshes on every action

Same fix as desktop 0.3.26 — the peers screen no longer needs a daemon
push event to drop a revoked peer or hide a discarded invite.

- The peers list re-reads `host.profile.detail` on focus, so returning
  from add / revoke / accept reflects the daemon state immediately
  even if the `peers_changed` event is delayed over a flaky Tailscale
  leg.
- Discarding a pending invite forces an in-place refresh of both the
  pending list and the profile detail.
- `useProfile` now exposes `refreshDetail()` for any screen that needs
  to force a re-read of the heavy companion (peers, models, mcps).

## v0.1.19 — 2026-05-27 — design tokens aligned with desktop

Same clothing-size scale as the desktop CSS variables, so a value that
reads as "lg" in one client renders the same in the other. No visible
shift in everyday screens; a handful of sub-px differences in chat
bubbles, headers and badges get rounded to the nearest token.

- Font sizes collapsed from 21 names → 9 (xxs · xs · sm · base · md ·
  lg · xl · 2xl · display). Same scale as desktop `--fs-*` with one
  extra `2xl: 22` for the Locked / empty-chat heading.
- Line heights aligned with desktop multipliers (tight 1, cozy 1.3,
  normal 1.5, relaxed 1.65) and applied as `fontSize · tier` across
  flowing text. Badges and icon-centering keep their raw pixel values
  because they're layout, not typography.
- A few stray `15.5` / `14.5` / `11.5` font sizes and a couple of bug
  `fontWeight` strings (those don't apply to Inter loaded by family)
  are fixed.
- Four unused design-system primitives (`Eyebrow`, `SearchField`,
  `Switch`, `SwitchRow`) and the dead `Geist` fallback font family are
  removed.

## v0.1.18 — 2026-05-27 — ask_user clarification sheet (UX.1)

When the agent calls ``ask_user`` on a daemon paired with this
device, mobile pops a native sheet with one button per choice
instead of asking via numbered chat text.

- New ``ClarificationSheet`` (rendering) + ``useClarificationQueue``
  (state + RPC) under ``src/features/clarification/``. Mirrors the
  approval-sheet pattern.
- Subscribes to ``clarification.request`` /
  ``clarification.resolved`` on the live event stream and fetches
  ``host.clarification.pending`` whenever the active endpoint
  changes so cold-start clients pick up in-flight requests.
- An "Other…" affordance swaps in a text input when the user wants
  to answer outside the enumerated choices; closing the sheet sends
  a clean ``User cancelled clarification.`` so the daemon resolves
  the model's Future cleanly.

Requires alpi ≥ 0.6.18.

## v0.1.17 — 2026-05-26 — drop the TTS autoplay toggle

Audio playback is already a per-message action (the play button in
each bubble). The separate autoplay row in profile settings was
redundant and only made sense when the daemon was the player — now
it's gone.

- Profile → Voice loses the **Autoplay** row. Voice picker stays;
  audio delivery is up to the message UI.
- The mobile client no longer calls ``host.voice.autoplay``. Older
  daemons that still register it are unaffected; new daemons reply
  ``method-not-found`` to anything that calls it.

Requires alpi ≥ 0.6.12.

## v0.1.16 — 2026-05-25 — Outputs inbox replaces Activity

The bell icon now opens a real inbox of proactive messages, not
a transient event log. Every ``send_message`` and every schedule
failure is a durable row you can come back to — survives reboots,
app kills, and the OS clearing the notification tray.

- New ``Outputs`` screen at the bell-icon target. Pull-to-refresh,
  ``Mark all read`` in the header (with a live unread count
  beside the title). Auto-refreshes when the daemon emits
  ``output.created`` / ``output.updated``.
- Tapping a row opens an output detail screen with the full body,
  source (``send_message`` / ``schedule``), severity, delivered
  channels, ``Copy``, and a contextual ``Open chat`` / ``Open
  schedule`` button when applicable.
- Opening a row marks it read; ``Mark all read`` clears every
  ``unread`` across the active daemon's profiles via
  ``host.outputs.mark_all_read``.
- ``agent.message`` and ``schedule.failed`` notifications now
  honour the daemon's ``deep_link`` (``/outputs/<profile>/<id>``)
  and land you on the persisted row instead of a chat window.
- The old ``Activity`` event-history sheet is gone — events are
  internal transport now, the inbox is the surface.

Requires alpi ``v0.6.11`` or later (older daemons don't ship
``host.outputs.*``).

## v0.1.15 — 2026-05-25 — cold-start probes only the active daemon

Cheaper, more honest startup: the cold-start path no longer
probes every saved connection on launch — that was wasted work
since per-row status is only ever shown inside the connection
sheet.

- ``EndpointProvider.refresh()`` loads from SecureStore and
  probes the active endpoint only. New ``probeAllConnections``
  handles the full-list refresh and fires on
  ``ConnectionSheet`` open. Non-active rows stay ``unknown``
  until that surface is visible.
- ``ConnectionSheet`` triggers ``probeAll`` in a ``useEffect``
  gated on ``open`` so the network cost lands at the moment
  the user actually wants to pick.
- Cold-start failure auto-opens the connection sheet once
  (``useFireOnce`` hook) so the user can switch or pair instead
  of landing on an offline-only inbox. Later blips do not
  re-pop the sheet.

## v0.1.14 — 2026-05-24 — stop notification flood

Several independent fixes that together kill the "same
notification fires many times" symptom.

Requires alpi ``v0.6.6`` or newer for the daemon-identity piece;
the rest works against any daemon.

- ALN now claims events in the persisted cursor BEFORE attempting
  to fire the notification. The previous order (fire → on success
  → commit) was fragile: Android Doze can kill the background
  task between ``scheduleNotificationAsync`` (notif already
  delivered to the OS) and ``SecureStore.setItemAsync``, leaving
  the seq uncommitted → next wake re-fetches the same events and
  re-fires. Trade-off: a rare OS kill mid-task may now lose one
  notification rather than dup it forever.
- ``runPollOnce`` dedupes connections by daemon identity
  (``device_id`` from ``host.version``), not by ``(ip, port)``.
  LAN address + Tailscale address pointing at the same daemon
  now collapse to one poll. Re-pairings the user collected
  during cleartext debugging are also collapsed. Same-daemon
  ties resolve to the most recently added connection
  (``added_at``).
- Per-daemon state (``afterSeq`` / ``seenIds``) is keyed by
  ``daemon:<device_id>`` instead of ``connection.id``. Re-pairing
  the same daemon no longer resets the cursor.
- In-memory mutex on ``runPollOnce``: a second wake-up while the
  first is still running returns ``{skipped: 'in-flight'}``
  instead of starting a second concurrent poll.
- ``chat.turn_done`` removed from ``NOTIFIABLE_KINDS``: every
  assistant turn was emitting one, flooding the lock screen
  with redundant noise. Real "user got a message" still fires
  through ``agent.message``.
- Pairing rejects a daemon that answers ``host.version`` without
  a ``device_id`` (instead of saving a half-functional connection
  that ALN would then ignore). ``saveConnection`` refuses entries
  without a ``deviceId`` and ``loadConnections`` filters any
  legacy entry lacking one. ``unpair()`` and ``signOut()`` also
  wipe the legacy ``alpi.endpoint`` SecureStore key for hygiene.

Logic split across pure helpers (``groupConnectionsByDaemon``,
``alnStateKey``); regression tests cover group-by-daemon + route
failover, claim-before-fire ordering, in-flight mutex, no-event
skip, permission bail, no-``chat.turn_done``, and
``alnStateKey`` requiring a ``deviceId``.

## v0.1.13 — 2026-05-24 — your message stops showing twice while streaming

Since alpi v0.6.2 the daemon writes a *stub* turn (with the user
text but an empty assistant) into session.json as soon as the
user message lands, so paired clients see the message
immediately. Mobile didn't account for that: while the agent was
still streaming, the stub from `turns` and the optimistic
`pendingTurn` from useChatSend both rendered → you saw your
prompt twice. As soon as the assistant finished, the stub got
filled in and the duplicate collapsed.

- ChatList's turn merge moved into a pure
  `mergeStreamingTurn(turns, pendingTurn)` helper. Single rule:
  if the last persisted turn has the same `user` and an empty
  `assistant`, treat it as the stub and merge `pendingTurn`
  into it; otherwise just append `pendingTurn`. Text identity
  is not used as a turn id — sending the same text twice in a
  row no longer eats the second message.
- A transient 1-frame visual duplicate during the
  done→pendingTurn-clear swap is accepted; swallowing a
  legitimate repeat is worse.
- 7 regression tests cover the stub merge, the same-text-twice
  case, the post-stream duplicate-is-acceptable case, and the
  defensive null-turns paths.

## v0.1.12 — 2026-05-23 — long-press Edit and Retry actually do something

Both chat and workgroup screens forgot to wire `onEdit` and
`onRetry` on the MessageActionsSheet, so the Edit / Retry /
Ask again rows were no-ops.

- Chat user message → Edit prefills the composer; Retry re-sends
  with `rewrite_from_turn` so the daemon truncates back to that
  turn (matches desktop).
- Chat assistant message → Ask again re-sends the *original
  user prompt* (carried in `target.retryText`) with
  `rewrite_from_turn`. Previously it would have echoed the
  assistant text as the new prompt.
- Workgroup own messages → Edit + Retry (re-post; workgroups
  have no truncate primitive). Workgroup foreign messages →
  only Copy (Ask again hidden — re-posting another peer's text
  on your own account is the wrong default).
- Composer accepts `seedText` + `seedKey` props for external
  seeding without lifting state.
- Action visibility lives in `messageActions.buildMessageActions`
  with regression tests covering each (kind, retryText)
  combination.

## v0.1.11 — 2026-05-23 — workspace edits stick in the sheet

- The workspace sheet now accepts external `initialValue`
  updates only while the user has not typed: if `initialValue`
  arrives async after the sheet opens (e.g. via
  `host.profile.detail`), the field hydrates; once the user
  starts typing, further external updates are ignored until the
  next time the sheet opens. Logic in `lib/sheet-value`,
  covered by five regression tests.

## v0.1.10 — 2026-05-22 — notification deep link lands on the right chat

Requires alpi ``v0.6.5`` or newer for the daemon side of the fix
(older daemons still emit the broken path; the mobile fallback
below covers them).

- Tapping a notification with an ``agent.message`` or
  ``chat.turn_done`` payload now routes to the profile's chat
  (``/chat/<profile>``) instead of a non-existent
  ``/chat/<session_id>`` (the chat route reads ``[id]`` as a
  profile name, so the session-id path resolved to a "profile
  not found" / unmatched-route state).
- The ``session_id`` continues to travel in the notification
  payload so the chat screen can pre-select that session once it
  mounts.

## v0.1.9 — 2026-05-22 — Android cleartext for local daemons

Pairing on Android always returned "Daemon unreachable" against a
daemon on the Tailscale / LAN / Umbrel network. Android 9+ blocks
cleartext WebSocket traffic by default; iOS allowed it, so the
issue only surfaced on Android (e.g. a Samsung S25 on Tailscale).

- ``expo-build-properties@55.0.14`` added; ``usesCleartextTraffic:
  true`` configured inside the plugin entry. Expo SDK 55 routes
  this property exclusively through the plugin — a top-level
  ``android.usesCleartextTraffic`` in ``app.json`` is silently
  ignored. Verified with ``expo config --type introspect`` that
  the AndroidManifest receives ``android:usesCleartextTraffic='true'``.
- Requires a fresh EAS build to land (native manifest change).

## v0.1.8 — 2026-05-22 — pairing fixes

Requires alpi ``v0.6.4`` or newer for the daemon-name fix; the
unreachable bug works against any daemon.

- Pairing no longer always reports "Daemon unreachable" — the
  reachability check was comparing the wrong shape (regression
  since v0.1.0) and every pair attempt fell through to the error
  branch even when the daemon was up. Five regression tests added.
- The connection label is now the daemon's own ``device_name``
  (set via ``alpi setup``), not the label the pairing URL carried
  for the device being paired. So pairing your iPhone to your
  Macbook.Pro daemon shows "Macbook.Pro", not "iPhone".

## v0.1.7 — 2026-05-22 — instant fire feedback

Requires alpi ``v0.6.3`` or newer.

- Tapping "Fire now" on a schedule shows an immediate
  ``Schedule X started`` toast (matched to the desktop style)
  instead of holding the action sheet open until the agent
  finished. The job's result still arrives through the usual
  notification, and failures surface through the existing
  schedule event path.

## v0.1.6 — 2026-05-22 — leaving a chat no longer kills the work, lighter activity UI

Requires alpi ``v0.6.2`` or newer. Long-running tools (research,
deep web fetches, etc.) now survive screen exits, and the chat
view drops a couple of redundant activity indicators.

- Navigating away from a chat closes the local WebSocket but does
  NOT tell the daemon to interrupt. The tool finishes on the
  daemon side; come back later and the full reply is there,
  loaded from the persisted session.
- New ``detach()`` on the stream handle, used by ``useChatSend``
  on unmount. The explicit cancel button keeps cancelling.
- No more spinner inside a running tool row — the existing pulse
  already conveys "this is the one running".
- The "thinking" dots now only appear in the brief window between
  the user message and the first tool call (or first assistant
  text). After that, the pulse / streaming text takes over.

## v0.1.5 — 2026-05-22 — agent.message ambient notifications

Requires alpi ``v0.6.1`` or newer. The mobile app now surfaces the
new ``agent.message`` host event as a local notification, so any
``send_message`` call the agent makes via the default ``alpi``
channel lands as a native banner without any gateway in the middle.

- ``agent.message`` added to ALN's ``NOTIFIABLE_KINDS``. Title is
  the payload's ``title`` (falls back to a connection / profile /
  severity composite). Body is the payload's ``body``.
- Tap deep-link: ``data.deep_link`` wins when present; otherwise
  routes to ``/chat/<session_id>`` if the agent attached one. Falls
  back to the inbox root when neither is available.
- ``schedule.done`` is intentionally NOT in ALN's notifiable set.
  Successful schedules are activity/history only; jobs that need to
  wake the user call ``send_message(channel="alpi")`` explicitly.
  ``schedule.failed`` remains notifiable.
- The dev-only "Test notifications" route under Settings includes
  an ``agent.message`` sample so the deep-link routing can be
  verified locally with a single tap.
- ``wg.mention`` removed from the notifiable kinds list. Peer
  mentions in a workgroup are intermediate activity — waking the
  user breaks the ``#task``/``#done`` autonomy model. The event
  still flows through the live subscription; inbox / unread surfaces
  can use it. Only the native banner is gone.

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
