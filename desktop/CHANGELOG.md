# Desktop changelog

Release history for the Tauri desktop client. Tracked separately
from the alpi (CLI) [CHANGELOG.md](../CHANGELOG.md) — the two
products ship on their own cadence with their own version
schemes:

- alpi (CLI)  → ``vX.Y.Z`` (PyPI + GitHub release)
- desktop app → ``desktop-vX.Y.Z`` (GitHub release only)

The desktop app is a host-plane client of a local ``alpi``
daemon. Each release pins a minimum compatible alpi version.

## v0.4.4 — 2026-06-29 — Settings in one round-trip; bounded remote concurrency

_Requires alpi v0.10.1+._

- **A profile's Settings now load in a single request** instead of six — much
  snappier over a remote connection. Cached settings paint instantly and
  refresh in the background; a section that fails falls back on its own without
  blanking the rest.
- **Per-connection request limit:** the app caps how many requests are in
  flight to any one remote daemon, so opening Settings (or juggling many
  remotes) can't flood a connection. The local daemon and live event streams
  are unaffected.
- **Gentler reconnection to offline remotes:** retries back off from 4s up to
  60s with a little jitter instead of a fixed drumbeat, and stop entirely for a
  connection whose pairing was revoked until you re-pair it.

## v0.4.3 — 2026-06-29 — Lighter event handling, self-healing reconnects

_Requires alpi v0.10.0+._

- **Daemon events flow through one shared listener** instead of several, so
  reconnects and event bursts do less redundant work.
- **Event delivery self-heals:** if the app ever fails to attach its listener
  it retries on its own, instead of going quiet until you navigate away.
- **The local settings screen makes a single network probe** instead of three.

## v0.4.2 — 2026-06-28 — Settings panels load in parallel

_Requires alpi v0.10.0+._

- **Remote settings panels no longer stall behind one slow request.** Each
  field now talks to the daemon independently, so a slow fetch no longer holds
  up the rest — profile and workgroup settings open noticeably faster over a
  remote connection.
- **The sync bar sits in a fixed slot beneath the header** so the page no
  longer jumps when a refresh starts or finishes.
- **Usage and Schedule sections show a "loading…" hint** while they fetch
  instead of appearing empty and popping in a moment later.
- **Switching connection shows "Fetching latest settings…"** for the selected
  profile instead of a misleading "No selection" while the new daemon answers.

## v0.4.1 — 2026-06-28 — Settings stay responsive across connections

_Requires alpi v0.10.0+._

- **Profile settings render from cache immediately, then refresh in the background.**
  Usage, email accounts, paired devices, schedules, storage and workgroup
  members no longer blank out while a remote daemon answers over Tailscale.
- **Settings now shows the same indeterminate sync bar used by chat refreshes**
  while profile/workgroup data is being fetched.
- **Multi-connection settings calls are scoped to the selected daemon.**
  Workgroup lists, creation, member reads, actions, transcript fetches, storage
  and profile file reads now pass the active connection explicitly instead of
  falling back to whichever daemon was globally active.
- **Temporary offline probes keep the last good profile/workgroup cache visible**
  and only clear the view on authentication failure.

## v0.4.0 — 2026-06-26 — Gateways are now Email

_Requires alpi v0.10.0+._

- **Email is its own settings section, below MCP Servers.** Add IMAP and Gmail
  accounts directly — pick the type, fill the form, save. There's no separate
  "Gateways" panel anymore.
- **Each account is a pill labelled by its address.** Click one to edit it,
  test the connection, or remove it; the editor header shows whether the account
  is currently reachable.
- **Chat gateways are gone.** Telegram and Matrix have been removed — alpi
  v0.10 dropped the chat-app integrations entirely.
- **The per-profile "gateway" subsystem toggle is gone.** The daemon no longer
  runs a gateway subsystem, so there's nothing left to switch on or off.
- **Gmail still uses OAuth** — authorize when adding an account; edit its client
  id/secret later without re-authorizing.

## v0.3.87 — 2026-06-26 — chat: a busy chat tells you, instead of cancelling

_Requires alpi v0.9.35+._

- **Sending a message into a chat that's still working no longer cancels the running
  turn.** You get a "a turn is already running" notice; only Stop cancels. The
  in-progress work keeps going and finishes.
- **A chat that errored can be used again immediately** — no more getting stuck on
  "a turn is already running" after a failed turn.

## v0.3.86 — 2026-06-26 — chat: run several conversations in parallel

_Requires alpi v0.9.30+._

- **Start a new chat without interrupting the one already running.** Every chat
  — including separate sessions of the same agent — now streams on its own.
  Kick off a long turn in one, switch away and ask something else in another,
  and both keep working at the same time.
- **A live turn stays in its own chat.** Switching sessions while a reply is
  streaming no longer shows that reply's tool output in the chat you opened; it
  reappears, up to date, when you switch back.
- **Each chat has its own stop control**, and the sidebar marks every agent
  that's currently working.

## v0.3.85 — 2026-06-25 — loading & error states across modals and settings

_Requires alpi v0.9.30+._

- **Browse modals (memory, skills, tools) show a progress bar while loading** and
  a clear error state if the daemon can't be reached — no more blank pane.
- **Settings fields (model, storage, peers, workgroups) surface their own loading
  feedback** and cancel cleanly when you switch profiles, so you never see stale data.

## v0.3.84 — 2026-06-25 — memory + tools: monospace, spec-sheet reading view

_Requires alpi v0.9.30+._

- **Memory files (AGENT / MEMORY / USER) now render as formatted markdown** —
  headings, bold, lists and tables — in a monospace, spec-sheet style, instead
  of raw text.
- **Tool reference descriptions now render in that same monospace style.**

