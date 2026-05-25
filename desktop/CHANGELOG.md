# Desktop changelog

Release history for the Tauri desktop client. Tracked separately
from the alpi (CLI) [CHANGELOG.md](../CHANGELOG.md) — the two
products ship on their own cadence with their own version
schemes:

- alpi (CLI)  → ``vX.Y.Z`` (PyPI + GitHub release)
- desktop app → ``desktop-vX.Y.Z`` (GitHub release only)

The desktop app is a host-plane client of a local ``alpi``
daemon. Each release pins a minimum compatible alpi version.

## v0.3.18 — 2026-05-25 — Gmail paste fallback for cross-machine setups

0.3.17 fixed remote daemons by moving the OAuth loopback to
the desktop process. That still assumes the **desktop** and
the **browser** are on the same machine — which fails for
SSH X-forwarding, VNC, or Tauri running inside a VM/container
while you stare at it from your host. Added a paste escape
hatch alongside the loopback.

- A new "Browser on a different machine? Paste the callback
  URL" disclosure in the Gmail consent modal. Open the auth
  URL on whichever device has your real browser, copy the
  failed ``http://127.0.0.1:…/?code=…`` URL from the address
  bar, paste it back here, click "Use pasted URL". The desktop
  parses the URL and calls ``host.gateway.gmail.exchange``
  directly with the code+state.
- The loopback path is still the fast happy path — it just
  races the paste flow. Whichever finishes first wins; the
  loser hits "unknown or expired state" on the daemon and the
  client ignores it silently.
- New Tauri command ``gateway_gmail_paste`` plus a tolerant
  callback-URL parser (accepts a full URL or just the query).
  Unit tests cover both shapes plus whitespace trim and
  malformed input.

## v0.3.17 — 2026-05-25 — Gmail authorization works against remote daemons

The Gmail gateway modal used to lie ("Browser opened…") and
hang forever when the daemon was on another machine: the OAuth
loopback ran inside the daemon, unreachable from your browser.

- The loopback HTTP server now runs in the desktop process,
  not the daemon. The flow: bind a free port on this machine →
  ``host.gateway.gmail.begin`` returns the consent URL →
  system browser opens → callback hits the local loopback →
  ``host.gateway.gmail.exchange`` finishes the token exchange
  on the daemon. Works against a local or Umbrel/SSH daemon.
- The modal shows the consent URL inline while waiting, with
  a clickable link. If your default browser failed to launch,
  open the link in any browser **on this machine** — the
  loopback redirect is bound to ``127.0.0.1`` here, so opening
  the URL from your phone or another laptop won't reach back.
- The flow times out after 5 min if no callback arrives (closed
  tab, consent abandoned, etc.) instead of hanging the modal
  silently — error surfaces in the toast and the modal status.
- Requires alpi ≥ 0.6.9 (the new ``gmail.begin`` /
  ``gmail.exchange`` host methods).

## v0.3.16 — 2026-05-25 — launch with a dead daemon no longer blanks the window

Two real crashes plus a UX overhaul of the cold-start offline
path.

- **Fixed** the temporal-dead-zone crash from 0.3.15: the
  recents-fetch effect referenced ``hostConnections.active_id``
  before ``useHostConnections()`` had initialised it. Moved the
  effect below the hook.
- **Fixed** a settings-deeplink crash: a notification deep link
  with ``kind: "settings"`` and no profile used to set
  ``settingsTarget`` to ``null``, then ``activeProfile`` /
  ``activeSettingsWorkgroup`` dereferenced ``settingsTarget.kind``
  → ``TypeError``. ``resolveDeeplink`` now omits the field when
  there's no profile (convention: ``undefined`` = keep current
  target) and both useMemos use optional chaining.
- **Removed** the 2.5-second ``BootSplash`` grace. The shell now
  renders from the first frame — sidebar, chat pane, banner —
  while the active connection is being probed in the background.
  Same pattern the mobile client already uses.
- **Auto-open the connection switcher** once on cold-start when
  the active daemon's probe settles to ``offline`` or
  ``auth-failed``. Local daemons get the autostart attempt first
  and only fall through when autostart gives up. Remote daemons
  open the picker immediately on offline. Once-per-session via a
  ``useFireOnce`` hook so a later Tailscale blip can't re-pop the
  modal after the user has closed it.
- The offline ``Banner`` now also covers the
  ``autostartPhase === "starting"`` window with an info-toned
  "Starting local daemon…" message, replacing the part of the
  splash that used to mask it.

## v0.3.15 — 2026-05-24 — connection switch no longer leaks previous daemon's data

Two unrelated bugs collapsed into the same UX: switching from one
daemon to another (e.g. local → Tailscale) briefly showed content
that belonged to the previous connection.

Requires alpi ``v0.6.6`` or newer.

- New-chat view's "Recent chats" used to linger from the previous
  connection until something else forced a re-render. The effect
  that loads it only depended on ``view.kind``, so a connection
  switch (which keeps view kind as ``"empty"``) skipped the reload.
  Now it also depends on the active connection id and clears the
  list before the fetch so there is no flash of the previous
  daemon's sessions.
- ``host.events.subscribe`` cursor is now keyed by
  ``daemon:<device_id>`` instead of by connection id. Re-pairing
  the same daemon, or switching between LAN/Tailscale routes that
  point at the same daemon, no longer resets the event cursor.
  ``HostConnection`` carries the ``device_id`` captured from
  ``host.version`` during probe.

## v0.3.14 — 2026-05-23 — workspace edits stick + Browse hidden on remote

- The settings draft now merges baseline updates field-by-field
  only into fields the user has not touched. In-flight typing
  survives `config_changed` re-fetches, while async
  `host.profile.detail` arrivals (workspace + other heavy fields
  not present in `host.profile.summaries`) hydrate untouched
  fields correctly. Full reset still happens on profile or
  connection switch. Merge logic lives in `lib/profile-draft`
  with six regression tests.
