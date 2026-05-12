# Desktop changelog

Release history for the Tauri desktop client. Tracked separately
from the alpi (CLI) [CHANGELOG.md](../CHANGELOG.md) — the two
products ship on their own cadence with their own version
schemes:

- alpi (CLI)  → ``vX.Y.Z`` (PyPI + GitHub release)
- desktop app → ``desktop-vX.Y.Z`` (GitHub release only)

The desktop app is a host-plane client of a local ``alpi``
daemon. Each release pins a minimum compatible alpi version.

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