## v0.3.83 — 2026-06-24 — skills modal: consistent chips + source-style file viewer

_Requires alpi v0.9.30+._

- **A skill's tools, platforms and keywords render as consistent monospace
  chips** — alpi's built-in tools first, MCP tools last (shown as
  `server.tool`).
- **Skill files (SKILL.md, scripts, configs) show as monospace source** in
  the viewer, so you read them as code.
- **The file tree is rooted at `files`** instead of repeating the skill name.

## v0.3.82 — 2026-06-24 — notification severity at a glance + tidier reading view

_Requires alpi v0.9.30+._

- **Warning and error notifications stand out.** The list shows a coloured
  dot next to the time, and the open notification shows an error/warning
  chip beside the date.
- **The notification title now has matching top spacing** instead of
  hugging the header.
- **List previews drop emoji** for a cleaner one-line summary — the full
  notification keeps its 🔴🟡🟢 status markers.

## v0.3.81 — 2026-06-24 — report-grade notification reading view

_Requires alpi v0.9.30+._

- **Notifications now render as a clean report.** Long agent summaries get a
  title, section headings and scannable subsection labels, bullet and
  numbered lists, tables that scroll when wide, quotes, code blocks and
  inline emphasis — capped to a comfortable reading width instead of a
  full-bleed wall of text.
- **You can select and copy text from a notification.**

## v0.3.80 — 2026-06-24 — the Schedule panel stays in sync and reports its loading

_Requires alpi v0.9.29+._

- **The Schedule panel updates live.** When another client pauses, resumes
  or removes a schedule on the daemon you have open, the list refreshes
  on its own instead of waiting for you to switch profile or reopen the
  panel.
- **The "fetching latest settings" bar now also reflects the Schedule
  panel.** Following v0.3.79's pass over usage, devices and gateways, the
  schedule list is the last Settings section whose loading state lights
  up the indicator.

## v0.3.79 — 2026-06-23 — the rest of Settings reads and writes only the daemon you've selected

_Requires alpi v0.9.29+._

- **Every Settings panel now targets the daemon the panel is showing.** Following
  schedules in v0.3.76, the rest of the surface — usage, profile memory, devices
  and gateways — reads and edits only the selected daemon when two paired daemons
  share a profile name. Late results from a previously selected daemon no longer
  leak in, and each save, key change or removal lands on the right one.
- **Gmail authorization stays on the daemon and attempt that started it.**
  Switching daemons mid-flow can no longer let a late "authorized" event drive
  the wrong daemon; the whole consent flow — including the paste-the-callback-URL
  fallback — is pinned to the one connection that began it.
- **The "fetching latest settings" bar reflects each panel.** Usage, devices and
  gateways now report their own loading, so the indicator is accurate while a
  panel refreshes against the chosen daemon.

## v0.3.78 — 2026-06-23 — scheduled-job failure notifications name the schedule and the reason

_Requires alpi v0.9.29+._

- **A failed scheduled job's native notification now says which schedule failed
  and why.** It uses the job's name and the enriched failure reason (the error,
  or "agent timed out" with the timeout) from the daemon's `schedule.failed`
  event, instead of the cryptic job id and a bare one-liner.

## v0.3.77 — 2026-06-23 — Fast Refresh restored in the notifications view

_Requires alpi v0.9.27+._

- **Fast Refresh works again when editing the notifications view.** A
  non-component helper exported alongside the modal was forcing Vite to
  full-reload the page on every change during development; the helper now
  lives in its own module so edits hot-apply in place.

## v0.3.76 — 2026-06-22 — scheduler errors visible; schedules respect the chosen daemon; profile-name traversal closed

_Requires alpi v0.9.27+._

- **Scheduler errors no longer disappear.** When alpi cannot read its
  `jobs.json` (corrupt file, parse failure), the Schedule panel now
  shows the daemon's exact error instead of pretending the list is
  empty.
- **Schedules respect the chosen daemon.** When two paired daemons share
  a profile name (e.g. `default` on home + work), the schedule list and
  every fire/pause/delete now target the daemon the panel is showing,
  not whichever connection happened to be active.
- **Profile names accept dots and reject `..` everywhere.** The
  new-profile dialog matches the daemon's contract — `build.debug`,
  `a1`, single-character names all pass; `foo..bar` and any other path-
  traversal vector is refused with the same rule the daemon enforces.

## v0.3.75 — 2026-06-20 — attach & save files on Windows and Linux

_Requires alpi v0.9.19+._

- **Attaching files now works on Windows and Linux.** The attach button and the
  workspace picker used a macOS-only file dialog and did nothing elsewhere; they
  now open the native picker on every platform.
- **"Reveal in folder" and "Save a copy" work cross-platform too** — Explorer on
  Windows, the file manager on Linux, Finder on macOS.

## v0.3.74 — 2026-06-19 — reliable reconnect after a daemon restart

_Requires alpi v0.9.19+._

- **The app no longer thrashes after the daemon restarts.** It now marks a
  connection "online" only once the daemon actually replies (not the instant
  the socket opens), and a transient error no longer triggers reload storms —
  so a restart settles cleanly instead of looping.
- **Starting the daemon from the app uses the installed supervisor** (launchd /
  systemd) instead of spawning a competing foreground process, and waits for the
  daemon to actually answer — not just a pidfile — before reporting it started.

## v0.3.73 — 2026-06-19 — skills explorer + unified panels

_Requires alpi v0.9.18+._

- **New Skills explorer.** Browse every skill on a profile: read its SKILL.md,
  see at a glance whether it's active or inactive (and why), check its
  requirements, tools and keywords, and open its files (scripts, references) —
  all read-only. Secret files stay locked.