- The Browse… button next to the workspace path opens the local
  Mac folder picker; on remote daemons (Tailscale / Umbrel) that
  path is meaningless. The button is hidden when the active
  connection is not local.

## v0.3.13 — 2026-05-22 — pair-then-cancel no longer silently un-pairs

The "Pair new device" modal used to revoke the freshly-generated
token whenever it closed via Cancel or the X — even when the phone
had already scanned the QR or pasted the link. Result: the phone
thought it was paired, the daemon no longer trusted its token, the
desktop list looked empty.

- Cancel now checks the daemon's view of the token. If the phone
  already touched it (``last_seen`` set), the device is kept and
  saved with whatever label you typed (or "Unnamed device" if
  blank); the list refreshes. Unused tokens still get cleaned up.
- Notification taps for ``agent.message`` payloads without a
  bound ``session_id`` now land on the profile's latest chat
  instead of doing nothing — the Rust side emits
  ``kind: "profile"`` and the JS consumer had no handler for it.
- New tests: ``lib/device-pair`` and
  ``hooks/useNotificationDeeplink``.

## v0.3.12 — 2026-05-22 — instant fire feedback

Requires alpi ``v0.6.3`` or newer.

- Pressing "Fire" on a schedule now shows an immediate
  ``Schedule X started`` toast instead of freezing for the full
  agent run (which could be 30s or more). The job's result still
  arrives through the usual notification, and a job that errors
  out is surfaced through the existing schedule failure path.

## v0.3.11 — 2026-05-22 — lighter tool-call activity

UI cleanup of the chat turn.

- The inline activity spinner inside a running tool row is gone —
  the existing accent-coloured pulse already says "this is the one
  running". One signal, not two.
- The "thinking…" indicator now only shows in the brief window
  between the user message and the first tool call (or first
  assistant text). Once a tool has started, the pulse takes over;
  once the assistant starts replying, the text itself does.

## v0.3.10 — 2026-05-22 — ESC closes every popover

UX polish for the in-app pickers.

- ESC now closes the Model picker, Accent color picker, and the
  generic Settings popover (Anchored / Popped). They used to only
  close on outside click — keyboard users had to grab the mouse.
- Outside-click and ESC handling unified across all popovers, no
  more ad-hoc listeners.

## v0.3.9 — 2026-05-22 — agent.message native notifications

Requires alpi ``v0.6.1`` or newer. The Tauri client now surfaces the
new ``agent.message`` host event as a native macOS / Windows / Linux
notification, so the agent reaching the user via
``send_message(channel="alpi")`` lands as a system banner without any
gateway involvement.

- ``dispatch_daemon_frame`` adds a match arm for ``agent.message``
  in ``src-tauri/src/notifications.rs``. Title falls back to the
  profile name when the payload omits it; body is the message text.
- Deep link: when the payload carries ``session_id``, tapping the
  notification routes to ``/chat/<session_id>`` on the active
  connection. Otherwise it lands on the profile.
- Empty-body events are dropped silently — no point waking the user
  for nothing.
- ``schedule.done`` success does not fire native notifications.
  Successful schedules that need to wake the user now do so through
  ``send_message(channel="alpi")`` / ``agent.message``; only
  ``schedule.failed`` wakes the user automatically.
- ``approval.request`` now also fires a native banner when the
  window is NOT focused. When the desktop window is in front, the
  existing in-app ``ApprovalSheet`` queue continues to own the
  flow — no double-notify. Title carries the severity (``caution``
  / ``danger``) and body shows the command or pattern that needs
  approval. Tap deep-links to ``/approval/<request_id>`` on the
  source profile.

## v0.3.8 — 2026-05-21 — reasoning effort in profile settings

Requires alpi ``v0.5.4`` or newer. On older daemons the row stays
hidden.

- Profile settings expose a reasoning effort dropdown
  (``Default / Low / Medium / High``) right under the model picker,
  for OpenAI o-series, Claude 3.7+ / 4+, Gemini 2.5+, DeepSeek R1,
  and any OpenRouter route.
- The row only appears when the picked model supports reasoning;
  swapping to an unsupported model clears the value automatically.
- Mid-chat model overrides from the composer don't carry effort.

## v0.3.7 — 2026-05-21 — approval modal for caution commands

Requires alpi ``v0.5.1`` or newer. On older daemons the modal stays
dormant.

- Caution commands (recursive `rm`, `sudo`, force-push, …) now open a
  modal with four choices: allow once, allow this session, always,
  deny. Previously these only worked from the TUI.
- The modal shows the command, profile, severity, and a live
  countdown to the daemon's auto-deny.
- Opening the app mid-prompt or switching to a connection that
  already has a pending prompt shows it immediately.

## v0.3.6 — 2026-05-21 — connection switch hardening + grouped tool calls

Requires alpi ``v0.4.52`` or newer. No daemon contract change.

- Connection switching is now atomic from the UI's point of view:
  local/remote changes reset the picker, reject stale reloads with a
  switch token, and load the incoming connection cache only after the
  active connection ref has flipped. This prevents the temporary
  "remote selected, local data visible" frame and avoids pruning the
  outgoing workgroup cache with the incoming workgroup list.
- Adjacent same-name tool calls collapse into a single row with an
  ``×N`` badge and per-call status dots. The row expands to show the
  individual calls without changing transcript data.
- Chat loading now renders a realistic user-bubble / assistant-line
  skeleton instead of an empty pane.
- The model override footer's ``Set default…`` action now opens the
  active profile settings.
