# Desktop changelog

Release history for the Tauri desktop client. Tracked separately
from the alpi (CLI) [CHANGELOG.md](../CHANGELOG.md) — the two
products ship on their own cadence with their own version
schemes:

- alpi (CLI)  → ``vX.Y.Z`` (PyPI + GitHub release)
- desktop app → ``desktop-vX.Y.Z`` (GitHub release only)

The desktop app is a host-plane client of a local ``alpi``
daemon. Each release pins a minimum compatible alpi version.

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