- **Tools, Skills, Memory and Notifications now share one layout.** The same
  two-pane shell, search, headers and sizing across all four; the window grows
  with your screen instead of staying fixed.
- **Cleaner detail headers.** Skills and Tools read as a `category/name` path,
  disabled tools are dimmed, and a notification shows its `connection/profile · time`.

## v0.3.72 — 2026-06-18 — real context window in the header

_Requires alpi v0.9.17+._

- **The chat header shows the model's real context window.** It always read
  200K; it now reflects the model's actual limit (e.g. 1M for the latest
  models).

## v0.3.71 — 2026-06-18 — notification titles

_Requires alpi v0.9.16+._

- **Notifications show their title.** When a notification has a title it leads
  the push as its headline (with the body below), heads the inbox row above a
  two-line body preview, and sits as a bold heading above the body in the
  detail. Untitled ones derive a headline from the body's first sentence so the
  inbox stays scannable.
- **The detail header lines up with the search box** — same height and a
  matching bottom divider.

## v0.3.70 — 2026-06-17 — auto-read speaks the new reply

_Requires alpi v0.9.15+._

- **Auto-read speaks the reply that was just generated, not the previous one.**
  On a fast turn the spoken text could lag a beat behind the saved history and
  read the prior message; it now reads from the freshly streamed reply.

## v0.3.69 — 2026-06-17 — a dropped connection no longer hijacks the app

_Requires alpi v0.9.15+._

- **A disconnected background daemon no longer yanks you to it.** A "daemon
  disconnected" alert used to, on the next window focus, switch you to that
  (often dead) connection and surface its connection error — even one you
  weren't using. Disconnect alerts now fire only for the connection you're
  actively using, and a settings/notification deep-link never switches the
  active connection.

## v0.3.68 — 2026-06-17 — read notifications aloud

_Requires alpi v0.9.15+._

- **Read a notification aloud** — the notification detail gets a read-aloud
  button next to Copy, with live audio bars while it plays (tap to stop). It
  uses the profile's configured voice.
- **Notification text now renders like a chat message** — same size and full
  Markdown (tables, code blocks, lists, links) instead of a smaller, plainer
  style.
- **The inbox is grouped by date** — Today / Yesterday / This week … like
  sessions, so recent alerts are easy to scan.
- **The detail header shows the source connection**, matches the list's
  lowercase styling, and stays pinned while you scroll a long notification.
- **Per-connection profile data loads from the right daemon** — a paired
  connection's voice (and other profile details) no longer falls back to the
  active connection's.

## v0.3.67 — 2026-06-17 — interrupted turns are marked

_Requires alpi v0.9.14+._

- **An interrupted message no longer looks like it's still loading.** A turn
  that never got a reply now shows a subtle "Interrupted before final reply"
  instead of appearing as if a response is still on its way.

## v0.3.66 — 2026-06-17 — tidier chat header

_Requires alpi v0.9.8+._

- **Header actions moved into a "⋯" menu** — Profile settings, Pause, Auto-read
  replies (with an on/off toggle), Skills, Memory, Tools and Refresh thread now
  live in one menu instead of a row of buttons. Sessions and the live audio
  indicator stay in the bar. Workgroups get the same menu.
- **New session** is the top row of the Sessions dropdown (⌘N) — and you can
  start one even from a profile with no sessions yet.
- **Popovers toggle properly** — clicking a menu or dropdown button again closes
  it instead of flickering back open (fixed across the app).

## v0.3.65 — 2026-06-16 — generated images render as attachments

_Requires alpi v0.9.8+._

- **Images an agent generates now render as real attachments** — a large inline
  preview you can click to zoom or download, instead of being flattened into the
  message text. A produced photo shows reliably (no more occasional blank), and
  several images lay out in a simple grid.
- **A preview that fails to load once is no longer stuck for the whole session.**
  A transient read failure (for example right after the daemon restarts) used to
  stay blank until you reloaded the app; now it can recover when the message
  remounts (e.g. navigating back to the chat).

## v0.3.64 — 2026-06-16 — reasoning reads in execution order

_Requires alpi v0.9.8+._

- **Thinking and tools now interleave in the order they happened** — think →
  search → think → read → answer, instead of stacking all the reasoning above
  the tools. Each earlier thinking step collapses to a one-line "Thought for Ns"
  you can expand, and the steps sit together as one tight timeline.
- **Calmer live thinking** — while the agent works you see a single
  "thinking · Ns" line with its latest thought; click to open the full trace.
  The shimmer placeholder is gone and the reasoning window no longer takes over
  the screen.
- **Screen readers** now announce a grouped tool row as expandable, with its
  expanded/collapsed state.

## v0.3.63 — 2026-06-15 — pause a profile

_Requires alpi v0.9.8+._