- Added ``useHostConnections.test.js`` coverage for cache pruning,
  picker reset, and A→B→A stale reload rejection. 68/68 tests pass.

## v0.3.5 — 2026-05-20 — vitest harness + CreateWorkgroup crash fix, hub dropdown shows model, Field/Textarea primitives in modal

Requires alpi ``v0.4.52`` or newer (no daemon contract change vs.
v0.3.4). Layer-2 polish on top of the daemon migration: testing
infrastructure, a P0 crash in the workgroup creation modal, and a
handful of input/dropdown affordances aligned with the design spec.

**Tests.** Adds vitest (`vitest run` via `pnpm test`) with a jsdom
environment and a minimal Tauri mock (`@tauri-apps/api/core`,
`@tauri-apps/api/event`) in `vitest.setup.js`. New suites cover the
load-bearing paths the v0.3.4 migration introduced: `daemon-frame`
(pure mapper from raw daemon emits), `workgroup-fetch` (transcript
pagination contract: first fetch `tail=true`, subsequent
`after_seq`), `workgroup-cache` (per-`(connection, wg_id)` cache),
`useProfileDetail` (per-`(connectionId, profile)` cache invalidation
on config/gateway/peers events), `useNavListener` (tray nav payload
dispatch), and `useChatStream` (session_start pin, heartbeat no-op,
done clears unless an error landed, stale request_id dropped, 10s
stall watchdog replays sidecar and clears only on done, mid-replay
without done preserves preview). 65 tests, all green.

**CreateWorkgroupModal crash.** `+` from the sidebar threw
`ReferenceError: hub is not defined` — the render referenced a
`hub` object that lived only as a memo in an older revision. Restored
the derivation via `useMemo` from `hubProfile + eligibleHubs`. The
modal also adopts the design-system input primitives
(`Field`, `Textarea` with `.ds-field`) so the Name placeholder
vertical alignment matches every other input in the app; bespoke
`.input` / `.textarea` CSS removed from
`CreateWorkgroupModal.module.css`.

**Dropdown gains `trigger.trailing`.** New slot in
`primitives/Dropdown.jsx` for content that should sit right-aligned
in the trigger (mono, ink-3, margin-left:auto). Used by the hub
picker so the selected profile's model id renders inline next to
`@name` instead of stacked underneath via `caption`. The dropdown
row items keep `caption` to show the model under each `@name` in the
popover.

**Mid-stream cancellation correctness.** While auditing the test
suite, hardened `daemon-frame::fromDaemonFrame` to surface the same
shape regardless of which mutator emitted the event (test now pins
the contract instead of relying on the consumer to be tolerant).

Workgroup transcript refresh on `wg.post`/`wg.done` still flows
through `workgroup-fetch::fetchWorkgroupTranscript`, with
`useChatStream` driving session-detail reloads on `reply` (the
daemon emits `reply` before `done`, so the new transcript is on disk
by the time we refetch).

## v0.3.4 — 2026-05-20 — daemon v0.4.52 contracts: seq-only events, lite/detail profile, lazy skills body, transcript pagination, plus ConnectionPanel hydration fix and richer About macOS

Requires alpi ``v0.4.52`` or newer. Migrates every host-plane consumer
to the new daemon contracts: per-connection `seq` cursor with
subscribe-then-backfill, lazy `host.profile.detail` + `host.skill.read`
fetched per `(connectionId, profile)`, paginated workgroup transcript
with `tail=true` first-paint, `session_start` as the first chat frame.

**Event bus.** `subscribe_daemon_events` (Rust) opens the stream
first, then on the `subscribed` handshake pages from the previous
seq cursor and dedupes against the live overlap (bounded set of
1024 seqs). Closes the race where a frame fired between `history`
and `subscribe` was silently counted in the daemon's seq without
ever reaching the client. Per-connection cursor stays in a
`HashMap<connection_id, u64>` so daemon switches never replay
cross-host state.

**Daemon-event mapping.** `App.jsx::fromDaemonFrame` reacts to the
new emits the daemon now publishes on every mutator:
`config_changed`, `gateway_changed`, `peers_changed`,
`profile_changed`, `workgroup_changed`, `workgroup_members`,
`schedule.changed`. No more polling for these surfaces.

**`useProfileDetail(connectionId, name)`.** New hook with a
per-`(connectionId, name)` cache so two daemons with the same
profile name never bleed peers/models/mcps. Refetches on
`config_changed`/`gateway_changed`/`peers_changed` for that specific
(connection, profile). `App.jsx` calls
`invalidateProfileDetailCache(prev)` AND
`invalidateProfileDetailCache(active_id)` on connection switch —
events from the new daemon weren't received while we were elsewhere,
so anything cached for it is potentially stale. Consumers:
`ChatPane`, `ProfileDetail`, `CreateWorkgroupModal`,
`WorkgroupDetail`. `useHostConnections.reload` no longer merges
detail per-profile on every poll — hot path stays lightweight.

**`SkillsPanel`.** SKILL.md body is now fetched per-skill on demand
via `profile_skill_read` inside a `SkillDetailBody` child that owns
its own state in `useEffect` after mount. The previous shape — a
`fetchBody(...)` call inside `renderDetail` — tripped the React
"setState during render" warning and tore the tree (white flash on
open). The child receives `profile` + `skill` and swaps its body
when `skill.name`/`skill.categoryRaw` change.

**Workgroup transcript.** `workgroup_transcript({after_seq?, limit?,
tail?})` returns `{posts, next_seq}`. First fetch uses `tail=true,
limit=200`; subsequent fetches paginate with the cached `next_seq`.
`lib/workgroup-fetch.js` caches per `(connection, profile, wg_id)`
with merge-by-seq, and `invalidateTranscriptCache(connectionId)`
clears on connection switch.

