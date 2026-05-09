# Desktop changelog

Release history for the Tauri desktop client. Tracked separately
from the alpi (CLI) [CHANGELOG.md](../CHANGELOG.md) — the two
products ship on their own cadence with their own version
schemes:

- alpi (CLI)  → ``vX.Y.Z`` (PyPI + GitHub release)
- desktop app → ``desktop-vX.Y.Z`` (GitHub release only)

The desktop app is a host-plane client of a local ``alpi``
daemon. Each release pins a minimum compatible alpi version.

## v0.2.5 — 2026-05-09 — Gmail OAuth in Settings, refresh button, gateway validation

Requires alpi ``v0.4.18`` or newer (new ``host.gateway.gmail_authorize``
stream verb).

**Gmail OAuth flow lives in the desktop now.** The Gmail row in
``Settings → Services → gateways`` previously dead-ended on a "run
``alpi -p <name> setup`` from the shell" message — Gmail was the one
gateway that couldn't be configured from the app because it needs an
interactive browser handshake. The new ``GmailAuthModal`` drives the
full flow: Client ID + Secret + Allowed senders inputs (hydrated from
``host.gateway.config``, secret shown as ``current: … (paste to
replace)`` mirroring Telegram/IMAP), an Authorize button that streams
``host.gateway.gmail_authorize``, and a status line that updates as
events arrive (``Browser opened — complete the Google consent flow…``
→ ``Authorized as <email>``). Re-authorize without re-typing the
secret works because the host verb falls back to the stored value
when the input is blank.

The Authorize button is disabled while the OAuth is in flight and
the Close button becomes ``Cancel`` so the modal is never trapped in
a busy state — closing the browser tab without completing consent
no longer leaves the modal spinning forever (closes the modal; the
daemon-side ``first_run`` thread eventually times out at its 5-min
budget).

**Refresh button in the header.** New ``RefreshIcon`` primitive plus
a ``Button`` in ``AppHeader``'s right cluster, only visible while
``view.kind === "settings"``. Click reloads ``profile_summaries`` /
``workgroups`` and bumps a tick that re-keys the ``ProfileDetail`` /
``WorkgroupDetail`` subtree, forcing every child that fetches its own
data via ``invoke`` (gateways, skills, schedules, storage…) to
re-fetch. The Lucide refresh-ccw glyph spins while in flight via the
``AppHeader.module.css`` ``spin`` class.

**Required-field validation in the gateway editor.** The IMAP /
Telegram / Matrix modal previously called the ``provider_set_key``
chain even when half the required fields were empty, declared
``saved · daemon restarting``, and the gateway then sat dead in the
chip strip with no error. ``GATEWAY_FIELDS`` now carries a
``required`` flag per field; ``save()`` short-circuits with
``Missing required: …`` when the resulting state would leave any of
them blank (a stored secret counts as filled, so editing one
non-secret field doesn't force the user to retype the secret). Each
required field gets a ``*`` next to its label in the modal.

## v0.2.4 — 2026-05-08 — pooled remote WebSocket + high-latency stability

Requires alpi ``v0.4.16`` or newer (server multi-message support).
Recommended ``v0.4.17`` for short peer-ping timeout.

The motivating bug: a peer running on Tailscale Hua Hin → Chiang Mai
(~414 ms RTT measured, jittery) made the desktop feel unusable —
clicking that connection lagged for seconds and the status would
mark it offline despite the daemon being reachable. Root-cause audit
found four converging issues; this release fixes all of them.

**Pooled WebSocket per remote.** Every ``host.*`` call used to open a
fresh WebSocket — TCP connect + HTTP/1.1 Upgrade + auth handshake on
every IPC, ~3.5 RTTs of overhead per call. ``call_remote_inner`` now
keeps a single ``Arc<Mutex<WsClient>>`` per remote in
``remote_ws_pool()`` and reuses it for subsequent calls. Each request
carries a unique id (``next_request_id()``) and ``WsClient::request``
filters incoming frames by that id so concurrent callers can serialise
on the same WebSocket without confusing responses. App-level RPC
errors (``alp -3200X``) leave the WS intact and keep the pool entry;
transport errors (``websocket closed``, ``connect ws://...``,
``set read/write timeout``) drop the entry and trigger one retry on a
fresh WebSocket. Auth failures revoke the connection at the higher
level (``mark_connection_revoked``) which evicts all pool entries for
that id. Streams (``call_stream_remote``) and probes
(``call_remote_once``) keep dedicated WebSockets — the server
processes one message at a time per WS, and a long stream or slow
probe must not block normal RPCs that share the pool.

**Per-stage timeouts in ``WsClient::connect``.** A single timeout used
to cover TCP connect + WS handshake + first read. ``connect`` now
takes separate ``connect_timeout`` (4 s) and ``read_timeout`` so the
budget is realistic for each phase.

**Bumped budgets for remote calls.** ``READ_TIMEOUT_REMOTE_SECS``
8 → 20; ``PROBE_REMOTE_TIMEOUT_MS`` 3500 → 8000. Local UnixStream
calls keep the tight 8 s budget.

**TCP keepalive + ``TCP_NODELAY``.** Every remote socket sets
``set_nodelay(true)`` (Nagle was eating ~40 ms/RTT on chatty WS
handshake) and ``TCP_KEEPALIVE`` (idle 30 s + interval 10 s), so
silently-broken Tailscale tunnels are caught in ~60 s instead of
waiting for the 600 s stream read deadline. Added ``socket2`` as a
direct dependency (already transitive of Tauri).

**Sticky offline status.** ``STICKY_OFFLINE_THRESHOLD = 2`` —
``set_status`` only publishes Online → Offline after two consecutive
failure observations. Online resets the counter; AuthFailed and
Probing transitions stay immediate. Absorbs routine packet loss
without delaying real outage detection.

**One retry on probe failure.** ``probe_connection`` retries once
after a 350 ms delay for remote connections (skipped on auth-failed
and on local probes).

**Synchronous probe command for connection switches.** New Tauri
command ``host_connection_probe(id) → string``. The React-side
``onSetHostConnection`` flow now: optimistic ``probing`` flip + cache
load → ``set_active`` → fire-and-forget ``host_connection_probe`` →
the ``connection-status`` event listener and ``activeStatusKey``
effect take over. The intermediate ``reloadConnections()`` between
``set_active`` and the probe is dropped — it returned the stale
in-memory status and woke the effect into firing ``reload()`` against
a potentially-offline remote.

Tests: ``host_client.rs`` adds six new tests covering the sticky
threshold (``sticky_offline_holds_until_threshold``,
``sticky_offline_resets_on_recovery``,
``auth_failed_is_not_subject_to_sticky_threshold``), the eviction
decision logic (``should_retry_remote_ws_distinguishes_transport_from_app_errors``,
``is_app_error_only_matches_alp_rpc_errors``), and the pool eviction
policy (``pool_survives_app_error_but_drops_on_transport_error``).

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