- **Pause a profile** from its chat header (or the sidebar's right-click menu),
  the same way you pause a workgroup. A paused profile drops to the bottom of
  the sidebar (dimmed), is never the new-chat default, and opens read-only — you
  can read the history, but the composer is disabled until you resume.
- **Quieter "thinking" indicator** — dropped the bouncing dots next to the
  label, in both the reasoning trace and the pending-reply placeholder.

## v0.3.62 — 2026-06-15 — reasoning trace, livelier loading, cleaner switch

_Requires alpi v0.9.7+._

- **Redesigned the reasoning ("thinking") trace.** While the agent reasons you
  get a live, auto-scrolling window; when it's done it collapses to a
  "Thought for Ns" you can expand. A page-long thought is capped to half the
  screen and scrolls instead of burying the conversation.
- **Livelier loading placeholders** — both opening a conversation and waiting
  on a reply now animate instead of sitting static.
- **Switching connections opens a new chat** instead of reopening the last
  profile you were on — the switch is instant and carries no stale context.
- **Cleaner "Thought" on older sessions** — no more "Thought for 0s" when the
  duration wasn't recorded.
- **The Copy tooltip in a notification no longer shows in ALL-CAPS.**

## v0.3.61 — 2026-06-15 — connections recover on their own

_Requires alpi v0.9.7+._

- **A dropped connection now reconnects by itself.** When the daemon went away,
  the connection got stuck on "offline · retrying…" until you clicked retry or
  reopened the app — the "retrying" was only a label. It now genuinely re-probes
  every few seconds and flips back online the moment the daemon is reachable.
- **A brief daemon hiccup — or the warmup right after a restart — no longer
  flaps the connection offline.** The local probe is more tolerant (one retry,
  a longer timeout), so a busy-but-alive daemon stays shown as online instead of
  blinking offline↔online.

## v0.3.60 — 2026-06-14 — update a daemon in place

_Requires alpi v0.9.6+._

- **"Update alpi"** in Settings → Service upgrades the daemon to the latest
  release and restarts it (no-op + a clear note on image-pinned Docker installs).
- **An "update" badge** marks any connection running behind the latest version.

## v0.3.59 — 2026-06-13 — notifications across every connection

- **Background daemons can reach you now.** You get native notifications from
  every connected daemon, not just the active one — switch away from a daemon
  and you'll still hear when it needs you.
- **One notifications inbox for all connections**, each item tagged with its
  daemon. Read, open, or clear any of them from a single list.
- **The unread count covers every connection**, so the bell reflects all your
  daemons at a glance.
- **Dropped the confusing source tag** (`send msg` / `schedule`) from the list
  and detail — it showed an internal delivery detail, not anything useful.
- **Click a notification to land on it** — the app switches to the originating
  connection and opens the right place.

## v0.3.58 — 2026-06-13 — clearer schedule view

_Titles require alpi v0.9.4+._

- **Job titles.** The schedule list shows a job's title when it has one, instead
  of the raw prompt or `python3 …` command. Without a title it still shows the
  prompt.
- **Hover the title** to see the full underlying prompt or `python3 …` command
  in a wide tooltip.
- **Distinct icon actions** — Run (▶), Enable/Disable (power), Delete — always
  visible with tooltips, instead of text links that only appeared on hover.
- **Cleaner four-column row** — id · schedule · title · actions — and the
  schedule chip drops the redundant "cron" label.

## v0.3.57 — 2026-06-12 — auto-read agent voices

_Requires alpi v0.9.1+._

- **Auto-read replies (per profile)** — turn it on in Settings → Voice and the
  app speaks each agent reply aloud as it lands. Your own messages are never
  read.
- **Auto-read messages (per workgroup)** — the hub can have agents' automatic
  messages read aloud; your directives are never read.
- **Animated sound-wave in the chat header** whenever a reply is being read
  aloud (auto-read or a manual *Read aloud*) — tap it to stop the current read.

## v0.3.56 — 2026-06-12 — robust startup: no blank screens, no duplicate windows

- **No more blank screen on launch** — a startup crash introduced in v0.3.55 is
  fixed, and an unexpected error now shows a recoverable screen with a Reload
  button instead of a dead window.
- **Only ever one Alpi window** — launching the app again (or after an update)
  now focuses the existing window instead of opening duplicates. Fixes the
  multiple-windows behaviour seen on Windows.
- **First-run connection guard** — if there's no daemon running and no
  connection set up yet, the Connection panel opens and stays put until you add
  one, so the app never sits empty with nothing to do.

## v0.3.55 — 2026-06-12 — sidebar + modal fixes

- **No more stray "Show less"** in the sidebar when all your alpis already fit.
- **The profile right-click menu actually works.** "Open settings" and
  "Delete profile…" now open the right profile (before they silently did
  nothing); delete removes the row immediately, shows a toast, and restores it
  if the daemon call fails.
- **No right-click menu on connections you don't administer** — it would only
  have shown "Pin", which already lives on the row.
- **The Connection window closes with Esc**, like every other modal.

## v0.3.54 — 2026-06-12 — budget editor is USD-only

- **The profile budget is now just a daily USD cap (or unlimited)** — the
  token-cap option is gone, matching the simplified budget model.

## v0.3.53 — 2026-06-11 — chat fixes: no double message, calmer scroll, kept formatting

- **Your message no longer shows up twice** while the reply is still streaming.
- **The chat follows the reply as it streams** and snaps to the latest when you
  send — scroll up any time to stop following, send again to re-engage.
- **Multi-line messages and bullet lists keep their formatting** in the bubble
  instead of collapsing onto one line.

## v0.3.52 — 2026-06-11 — drafts that survive, smoother modals, less friction

- **Your unsent text is never lost.** Drafts persist per chat and workgroup when
  you switch views or restart the app, and clear once sent.
- **Copy code with one click.** Code blocks now show a copy button on hover.
- **Every modal, panel and tooltip animates** consistently — and respects your
  system's reduced-motion setting.
- **The window remembers its size and position** between launches.
- **A keyboard shortcuts sheet** — press ⌘/ (or find it in the command palette).
- **Keep typing while reconnecting** in a workgroup — only sending waits.
- **Closing a dialog returns focus** to where you were, for keyboard users.
- Long sidebar names no longer clip their descenders (g, y, p).

## v0.3.51 — 2026-06-10 — animations are back, text zoom, calmer shortcuts

Requires alpi v0.8.18+.

- **Every micro-animation works again.** A broken design token had silently
  disabled all transitions and pop-ins since v0.3.29 — hovers, tooltips and
  panels now ease the way they were designed to.
- **Zoom the whole UI** with ⌘+ / ⌘- (and ⌘0 to reset), between 70% and 150%,
  remembered across launches.
- **⌘⇧A always brings Alpi to the front.** It no longer hides the window when
  the app is visible but unfocused, and the tray menu drops the Open/Hide
  toggle for a plain "Open Alpi". Closing the window still keeps Alpi in the
  menu bar.
- **Usage chart polish:** the day tooltip is properly centered over its bar,
  and days with no activity no longer show an empty tooltip.

## v0.3.50 — 2026-06-10 — saving settings keeps you connected

Requires alpi v0.8.18+.

- **Gateways, subsystem toggles and the ALP port no longer restart the
  daemon.** The daemon applies them in place within seconds (toasts now say
  "applying") — your chat, your peers and other machines stay connected while
  you change settings. Address and pairing-port changes still restart, as they
  rebind the connection you're on.

## v0.3.49 — 2026-06-10 — stays responsive when the daemon dies

Requires alpi v0.8.17+.

- **The app no longer freezes when the daemon stops or restarts.** Every daemon
  call runs off the main thread now — a dead daemon means a banner and a quick
  reconnect, not a locked-up window.
- **Reconnecting is calm.** Catching up after a restart is one quiet refresh
  instead of replaying every missed event against a cold daemon.
- **Background workgroups stop stealing your UI.** Activity in a workgroup you
  aren't viewing just lights its sidebar badge — no global reloads, no
  transcript fetches, no disk writes until you open it.
- **Long transcripts render lighter.** Messages re-render only when their
  content changes, and post bursts coalesce their disk writes.
- **Offline is detected fast and probed with backoff** — pollers pause while
  the daemon is down and resume on the first sign of life.

## v0.3.48 — 2026-06-10 — tools panel without the "Other" pile

Requires alpi v0.8.16+.

- **Every tool shows under a meaningful group.** The dozen tools that piled up
  in "Other" (semantic search, notify, workgroup posting…) now appear under
  Workspace, Memory, Comms, Agent and Collab.

## v0.3.47 — 2026-06-10 — notifications always reach you

Requires alpi v0.8.14+.

- **Notifications no longer get swallowed.** When the agent notifies you — a
  reminder, an alert, a finished task — the banner now shows even if you're
  looking at that very chat. Before, it was silently suppressed.
- **Alerts are colour-coded.** Notifications carry a type: `error` shows a red
  badge, `warning` an amber one, `info` stays neutral.

## v0.3.46 — 2026-06-09 — usage chart in Settings

Requires alpi v0.8.12+.

- **A Usage section charts your last 14 days of token activity.** In a profile's
  Settings (after Overview) and a workgroup's (after Budget): today's cost,
  input/output tokens, a per-day bar split input vs output, and the 14-day total
  with cost. Hover a day for its breakdown. Works for free models too — the bars
  track token volume, so a $0 model still shows real usage.
- **Cost stays front and center in dollars** — today's spend (matching your daily
  budget), the 14-day total, and for profiles the daily cap with how much is
  left. Workgroups show the daily average instead.