**Chat replay.** `ChatEvent::SessionStart` is wired through Rust and
`useChatStream.js` so brand-new threads can be replayed via
`host.chat.events_since` after a silent stream — `pendingTurn.
sessionId` is pinned on the first frame, not on `reply`.

**Rust commands.** New `profile_detail`, `profile_skill_read`. The
existing `workgroup_transcript` now takes `(after_seq, limit, tail)`
and returns `{posts, next_seq}`.

**ConnectionPanel hydration fix.** The connection row was a `<button>` containing the `Forget` `<button>`, which React reported as invalid HTML nesting and the dev tree blanked on every mount. The row is now a `<div role="button" tabIndex={0}>` with explicit `onKeyDown` for Enter/Space; the `Forget` button stays a real `<button>` and the row's `onKeyDown` guards with `e.target !== e.currentTarget` so Enter while focused on `Forget` no longer also fires the row's `onPick`.

**About Alpi enriched.** The macOS app menu now mounts an explicit `Submenu` with `PredefinedMenuItem::about(Some(AboutMetadata))` populated from `Cargo.toml` + repo metadata: name, version, authors, copyright (`© 2026 Satoshi Ltd. · BUSL-1.1`), comments (tagline + description), website (`alpi.satoshi.ltd`), and license. `tauri.conf.json::bundle` also carries `publisher`, `copyright`, `category`, `shortDescription`, `longDescription`, `homepage`, and `macOS.minimumSystemVersion` so the bundled `.app` Info.plist + Spotlight/Launchpad surfaces pick the same values up.

**Tests + build.** `npm run build`: green (chunk-size warning is
pre-existing). `cargo test`: 10 passed.

## v0.3.3 — 2026-05-19 — clean schedule notifications + Ollama provider UI polish + network pairing settings

Requires alpi ``v0.4.51`` or newer (the release that ships the structured `schedule.done` payload, the `{models, errors}` envelope for `ollama_models`, and the `host.network.*` RPCs that the new Network panel consumes).

**Schedule notifications.** The notification handler now prefers `data.reply` as the body when present, drops the `<job_id>: silent run ok: ...` wrapper, and suppresses silent maintenance entirely.

- `src-tauri/src/notifications.rs` — `schedule.done`/`failed` branch reads `data.reply` first. Title becomes the bare profile name when content is present; falls back to `<profile> · schedule ran` (or `failed`) with `<job_id>: <message>` body when `reply` is empty (older daemons, failures, send_message self-delivered). Suppress entirely when `ok && data.silent === true` — silent maintenance never wakes the user. Uses the explicit `silent` boolean from the alpi payload, not string-matching on `message`. `delivered_to` is currently ignored: the desktop notifies whenever a `reply` is present, even on jobs also routed through Telegram/etc. (owned-client-first stance).
- Backward compatible: clients still get the legacy fallback when the daemon predates the structured payload.

**Ollama provider UI.** Surfaces partial discovery results, fixes a grouping foot-gun, and migrates new inline styles to CSS modules per repo rule.

- `src/features/ModelPicker.jsx` / `src/features/settings/fields/{ModelField,AddProviderField}.jsx` — `ollama_models` now returns `{models, errors[{name,url,detail}]}`; the UI consumes the envelope, falls back to the legacy bare array for older daemons, and renders unreachable instances inline (per-row in the editor, aggregate at the bottom of `ModelField` when picking a model) instead of silently dropping them.
- `src/features/ModelPicker.jsx` — model grouping discriminator is now the **exact model identity** (`ollamaModelSet.has(m)`), not the first path segment. An Ollama server happening to be named `openrouter` no longer relabels real `openrouter/...` models under `ollama/openrouter`.
- `src/features/settings/Settings.module.css` — four new utility classes (`warnBlock`, `warnBlockTight`, `warnLine`, `inlineRowWrap`) replace the inline `style={{ display: "block", marginTop: … }}` introduced in the same patch, keeping the file on the CSS-modules-only convention.

**Network pairing settings.** Parity with `alpi setup → devices → network` — pick Tailscale / LAN / Custom advertised host from the desktop instead of editing `config.yaml` by hand.

- `PairDeviceModal` shows the network character of the host as a chip (`TAILSCALE`, `LAN`, `CUSTOM`, `UMBREL`) with a scope-aware hint, instead of the procedural `CONFIGURED` value that leaked the resolution path to the UI. Driven by `host.devices.generate`'s new `scope` + `is_override` fields.
- New `NetworkField` in `Settings → Devices` (default profile, local connection) — Chip + popover with a 4-option segmented (Auto / Tailscale / LAN / Custom), per-mode hints showing the actual detected IPs, a Custom-only input for hostnames / MagicDNS / VPN IPs, the pairing name field, and a "Save and restart" action. Public IPs, loopback, multicast / link-local / reserved, and malformed hostnames are rejected by the daemon. Auto + unavailable detections are greyed out so the user only sees what the machine can actually reach.
- New Tauri commands `network_status`, `network_set_advertised`, `network_restart_host_server` (in `src-tauri/src/lib.rs`) thin-wrap the three `host.network.*` RPCs.

## v0.3.2 — 2026-05-18 — daemon version in connection metadata

Requires alpi ``v0.4.47`` or newer.

Small follow-up to the v0.3 shell rebuild.

- **Connection metadata.** The desktop probes `host.version` after a successful connection check and carries `alpi_version` through the cached connection state, redacted connection JSON, and `connection-status` events.
- **Connection switcher.** The connection panel now shows `v<version>` next to each host when the daemon reports it, making local/remote compatibility visible without leaving the app.
- **Pinned recency.** Pinned profiles and pinned workgroups now share one recency-sorted list, with incomplete/paused items still drifting after healthy entries.