## v0.3.45 — 2026-06-09 — reasoning is its own collapsible block

Requires alpi v0.8.8+.

- **The agent's reasoning is now a collapsible block, not a blob.** While it
  thinks you see "Reasoning…"; once it answers it collapses to "Reasoned for 12s"
  (click to expand), split into paragraphs. It no longer vanishes when the final
  answer arrives.
- **Tables read cleanly again.** Body rows use the chat-panel background (only the
  header is shaded), instead of a grey fill.

## v0.3.44 — 2026-06-09 — image previews land in the conversation

Requires alpi v0.8.7+.

- **Images preview inline in the conversation.** Both the images you attach and
  the ones an agent generates show their thumbnail in the thread — not only while
  composing, and not as a bare filename in history.
- **No duplicate when you re-edit.** Editing a sent message and pressing enter no
  longer leaves the old copy beside the new one.
- **Tidier image captions.** The caption under an image stays on a single line.
- **Cleaner replies.** The redundant file path an agent sometimes printed under a
  saved image is hidden — the attachment already carries it.

## v0.3.43 — 2026-06-08 — files an agent makes show up as attachments

Requires alpi v0.8.6+.

- **Generated files arrive as attachments.** An image an agent produces previews
  inline (full-size, click to enlarge); other files — PDF, spreadsheet, doc —
  show as a labelled attachment, even when the agent replies with no text.
- **Cleaner tool output.** A step that produced a file shows a compact
  "Generated · name" line instead of the raw result blob.

## v0.3.42 — 2026-06-07 — images show inline in chat

Requires alpi v0.7.2+.

- **Images now appear in the conversation.** When an agent produces an image, it
  renders right in the reply as a captioned card instead of just a file path.
- **Click to enlarge.** Open any chat image full-size in a lightbox; close with
  Esc or by clicking outside.
- **Download (macOS).** Save a copy of an image from its caption or the lightbox.

## v0.3.41 — 2026-06-06 — model picker stops sticking to a stale override

Requires alpi v0.7.2+.