`pnpm build` ✓; `cargo check` ✓.

## v0.3.1 — 2026-05-18 — sidebar text spec, frontend unread, design-token coverage

Requires alpi ``v0.4.46`` or newer.

Visual polish pass on the new shell.

- **Sidebar typography.** New `.sb-name` / `.sb-hash` / `.sb-ts` / `.sb-eyebrow` classes lock the row hierarchy (3 weights × 2 colors, `.is-sel` / `.is-unr` modifiers). Profile incomplete state: `[data-state="needs-provider"]` draws an outlined diamond, `var(--ink-3)` name, opacity .55, no `MuteIcon`. Workgroup paused: `[data-state="paused"]` just dims via opacity; the pause glyph already lives in the leading slot.
- **Unread (frontend-only).** New `hooks/useReadState.js` persists `last_read_at` per profile + workgroup in `localStorage`, scoped by active connection id. Rows compare against `latest_session.updated_at` / `workgroup.mtime` and swap the trailing timestamp for a pulse-dot tinted with the row's accent. Reading marker syncs with `recency` while the row is active.
- **Sidebar sort, uniform.** Pinned and unpinned sections now use the same rule: paused / incomplete drift to the end of their section, healthy items sort by recency desc.
- **Token coverage closed.** Added `--fw-regular/medium/semibold/bold`, `--lh-tight/cozy/normal/relaxed`, `--modal-sm/md/lg`, `--alpha-faint/disabled/muted/soft`, `--pop-xs`. Migrated 97 raw `font-weight`, 76 raw `line-height`, and the high-frequency `opacity` values (0.35 / 0.45 / 0.55 / 0.7) to tokens. Body `letter-spacing` `-0.003em` → `-0.005em` per spec.
- **Button system aligned to spec.** `.btn` / `.btn-primary` / `.btn-ghost` / `.iconbtn` / `.alink` in `design-system.css` snap to v3 spec (28h / 12px-x / gap 6, outline-based focus, active `translateY(.5px)` / `scale(.96)`). React `<Button>` gains `size="lg"` (32h) and `size="hero"` (40h × 20px-x); empty-state CTA uses `hero`. `.primary` variant flipped to solid `--ink` default → `--ink-2` on hover.
- **Pair-device flow.** `host_connection_add_remote` no longer auto-switches active connection; toast says `Paired <name>` (not "Connected" — pairing only registers, user still switches into it), input clears only on success, panel closes.
- **VersionButton.** Friendly updater errors (`No build available for your platform yet` / `Couldn't reach update server` / etc.) replace the raw stack. Popover at `--pop-xs` (220px) fits inside the sidebar.
- **Misc.** `ModelPicker` label strips the first `/` only so OpenRouter shows `stepfun/step-3.5-flash` instead of just `stepfun`. `ProviderPickerForm` placeholder uses the `current: <preview> (paste to replace)` pattern. The no-provider CTA now uses the larger `hero` button size, and the tray update icon was regenerated with a red bullet bottom-right.

`pnpm install --frozen-lockfile` clean; `pnpm build` ✓; `cargo check` ✓.

## v0.3.0 — 2026-05-18 — desktop shell rebuild + local voice + native notifications

Requires alpi ``v0.4.46`` or newer.

Large desktop refactor that turns the app into a cleaner host-plane client with a stronger visual system, native notification hooks, and local voice playback.

- Rebuilds the React surface around `features/`, `pages/`, and shared `primitives/`, replacing the older `components/` layout while keeping the client on daemon-host verbs only.
- Refreshes the Alpi brand assets, Tauri icons, sidebar, settings shell, browse panels, chat headers, empty states, command palette, and shared design tokens.
- Adds desktop-local TTS: the renderer calls a Rust Edge TTS WebSocket implementation (`desktop/src-tauri/src/tts.rs`) and plays audio locally. The daemon no longer brokers playback; `host.tts.synthesize` is gone.
- Adds native desktop notifications for completed sessions, workgroup completions, schedules, budget thresholds, and daemon disconnects, with focus-aware suppression for the active conversation.
- Adds local daemon autostart/retry handling, sharper offline banners, and notification deeplinks back into chat, workgroups, or settings.
- Expands Settings with structured profile/workgroup detail views, gateway setup fields, budget editing, MCP configuration, schedule summaries, service controls, peer/workgroup management, and voice preview.
- Improves streaming recovery UI by deduplicating repeated `tool_start` frames and keeping heartbeat/replay behavior compatible with the daemon event sidecar.

## v0.2.18 — 2026-05-14 — shared scaffold for Skills/Tools/Memory + typography pass

Requires alpi ``v0.4.36`` or newer.

- Skills/Tools/Memory panels share a single scaffold via new `BrowseDetail` + `MarkdownBody` primitives. Their list rows match the chat + settings sidebar items.
- Detail content uses monospace; sidebar and search input stay in the UI font. Inline code loses its grey pill background.
- Tool descriptions render inline markdown (`**bold**`, `` `code` ``) without changing the source — keeps system-prompt tokens cheap.
- Row selection only on click — no hover hijacking.
- `letter-spacing` removed from every CSS module under `desktop/src/`.

## v0.2.17 — 2026-05-14 — tray update badge + sticky settings sidebar + sharper empty-state logo

Requires alpi ``v0.4.36`` or newer.

- Tray gains a `tray-template-update.png` variant; `tray.rs::refresh_icon` swaps it in when `tray_announce_update` fires. The update variant runs in non-template mode (`set_icon_as_template(false)`) so its red badge dot keeps its color instead of being retinted by macOS.
- Tray base icon now ships from `assets/alpi-trayicon.png` (alpaca head, 64×64 RGBA, transparent background) instead of the prior bespoke `tray-template.png`.
- "Connection" label moved inside `ConnectionSwitcher` itself — both the chat sidebar and the settings sidebar now render an identical block (label + dropdown) without each parent providing its own duplicate label markup.
- Settings sidebar refactored into a 3-zone flex column. Connection at top and `VersionFooter` at bottom stay pinned; only the profiles/workgroups list scrolls. Matches the chat sidebar's pinned-connection behavior. Footer padding bumped from `--space-4` to `--space-6` so it no longer hugs the bottom-left edge.
- `.sectionLabel` / `.asideTitle` lose `letter-spacing` — used design tokens only, no bespoke spacing.
- Empty-state logo loses its `opacity: 0.85` — the CSS-mask + `currentColor` combo already adapts per theme; the extra opacity washed the llama out in dark mode.

## v0.2.16 — 2026-05-13 — chat reconnect-on-stall

Requires alpi ``v0.4.36`` or newer.

Fixes the freeze where a chat UI hangs forever after the host-plane stream socket dies mid-turn. The turn still completes on disk; v0.2.16 lets the desktop notice the silence and rebuild from the daemon's sidecar.

- New `chat_events_since` Tauri command + watchdog in `useChatStream`: after 10s of silence on a pending turn, replay the sidecar and reconstruct tools / deltas / reply.
- Two toasts mark the cycle: "Stream went silent — reconnecting…" → "Reconnected — turn recovered from disk".
- New `ChatEvent::Heartbeat` variant carries the daemon's 5s keepalive through to React so long tool calls don't trip the watchdog falsely.
- New sessions (no `session_id` at send time) are skipped — the failure mode is existing-session continues, which is fully covered.

## v0.2.15 — 2026-05-13 — Apple Developer ID signing + notarization

Requires alpi ``v0.4.30`` or newer.

First release built and shipped through the Apple Developer ID notarization path. No host-plane API or UX changes — purely the build/distribution side going live, so existing users on v0.2.12 will see the same app, just signed and notarized.

- ``desktop/src-tauri/tauri.conf.json`` declares ``macOS.hardenedRuntime: true`` with ``entitlements: null`` — Tauri 2 signs with hardened runtime and ships a Gatekeeper-friendly DMG.
- ``.github/workflows/publish-desktop.yml`` gates releases on every signing + notarization secret, scopes the Apple credentials to the macOS matrix job only, and owns notarization end-to-end with five defenses: (1) ``openssl pkcs12 -info`` + ``security import`` validate the cert before the expensive Tauri build; (2) ``xcrun notarytool history`` round-trips ``APPLE_ID`` / ``APPLE_PASSWORD`` (app-specific) / ``APPLE_TEAM_ID`` through Apple's notary so wrong creds fail fast; (3) explicit ``xcrun notarytool submit --wait`` + ``stapler staple`` after the build, because ``tauri-action`` v0.6.2 signs but does not auto-notarize; (4) ``gh release upload --clobber`` re-uploads the stapled DMG so users download the bytes that Apple actually registered (without it, ``tauri-action``'s pre-notarize upload is what lands on the release); (5) ``spctl --assess --type install`` runs against the published DMG and fails the workflow if Gatekeeper rejects.
- Linux job hardened so ``apt-get install`` can't hang the matrix: ``DEBIAN_FRONTEND=noninteractive``, ``NEEDRESTART_MODE=a``, a 10-minute step timeout, and a swap to ``libayatana-appindicator3-dev`` (the maintained drop-in for the legacy ``libappindicator3-dev`` whose postinst can stall on 22.04).
- ``publish-release`` step uses ``gh release edit --tag --draft=false`` (with ``set -euo pipefail``) instead of ``gh api -X PATCH .../releases/$id`` — the latter died in <1s on workflow re-runs because the stale ``check-version`` output left ``release_id`` empty.
- ``desktop/RELEASING.md`` documents the Developer ID certificate, app-specific password, signing identity, and Team ID setup so future desktop releases stay reproducible.
- ``tests/core/test_desktop_release_workflow.py`` locks the workflow shape: version sync, hardened-runtime config, every required secret present, Apple secrets scoped to macOS only, and the five notarization defenses (cert verify, notarytool credential round-trip, explicit notarize+staple ordered between build and Gatekeeper, stapled-DMG re-upload before Gatekeeper, Gatekeeper assess).

## v0.2.12 — 2026-05-12 — auto-compact surfacing in the context bar

Requires alpi ``v0.4.30`` or newer.

Surfaces the new auto-compact pipeline in the desktop chat. The context bar in the header gets a tooltip explaining that Alpi auto-compacts when the window fills up, and ``auto_compact`` events stream into the active turn as a discrete tool card.

- Adds the ``auto_compact`` variant to ``ChatEvent`` (Rust + JS) with ``tokens_before`` / ``tokens_after``.
- Tooltip primitive used in the header context bar with a single-line note (the percentage and token counts stay inline).
- ``useChatStream`` renders incoming compaction events as an ``auto-compact`` tool card inside the running turn.

## v0.2.11 — 2026-05-12 — chat concurrency: interrupt-and-replace on the same session

Requires alpi ``v0.4.29`` or newer.

Fixes the case where sending a new prompt while the previous response
was still streaming could mix frames from both turns on the desktop
chat surface.

- Chat events now carry ``request_id`` so stale ``interrupted``, ``reply``, and ``done`` frames from the cancelled turn are ignored.
- Re-sending on the same session now cleanly interrupts and replaces the previous turn instead of letting both streams update the same pending message.
- Pending-turn cleanup is scoped to the active request, so sidebar and tool-panel refreshes no longer clear the wrong in-flight reply.

## v0.2.10 — 2026-05-12 — browse panels (tools / skills / memory) + palette org