- **The model picker no longer keeps a stale choice.** When a profile's model
  changes, the per-message override resets — so you won't keep silently sending
  a model you picked earlier (which could, e.g., break image input on a profile
  that's since switched to a vision model).
- **Clearer when you're overriding.** The model control now highlights when the
  active model is an override, not the profile's configured default.

## v0.3.40 — 2026-06-04 — consistent iconography

Requires alpi v0.7.2+.

- **One icon set.** Every glyph now shares the same weight and grid, so
  toolbars, menus, and settings read evenly instead of mixing thin and heavy
  lines.
- **Clearer labels.** Model shows a sparkle, skills a blocks glyph, tools a
  wrench, memory a chip, and auto-theme a sun/moon — each easier to tell apart.
  Remote daemons use a server icon, local ones a chip.
- **Stop button fixed.** The stop-generation square is centered and sized to
  match the surrounding controls.

## v0.3.39 — 2026-06-03 — attach files to chat

Requires alpi v0.7.2+.

- **Attach files.** A paperclip next to Send opens a native file picker, and
  you can drag files straight onto the window. Images, PDFs, and text files
  show as cards (icon + name + size) you can remove before sending; the model
  reads them.

## v0.3.38 — 2026-06-03 — tables & code in messages

Requires alpi v0.7.1+.

- **Tables and code blocks render now.** Markdown tables show as clean tables
  (subtle header, aligned columns, row separators) instead of flattened text,
  and fenced code blocks get a language label and their own framed block.
- **Tidier profile header.** Dropped the redundant per-session cost that sat
  between the token and budget meters — the budget meter already shows spend.
- **A workgroup you just created is no longer flagged unread**, and the
  sidebar's unread dot sits consistently aligned.

## v0.3.37 — 2026-06-03 — one accessible address

Requires alpi v0.7.1+.

- **Simpler network settings.** Set one accessible address in Service; the ALP
  and Devices sections now show just their ports, each tagged with the detected
  network type (`tailscale:` / `lan:` / `tcp:`). Saving an address or a port
  reliably restarts the daemon and tells you if the restart didn't take, and
  warns when an address would expose the daemon on every interface.
- **Consistent labels.** Section labels across the sidebar, the pipeline bar,
  and settings now share one typographic style.

## v0.3.36 — 2026-06-03 — cleaner pipeline strip

Requires alpi v0.6.35+.

- **Quieter pipeline strip.** Upcoming stages now show just their name (no
  hollow circle), the active stage is a pulsing dot in the hub's accent, and
  done stages keep the green check — only a blocked stage gets a filled pill.

## v0.3.35 — 2026-06-03 — pipeline at a glance

Requires alpi v0.6.35+.

- **Pipeline strip under the header.** A workgroup with a pipeline now shows its
  stages as a row of chips — done, current, blocked, or pending — so you can see
  where the work stands without scrolling the transcript.
- **Jump to a stage.** Click a stage chip to jump straight to that phase's
  message in the transcript.
- **Calmer status banners.** Blocked and paused banners sit just below the header
  with a single, consistent style.

## v0.3.34 — 2026-06-02 — blocked workgroups show it, quieter notifications

Requires alpi v0.6.35+.

- **A blocked workgroup shows it.** When a workgroup's pipeline halts (a `#done
  BLOCKED · …` close), the workgroup view shows a banner with the phase + reason
  instead of looking idle.
- **No banner for the view you're looking at.** A workgroup `#done` or an agent
  message no longer fires a native notification when you're already focused on
  that workgroup or chat — only when it's in the background.

## v0.3.33 — 2026-06-02 — assign a workgroup pipeline

Requires alpi v0.6.32+.

- **Assign a pipeline to a workgroup.** Workgroup settings has a Pipeline
  section: add, remove, and reorder (`◀ ▶`) the ordered stage chips the hub
  runs (`intake → content → build → qa`), then Save. The create dialog takes a
  pipeline field too. Empty = a normal deliberation workgroup.
- **Section descriptions read inline.** Each settings heading shows its short
  description beside the title instead of behind a `?` tooltip.

## v0.3.32 — 2026-05-29 — task history reads skips correctly

- **Skips read correctly.** One member passing on a round no longer
  marks the whole task as skipped or counts it resolved — the task
  stays active until the hub closes it.
- **No phantom tasks.** A message that both opens and closes a task is
  shown as plain text instead of a stray entry in the history.
- **Cleaner working indicator.** Active tasks show a single pulsing dot
  — task list, header, and `#working` posts — so tasks read as just
  working, done, or skipped.

## v0.3.31 — 2026-05-29 — task slugs, denied tools, profile bio tooltips

- **Composer enforces `#task #<slug>`.** Workgroup composer validates
  as you type: the Send button stays disabled until a valid `#<slug>`
  follows, with a warning line showing the expected shape. `#task`
  without a slug is no longer treated as a task anywhere in the UI —
  parser and `findLatestTask` reject them in lockstep with the new
  alpi protocol gate. `TasksButton` reads the slug straight from the
  post; the `slugifyTitle` fallback is gone.
- **Denied tools shown muted.** Tools blocked by `tools.deny` in the
  profile's `config.yaml` now show up struck-through with a `denied`
  tag in the tools panel, with a detail-view banner explaining the
  agent can't see them. Previously every registered tool looked
  available regardless.
- **Profile bios on hover.** Hovering a profile's diamond reveals
  its `public_bio` — sidebar rows, workgroup chat header (hub),
  profile chat header title, profile settings hero, and workgroup
  speaker rows. Bios escape the sidebar's scroll container via a
  portaled tooltip so long text doesn't get clipped.
- **DiamondStack pulses while working.** Workgroup sidebar rows in
  the `working` state now pulse the stacked diamond (front + back,
  staggered) instead of swapping to a single pulsing diamond — the
  stack identity stays consistent across states.

## v0.3.30 — 2026-05-29 — workgroup transcript polish

- `#task` posts with a `#slug` (e.g. `#task #onboarding-friction-top3 ...`)
  show the slug bolded inline; the same slug feeds the task navigator
  caption.
- `#done`, `#working`, `#skip` cards render the full post body in
  markdown — paragraphs, lists, bold — instead of just the first line.
- Stale `#working` posts (superseded by a later message from the same
  peer **or** by a `#done`/`#skip` closing the task) collapse to a `WORK`
  badge with a static dot. Active `#working` shows the hub-colored
  diamond pulsing.
- `TASK` cards now tint with the hub color (same treatment as `DONE`).
- Sidebar workgroup rows lose the hash glyph in favour of a small
  stacked diamond in the hub color; `#name` label stays mono and one
  size below the profile label so the two columns finally line up.

## v0.3.29 — 2026-05-28 — restart daemon button + approval label cleanup

- New **Restart daemon** row in `Settings → Service` (admin-only).
  Typed-confirm modal — same pattern as delete profile, expects the
  word `restart`. The host SIGTERMs itself; launchd / systemd respawn.
- Approval modal eyebrow renamed `SANDBOX` → `ALERT` in danger red,
  so the label matches what users actually read.

## v0.3.28 — 2026-05-28 — workgroup `#task` shows the full briefing

The task card in a workgroup transcript was showing only the headline.
The body (context, role asks, deliverable) was dropped on the floor.

- `#task` cards now render the full briefing under the title with
  block-level Markdown — paragraphs, lists, emphasis — matching
  regular workgroup posts.
- `parseTaskOpen` moved to `lib/workgroup-tasks.js` so it has unit
  coverage; previously it lived inline in the view with none.

## v0.3.27 — 2026-05-28 — per-device profile scope pair modal

Pair modal restricts a non-admin device to a subset of profiles and
auto-revokes the placeholder token if the admin cancels or closes the
modal before pairing completes.

- **Profiles access dropdown** (`All profiles` / `Restrict to…`) with
  filter + checkbox rows per local profile, accent diamond, mono
  name. Built on the design system: `Dropdown`, `Field`, `Diamond`,
  plus new `Checkbox` / `Radio` primitives (inline check SVG;
  CSS-only sizing — no inline `style`).
- **Pair button is disabled** when **Restrict** is selected with zero
  profiles — empty selection would land at the daemon as `[]`, which
  means unrestricted. The form prevents that state from leaving the
  client.
- **Cancel / close auto-revokes the pending token** via an unmount
  cleanup, and the daemon prunes 24h-old `pending` rows that never
  paired as belt-and-braces.
- **Admin banner** uses the new `Checkbox` primitive + caption + `?`
  tooltip for the rationale.
- Wires `devices_set_profiles` on top of `host.devices.set_profiles`.
  Pairs with alpi 0.6.28; older daemons ignore the scope param.

## v0.3.26 — 2026-05-27 — peers panel refreshes on every action

The peers dropdown no longer keeps showing a stale peer after you
remove it, and pending invites disappear the moment you discard them.

- Add / remove / accept / discard now force a refresh of the profile
  detail cache instead of relying solely on the daemon push event.
  Even if the event arrives late or is dropped over a flaky remote
  connection, the dropdown reflects the daemon state immediately.
- Pairs with the alpi 0.6.24 local peer routing fix; ensure both
  upgrade together.

## v0.3.25 — 2026-05-27 — storage panel covers the full profile

Profile → Storage now shows where your disk is actually going,
not just sessions / audio / logs / schedule / workgroups.

- Six new rows with hover scope tooltip: **skills**, **memories**,
  **rag** (workspace embeddings — often the largest by far),
  **outputs** (notifications inbox), **gateway** (telegram/email/matrix
  chat sessions) and **mentions** (@-mention threads from ALP peers).
- Requires alpi ≥ 0.6.21.

## v0.3.24 — 2026-05-27 — notifications get search + undo delete

Cleaner inbox modal: live local search, and individual notifications
can be removed straight from the row with a 5-second undo.

- Local search bar above the list filters by body, title, profile,
  source and severity.
- Hover a row → the timestamp swaps to a discreet × close. Click
  removes the notification instantly and shows a toast with **Undo**
  for 5s; the backend delete fires after that.
- Dropped the red bullet next to unread rows — the bold body already
  communicates unread.
- Requires alpi ≥ 0.6.20 (uses the new `host.outputs.delete`).

## v0.3.23 — 2026-05-27 — ask_user clarification modal (UX.1)

When the agent calls ``ask_user`` on the daemon, desktop pops a
native modal with one button per choice instead of asking in chat
text. Pairs with the matching mobile sheet and the TUI inline
prompt.

- New ``ClarificationModal``: question + per-choice buttons (with
  optional description), Cancel, and an "Other…" affordance that
  swaps in a text input when the user wants to answer outside the
  enumerated set.
- Same event/queue plumbing as the approval modal: subscribes to
  ``clarification.request``/``clarification.resolved`` on the live
  stream, calls ``host.clarification.pending`` on connection switch
  for cold-start recovery, dedupes by ``request_id``.
- Two new Tauri commands — ``clarification_respond`` and
  ``clarification_pending`` — forward to the daemon RPCs of the same
  name.

Requires alpi ≥ 0.6.18.

## v0.3.22 — 2026-05-26 — Manage Sessions

The Sessions popover in the chat header gains a
``Manage sessions →`` footer link that opens a full session
inbox: every chat thread on the profile with activity, turns,
and disk size, filter chips, sort, and bulk delete behind a
typed-confirm.

- Filter chips: ``All``, ``≥ 30 days``, ``≥ 90 days``,
  ``< 3 turns``. Sort dropdown: size / activity / turns /
  created. Default sort = size.
- The active session is locked. Its checkbox is disabled and
  the row carries a ``◆ current session`` marker.
- Bulk select with ``⌘A`` (visible rows) or ``Shift+click`` for
  range. Header CTA swaps from ``Close`` to ``Cancel ▸ Delete N``
  (red) once anything is selected; footer shows
  ``Selected N · XX KB to free``.
- The confirm modal uses typed mode (``Type DELETE to confirm``)
  with the freed-bytes figure and an irreversible warning.
- Each row's size now counts both the session file and its
  per-turn replay sidecar, so the freed estimate matches what
  the disk actually loses.

Requires alpi ≥ 0.6.13.

## v0.3.21 — 2026-05-26 — drop the TTS autoplay toggle

Audio playback already lives on each message bubble. The separate
autoplay row in profile settings was redundant and only made sense
when the daemon was the player — now it's gone.

- Profile → Voice loses the **Autoplay** row. Voice picker + Test
  stay; everything else about audio delivery is on the message
  itself.
- The ``voice_autoplay`` Tauri command is gone. Older builds
  pinned against the new daemon get ``method-not-found`` and
  surface it as a normal toast, no crash.

Requires alpi ≥ 0.6.12.

## v0.3.20 — 2026-05-25 — Notifications inbox replaces Activity

The sidebar gets a bell — a persistent inbox of proactive
messages from every profile on the active connection. Same
surface, same rows as the mobile screen: every ``send_message``
and every schedule failure files a durable row you can open
later instead of catching it once on the OS notification tray.
Requires alpi ≥ 0.6.11.

- New ``Notifications`` modal — master-detail layout. Left
  column lists rows across every profile on the active
  connection (profile diamond + ``@name · source · relative
  time`` + body preview); right pane shows the full body with
  markdown, ``Open schedule`` / ``Open chat`` contextual action,
  and ``Copy``. ``Mark all read`` in the header.
- Bell button next to ``Settings`` in the sidebar footer, with a
  live unread badge and ``⌘O`` hotkey. Tooltip reads
  ``Notifications · N unread · ⌘O``.
- The macOS tray now mirrors unread outputs too: the tray icon
  switches to the attention variant, the menu shows
  ``Notifications (N)``, and the Dock badge carries the unread
  count. Updates still keep their own restart action in the same
  menu.
- Opening a row marks it read; ``Mark all read`` clears every
  ``unread`` across the active connection's profiles via
  ``host.outputs.mark_all_read``. List, detail and the bell
  badge re-fetch together after any mark/clear, so siblings
  don't drift.
- Native notifications now deep-link to the persisted row.
  ``agent.message`` and ``schedule.failed`` honour the daemon's
  ``deep_link`` (``/outputs/<profile>/<id>``) — clicking the
  banner opens the modal with that exact row selected, instead
  of dumping you into a chat or the schedule list. Older daemons
  fall back to the previous deep-link targets.
- Refresh-on-event: the modal and bell listen for the daemon's
  ``output.created`` / ``output.updated`` events and re-fetch
  without polling.

## v0.3.19 — 2026-05-25 — pair-with-role UI + role-aware gating

Surfaces the v0.6.10 ``admin / member`` device roles. Requires
alpi ≥ 0.6.10.

- Pair modal in Settings → Devices gains a **Grant admin
  access** checkbox under the label field, default off. The
  device is minted as ``member`` and promoted to ``admin``
  inline (``devices_promote``) if the checkbox is on when you
  hit Pair. The success toast reflects the final role.
- Device detail popover now shows the role as a chip with a
  **Promote to admin** / **Demote to member** button. Both
  call the new ``host.devices.promote`` / ``host.devices.demote``
  endpoints. Buttons gated by the active connection's role.
- ``+ Add device`` is hidden when the active connection's role
  is ``member`` — daemon would refuse anyway, but the UI
  shouldn't pretend to offer the action. Same for Revoke.
- New ``useActiveRole()`` hook reads the role from
  ``host_connections()`` and refreshes on the existing
  ``connection-status`` event. Cached in Rust per-connection
  alongside ``alpi_version``; sourced from the ``role`` field
  the daemon added to ``host.version``.
- Two new Tauri commands ``devices_promote`` and
  ``devices_demote`` wire through to the daemon via the normal
  host plane — admin WS clients can promote / demote remote
  devices too (the daemon enforces ``_ADMIN_METHODS``). Cached
  role on the affected device's desktop refreshes on next probe
  (~30 s); not a security gap since the daemon rejects regardless.
- **Settings → Devices** section used to be hidden whenever
  the active connection was remote (legacy "local-only" rule).
  Now it shows up for any admin connection — local Unix socket
  OR remote WS with ``role=admin``. Network sub-section
  (``host.network.*``) stays local-only since the daemon never
  unlocks those over WS.
- **Sidebar gating**: the ``+`` buttons for new profile and new
  workgroup, plus the **Delete profile** action in Settings,
  are now hidden for member-role connections. The daemon
  would refuse anyway, but the UI shouldn't pretend.
  Member-visible copy still mentions that this only gates the
  host control plane — the agent's own tools remain reachable
  via ``host.chat.send``.
- **Keyboard shortcuts and command palette** also stop offering
  *New profile* / *New workgroup* when the active connection is
  member. Both ``useWindowChrome`` and ``useCommands`` now
  receive ``null`` callbacks under that role, so ``⇧⌘N`` /
  ``⇧⌘W`` no-op and the palette omits the entries entirely
  instead of opening a modal that the daemon would reject.
  Role is read once at the App level via the new
  ``useActiveRole`` hook; pre-probe (no role yet) defaults to
  *allow* so local boot doesn't lose the shortcuts.
- **Pair-modal admin promote** is now honoured on the cancel /
  keep-anyway path too. If you ticked *Grant admin access*, then
  scanned the QR from the phone (which makes ``devices.list``
  see the device as paired) and closed the modal via Cancel,
  the device used to stay as ``member`` because the rename
  branch ran but the promote did not. Promote now fires in both
  paths.

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