Requires alpi ``v0.4.27`` or newer.

- Adds browse panels for Tools, Skills, and Memory using host-plane data only.
- Adds shortcuts for browse and create actions and folds them into the command palette.
- Reorganises palette groups so navigation and read-only inspection are easier to reach.

## v0.2.9 — 2026-05-11 — command palette + global summon + Esc cascade

Requires alpi ``v0.4.24`` or newer.

A keyboard-navigation pass: desktop gets a real command surface, a
global summon shortcut, and predictable Escape handling across
search, dropdowns, modals, and the chat stream.

- Adds a command palette with grouped actions, keyboard hints, and jump shortcuts for the first visible profiles and workgroups.
- Adds global ``⌘⇧A`` to show or hide the app window from anywhere on macOS.
- Normalises Escape handling so overlays close first and only then fall through to turn cancellation.
- Adds find-bar ``⌘G`` / ``⌘⇧G`` navigation and makes shortcut hints consistent through the shared ``<Kbd>`` primitive.
- Cleans up desktop release workflow races around release creation and updater metadata.

## v0.2.8 — 2026-05-11 — find-in-transcript + shortcut system + flat focus

Requires alpi ``v0.4.24`` or newer.

Focuses on making the app faster to drive from the keyboard and less
visually noisy while reading long transcripts.

- Adds in-chat transcript search with keyboard navigation, match counters, auto-scroll, and highlight ranges that survive message re-renders.
- Expands the shortcut system with smarter ``⌘,`` / ``⌘N`` behavior, Settings-aware jump targets, and shared ``<Kbd>`` rendering.
- Adds identity drafting in Settings through ``host.identity.draft``.
- Moves message hover controls and loading skeletons toward CSS-driven behavior to reduce chat-surface churn.
- Tightens the visual system toward flatter focus states and more consistent scrollbars, accents, and message chrome.

## v0.2.7 — 2026-05-10 — UX polish pass + design system tightening

Requires alpi ``v0.4.21`` or newer.

- Adds stop-during-streaming, keyboard navigation, and stronger first-run / offline states.
- Renames the bundled profile to render as ``@alpi`` in the UI.
- Improves skeletons, notification dedupe, and status affordances.
- Tightens the design system around tokens, buttons, and composer behaviour.

## v0.2.6 — 2026-05-09 — Devices section closes `alpi setup` parity

Requires alpi ``v0.4.19`` or newer.

- Adds a Devices section in Settings for local-only pairing administration.
- Supports listing, revoking, and generating device links or QR codes from the desktop UI.
- Keeps remote connections out of the pairing-admin path by design.

## v0.2.5 — 2026-05-09 — Gmail OAuth in Settings, refresh button, gateway validation

Requires alpi ``v0.4.18`` or newer.

- Adds Gmail OAuth from Settings through the host plane.
- Adds a manual refresh action for the current profile or workgroup.
- Tightens gateway validation and fixes a few settings-editing UX issues.

## v0.2.4 — 2026-05-08 — pooled remote WebSocket + high-latency stability

Requires alpi ``v0.4.16`` or newer. ``v0.4.17`` is recommended.

Targets the remote-connection lag seen on high-latency Tailscale links,
where every ``host.*`` call was paying a fresh TCP + WebSocket + auth
handshake.

- Reuses one authenticated WebSocket per remote connection for normal request/response RPCs.
- Keeps chat streams and liveness probes on dedicated sockets so a long stream or slow probe cannot block ordinary UI calls.
- Adds more realistic remote read/probe budgets, TCP keepalive, and a small retry path for transient probe failures.
- Makes cold start and dropdown checks incremental instead of probing every stored connection before the UI can move.
- Clears stale chat state when switching into an offline remote connection.

## v0.2.3 — 2026-05-07 — connection health and offline handling

Requires alpi ``v0.4.10`` or newer.

**Connections**

- Connection state is tracked per host with explicit online, probing,
  offline, and auth-failed states. Opening the connection dropdown no
  longer blocks on checks; inactive connections are probed in the
  background and offline connections remain visible but are not
  selectable.
- Switching hosts clears the active chat state immediately and does
  not leak cached sidebar content from the previous connection when
  the selected host is offline.
- Remote endpoints use stored IP addresses directly, avoiding
  hostname / mDNS resolution stalls in the desktop transport.

**Offline UX**

- The main pane shows an offline banner for unreachable active
  connections while keeping Settings reachable.
- Connection status changes no longer emit desktop notifications.

**Performance**

- The sessions dropdown loads recent sessions first and only requests
  the full session list when the user searches.

## v0.2.2 — 2026-05-06 — remote host switching, rewrite-in-place, release path cleanup

Requires alpi ``v0.4.6`` or newer.

This release turns the desktop into a real multi-host client instead
of a local-socket-only shell, finishes the "rewrite from here" chat
flow, and closes the release/update path so the app and the public
site can both point at a stable desktop artifact.

**Connections**

- Desktop can now keep multiple host-plane connections and switch
  between the local Unix socket and paired remote daemons. The new
  ``ConnectionSwitcher`` lives in the sidebar and in Settings instead
  of the header, so connection state no longer competes with session /
  model controls.
- Pairing UX is desktop-first: remote connections are stored in the
  Tauri layer and can be forgotten explicitly. Revoked devices are no
  longer treated as healthy/selectable forever.

**Chat + workgroups**

- ``Rewrite from here`` no longer opens a fresh session. Desktop now
  hides the selected turn and everything after it, seeds the composer,
  and only truncates the real session when the rewritten message is
  actually sent.
- Requires ``alpi v0.4.6`` because the host plane now accepts
  ``rewrite_from_turn`` when resuming a chat session.
- Message action footers, tool rows, and workgroup markers were
  tightened so the layout behaves like one system: shared icon
  primitive, shared row primitive, shared spacing/radius/motion
  tokens, consistent hover/focus rules, and smaller hot-path render
  cost in the message stream.

**Updates + distribution**

- Settings now exposes update state directly: ``check for updates``
  and, when a release exists, ``install X.Y.Z``. The tray remains a
  secondary surface instead of the only install path.
- Desktop release pipeline now republishes stable aliases under
  ``desktop-latest`` for both the updater and the site:
  ``latest.json``, ``alpi-latest.dmg``, and
  ``desktop-release.json``.
- The site landing page reads desktop version from
  ``desktop/src-tauri/tauri.conf.json`` and links its macOS button to
  the stable ``alpi-latest.dmg`` URL instead of a tag page.

## v0.2.1 — 2026-05-05 — pin / show-more sidebar, auto-grow textarea, streaming perf

Requires alpi ``v0.4.0`` or newer (unchanged from v0.2.0 — no new
daemon verbs). Iterative release: user-visible additions in the
sidebar and Settings, a shared row primitive that unifies both
surfaces, and a perf pass on the chat streaming hot path.

**Sidebar**

- Pin / unpin profiles and workgroups. Hover a row → animated thumbtack slides in from the right (220 ms cubic-bezier); the timestamp / status tag fades out simultaneously so the action area is clean. Pinned items leave their original list and live in a top **Pinned** section. State persisted to ``localStorage`` under ``alpi.sidebar.pinned``.
- ``Show N more`` button when alpis don't fit the available height. The cap is computed from measured DOM heights (no hard-coded constants) — pinned section, workgroups section, alpis label, and the show-more wrap each have a ``ResizeObserver``; the alpis cap is whatever fits the remaining space. Workgroups are always visible without scroll.
- Hovering a profile dot reveals its ``public_bio`` in a tooltip — quick read of who each peer is without entering the chat.

**Settings**

- ``Textarea`` primitive auto-grows with content (briefing, identity, env vars, pubkey). Replaces five raw ``<textarea>`` instances; preserves the ``rows`` attribute as a minimum height.
- Aside padding aligned with the chat sidebar so the two surfaces share a consistent visual baseline. Both now share a single ``NavRow`` primitive so visual differences cannot drift in the future.

**Primitives**

- ``NavRow.jsx`` — shared sidebar row used by both ``Sidebar`` and ``Settings`` aside. Slots for ``leading`` (``Dot`` / ``Hash`` helpers exported), ``trailing``, plus ``active`` / ``accent`` / ``muted`` props. Memoized.
- ``Textarea.jsx`` — auto-grow textarea (offsetHeight on first paint as min, then ``scrollHeight`` per change).
- ``Button.jsx`` — new ``size="xs"`` variant (``--control-height-xs: 22px``) for the in-row pin action.

**Performance**

- Streaming deltas (``assistant_delta`` / ``reasoning_delta``) are now ``requestAnimationFrame``-batched in ``App.jsx``: each chunk appends to a buffer ref; a single ``setPendingTurn`` flushes accumulated text on the next frame. Caps chat re-renders at ~60 fps; previously 100+ during fast streams kept the sidebar / settings hover sluggish.
- ``ProfileRow`` / ``WorkgroupRow`` wrapped in ``React.memo`` with stable callbacks (``onOpen`` / ``onTogglePin`` passed through ``App``'s existing ``useCallback``s; per-row binding is ``useCallback`` on the row itself). New ``hubAccentByProfile`` lookup in ``Sidebar`` replaces a per-workgroup ``profiles.find()`` so memoised rows can bail on shallow compare.
- ``NavRow`` / ``Dot`` / ``Hash`` / ``Message`` / ``Turn`` / ``ToolCard`` all wrapped in ``React.memo``.
- ``ChatPane.jsx`` — ``Turn`` keyed by ``turn.at`` (microsecond timestamp) instead of array index; ``ToolCard`` keyed by ``tool_id`` with a name-index fallback for legacy tools.

## v0.2.0 — 2026-05-03 — host-plane only profile state

Requires alpi ``v0.4.0`` or newer.

- Desktop profile-state reads now go through the daemon's ``host.*``
  device-state verbs: profiles, summaries, skills, storage, gateway
  views, workgroups, workgroup members, bounded file reads, and
  config field mutations.
- ``desktop/src-tauri/src/state.rs`` no longer mirrors profile parsing
  logic in Rust. The app remains a client of the host plane instead of
  a second reader of ``~/.alpi``.
- This is an architectural release: the same daemon verbs are suitable
  for the mobile companion, so desktop no longer owns a private state
  contract.

## v0.1.0 — 2026-05-02 — first public desktop release

First Tauri client landed. Requires alpi ``v0.3.9`` or newer for
the host-plane control API.

- New Tauri 2 desktop client under ``desktop/`` — Rust + React + plain JS (no TypeScript). Talks to the daemon through the host plane on the local Unix socket; does not run an LLM, does not own tools, does not duplicate security.
- Settings: ``Services`` section with ``subsystems`` chips, ``gateways`` chips (disabled when ``gateway`` service is off), ALP identity / peers / workgroups, ``Schedule`` section with one row per job (Fire / Enable / Disable / Delete + state bullet).
- Subsystem toggles, TCP port edits, gateway saves auto-restart the daemon (``host.daemon.restart``) so the change applies without a manual nag.
- ``@<peer>`` mentions in chat go through the same host-plane shortcut, persisted as a real session turn so the desktop's tool card survives the round-trip.
- Tray icon, native window, signed auto-update through the Tauri updater (manifest at ``releases/download/desktop-latest/latest.json``, minisign-verified against the public key embedded in ``tauri.conf.json``).
