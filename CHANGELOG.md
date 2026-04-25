# Changelog

## v0.2.89 — 2026-04-25

### alp.3 — workgroups: pause/resume + member-side state + management UX

Two layers landed together. The protocol now carries
``workgroup.pause`` / ``workgroup.resume``, and members get
their own subscription state plus a full management surface (CLI
verbs, ``alpi setup → ALP → Workgroups`` wizard, agent tool).

#### Pause / resume

- ``alpi/alp/workgroup.py`` — ``Meta.paused`` / ``paused_at`` /
  ``paused_by`` (only persisted while paused). Two new handlers
  ``workgroup.pause`` and ``workgroup.resume``, both idempotent.
  ``workgroup.post`` now rejects with ``-32010 workgroup-paused``
  + ``data: {paused_at, paused_by}`` when the flag is set.
  ``pull`` / ``join`` / ``leave`` keep working — pause must not
  trap members.
- ``docs/ALP.md`` — verbs documented; error code ``-32010`` added
  to the table; hub-state listing notes the optional fields.

#### Member-side state — ``Subscription``

A profile that joined a workgroup hosted by a peer needs local
state to send ``post`` / ``pull`` / ``leave`` without re-joining
on every restart, and to decrypt past traffic across rekeys.

- ``alpi/alp/subscription.py`` (new) —
  ``~/.alpi/<profile>/alp/secrets/subscriptions.yaml`` (mode 0600).
  Per-workgroup record: ``wg_id``, ``name``, ``hub_id``,
  ``hub_pubkey``, list of ``SealedKey(version, sealed)`` (hub
  rotations land here on the next ``pull``), ``last_seq`` cursor,
  ``joined_at``. Sealed keys stay sealed on disk — they only open
  with this profile's Ed25519 private key, so file exposure alone
  reveals nothing without the keypair.
- ``alpi/alp/workgroup_client.py`` (new) — member-side helpers
  ``join`` / ``post`` / ``pull`` / ``leave`` / ``pause`` /
  ``resume`` that resolve the hub via this profile's
  ``peers.yaml`` (Unix socket intra-machine, Noise_XK over TCP
  inter-machine), maintain the subscription cache, and refresh
  the sealed key when the hub signals a new
  ``current_key_version`` on a pull. Hub identity is **explicit**
  — we don't probe pinned peers for which one hosts a wg_id
  (that would leak the id to every pinned peer and let a
  malicious peer impersonate the real hub by pre-creating a
  same-id workgroup).

#### CLI surface — ``alpi workgroup``

Nine verbs split by role.

- Both: ``list``, ``show``.
- Hub: ``create``, ``kick``.
- Member: ``join``, ``post``, ``pull``, ``pause``, ``resume``,
  ``leave``.

``create`` accepts ``--member <pubkey | peer-id>`` (repeated) and
``--budget-usd`` / ``--budget-tokens``. ``kick`` accepts the
target as either a pubkey or a pinned peer id.

#### Wizard — ``alpi setup → ALP → Workgroups``

- List view: workgroups grouped under ``Hub of`` and ``Member of``
  headings (no group shown when empty). Status counter on the
  setup main menu reads ``N hosting · M joined`` instead of the
  earlier jargon ``N hub-of / M member-of``.
- Hub detail: split into ``Workgroup`` (Read messages, Members,
  Budget) and ``Maintenance`` (Pause / Resume, Kick member,
  Delete workgroup) headings.
- Read messages: hub-side audit view that decrypts the transcript
  with the hub's own sealed key.
- Members: shows each pinned member with role flag (``hub`` /
  ``joined`` / ``invited``); the current profile's row renders
  in the configured accent colour.
- Budget: edit-in-place at any time; clears when both prompts
  are blanked.
- Member detail: Read new messages (pull + decrypt), Send a
  message, Pause / Resume, Leave.
- Create flow: pick name → toggle members from ``peers.yaml`` →
  optional budget. **Auto-grants** the six workgroup verbs
  (``join``, ``post``, ``pull``, ``leave``, ``pause``,
  ``resume``) to every invited peer's ``allow`` list — without
  this, the hub's capability gate would reject every join.
- Join flow: pick the hub from pinned peers → paste the
  ``wg_id`` shared out-of-band.
- Kick flow: alias-aware (shows ``@bob`` instead of pubkey
  fragment).
- Budget flow mirrors the profile-budget UX exactly: ask for
  USD and tokens prompts; both are optional; both gate
  independently when set (whichever trips first freezes posts).

Workgroup budget validation relaxed accordingly — both
``max_usd`` and ``max_tokens`` may be set; only "neither + non-
empty dict" or "non-positive value" still raise.

#### Agent tool — ``workgroup_post``

Minimal hook: the agent can drop an encrypted message into a
workgroup it's already subscribed to. Auto-pull, mention
awareness, briefing, milestone, and budget-aware behaviour are
**deferred to PR 5** (closes ALP.3 functional).

#### Tests + demo

- ``tests/test_alp_workgroup.py`` — 9 new tests for pause /
  resume (gate, idempotence, persists across restart, doesn't
  block leave, and inverse-action persistence). Suite of
  workgroup tests now 40 cases.
- ``tests/test_alp_workgroup_client.py`` (new) — 8 tests:
  subscription roundtrip with 0600 mode, idempotent upsert,
  remove, end-to-end member join → post → pull → decrypt with
  cursor advance, post-rotation pull picks up new sealed key,
  leave drops subscription, post without subscription raises,
  hub resolution rejects unpinned peer.
- ``scripts/demo_workgroups.py`` (new) — runnable end-to-end
  demo. Spins up five in-process profiles (alice / bob / bling
  / mirai / default) under ``/tmp/alpi-demo-*``, mounts two
  overlapping workgroups (``design`` 2-member alice+bob,
  ``research`` 4-member mirai+bling+default+alice with a
  $1.00 lifetime cap), runs the canonical join → post → pull →
  decrypt cycle in both, prints a narrated trace, tears down.
  Doesn't touch the user's real ``~/.alpi/``.

Suite: 817 passed, 8 skipped (was 800).

**Pending for ALP.3 to close (PR 5):** briefing field, milestone
abstraction (alive / closed / failed + goal + result), engine
auto-pull on every turn (interactive / gateway / scheduler) so
agents see workgroup activity as part of their context, mention
awareness, ``workgroup_post`` declares cost from the current
turn's ledger, budget-conscious system prompt guidance (delegate
to better-funded peers, prefer concise replies near the cap),
per-member spend breakdown in the wizard.

## v0.2.88 — 2026-04-25

### alp.3 — workgroups (PR 2: leave + rekey + lifetime budget)

Second slice of ALP.3. Members can now leave a workgroup and the
hub rotates the group key for everyone left behind; workgroups can
carry an optional **lifetime** budget (USD or tokens, project-
scoped, no daily reset) and posts double-gate against it on top of
the existing profile-level cap.

- `alpi/alp/workgroup.py` — extended:
  - `Member.key_version` + `Meta.current_key_version` track the
    monotonic group-key generation. Bumps on every rekey.
  - `_rekey()` helper: drops a target pubkey, mints a fresh
    32-byte group key, re-seals it for every remaining member,
    persists. Used by both the over-the-wire `workgroup.leave`
    and the local `kick()` primitive.
  - `workgroup.leave` handler — the leaving member is dropped;
    the hub itself can't leave its own workgroup (`-32602`).
  - `workgroup.pull` response now includes `current_key_version`
    + the caller's currently-sealed key, so members detect rekey
    on their next pull and update their local key map without an
    extra verb.
  - `workgroup.post` accepts `key_version` (which key the
    ciphertext was encrypted under, recorded in the transcript)
    and an optional `cost: {usd, tokens}` declaration that the
    hub gates against the workgroup's lifetime budget.
  - `_validate_budget()` enforces `max_usd` xor `max_tokens` with
    positive values; the workgroup `ledger.json` accumulates
    `{usd, tokens, posts}` over the workgroup's life. Hitting
    either cap returns `-32005 budget-exceeded` with
    `data.cap_kind = "workgroup_usd"` or `"workgroup_tokens"`.
  - `kick(home, wg_id, target_pubkey)` — hub-side primitive
    equivalent to a remote `leave` (TUI surface lands in PR 4).
- `docs/ALP.md` — methods table now documents `leave`, the
  `key_version` / `cost` fields on `post`, and the rekey-via-pull
  flow. New "Group-key versioning" subsection. Budget section
  rewritten as project-lifetime cap (`max_usd` / `max_tokens`
  pick-one) with the author-declared cost trust model spelled
  out. Hub-state listing extended with `ledger.json` and the
  per-member `key_version` field.

15 new tests in `tests/test_alp_workgroup.py` (PR 1's 20 still
green — backward-compat preserved): leave end-to-end with
forward-secrecy assertion (old key opens past posts, fails on new
ones), left member loses access (`-32008`), hub can't leave its
own workgroup, local `kick` rotates and rejects hub / unknown
targets, budget shape validation, USD-cap admit-then-block,
tokens-cap admit-then-block, no-budget unbounded posting, ledger
file initialised on `create`, PR 1 on-disk format loads cleanly
with `key_version=1` defaults (no migration needed for any
workgroup already on disk), sequential leaves bump versions
monotonically (v1→v2→v3 with three drops), race between
concurrent post + leave serialises cleanly via asyncio's
single-loop dispatch, profile budget gate fires upstream of the
workgroup gate (`-32005 cap_kind=usd` before the workgroup
handler ever runs).

Suite: 804 passed, 8 skipped (was 789).

**Pending for ALP.3 to close:** `pause` / `resume` + `-32010
workgroup-paused` (PR 3), TUI / CLI surface + engine context
integration (PR 4), workgroup budget bump UI (folded into PR 4).

## v0.2.87 — 2026-04-25

### alp.3 — workgroups (PR 1: hub state + 4 core verbs)

First slice of ALP.3. The hub side of shared workgroups: a profile
can `create` a workgroup with a chosen roster, and pinned remote
peers can `join`, `post`, and `pull` over the existing ALP transport
(Unix socket or Noise_XK/TCP — the dispatch is transport-agnostic).
End-to-end encrypted: the hub stores ciphertext only, group keys
are sealed per-member.

- `alpi/alp/workgroup.py` (new, ~430 lines) — three layers in one
  module:
  - **Crypto.** ECIES seal of the group key for each member:
    X25519 (derived from the member's Ed25519 pubkey via the same
    birational map Noise uses) + HKDF-SHA256 + ChaCha20-Poly1305
    with AAD-tagged contexts (`b"seal"`, `b"post"`).
    `seal_group_key` / `open_sealed_group_key` for keys,
    `encrypt_post` / `decrypt_post` for transcript entries.
  - **Storage.** Per-workgroup directory under
    `~/.alpi/<profile>/alp/workgroups/<wg_id>/` with `meta.yaml`,
    `members.yaml`, and append-only `transcript.jsonl`. IDs
    follow `wg_<base32(16 random bytes)>` — name-independent so
    renames don't break references.
  - **Local + over-the-wire verbs.** `create()` is a local
    primitive (the hub creates a workgroup on its own profile;
    you don't ask another alpi to host one). `register()` wires
    `workgroup.join`, `workgroup.post`, `workgroup.pull` against
    an `alp.server.Server`. Capability is enforced at the
    transport layer; membership is enforced at the handler with
    the new `-32008 workgroup-not-member` and `-32009
    workgroup-not-found` error codes.
- `alpi/cli.py` — `alpi alp start` registers the workgroup
  handlers alongside the existing `link.ask` handlers.
- `docs/ALP.md` — workgroup methods rewritten with concrete
  signatures (`workgroup.post(workgroup_id, nonce, ciphertext)`,
  not `(workgroup_id, text)` — encryption is client-side, the hub
  never sees plaintext). New sections document the sealing scheme
  step-by-step and the hub's on-disk state. Error codes table
  gains `-32008` and `-32009`. `leave` and `pause`/`resume` flagged
  as PR 2 / PR 3.

20 new tests in `tests/test_alp_workgroup.py`:
- crypto round-trip + isolation (sealing only opens with the
  right Ed25519 key; wrong group key fails post AEAD)
- local `create` (persistence, dedup, validation, hub auto-join)
- end-to-end over Unix socket — `join` → encrypt-and-post → `pull`
  → decrypt
- multi-member (3 alpis posting, every member decrypts the full
  transcript)
- concurrent posts via `asyncio.gather` produce distinct
  monotonic `seq` values
- workgroup state survives a server stop+restart (proves
  on-disk authoritative state)
- same flow over Noise_XK / TCP via `call_tcp`
- error paths: `-32008` not-member across all 3 verbs,
  `-32009` not-found, `-32001` capability-denied.

Suite: 789 passed, 8 skipped (was 769).

**Pending for ALP.3 to close:** `leave` + group-key rotation +
budget double-gate (PR 2), `pause` / `resume` + `-32010
workgroup-paused` (PR 3), TUI + CLI surface + engine context
(PR 4).

## v0.2.86 — 2026-04-25

### setup wizard — section headings + copy pass

The `alpi setup` main menu split into 5 visual sections (Agent,
Boundaries, Messaging, ALP, Maintenance), and the model picker into
Local / Cloud / Manage. Headings are non-selectable, render as-passed
(no auto case transform), and `ui.menu()` auto-spaces between sections
and before the close sentinel.

- `alpi/ui.py` — new `Heading(NamedTuple)` shape; `menu()` recognises it,
  adds blank rows between sections and above `Back`/`Exit`, and keeps
  the cursor from landing on either.
- `alpi/cli.py::setup_cmd` — flat 13/14-item list rewritten as five
  sections. Dispatch unchanged. `_delete_profile_status` copy trimmed
  (`Remove all data & N service(s)`).
- `alpi/model_selector.py` — provider picker grouped Local / Cloud /
  Manage. Cloud always visible; Manage only when there is something
  saved to remove.
- Copy pass across the wizard — Sandbox / Workspace / Budget / TCP-port
  dim blocks trimmed to 3–6 lines; daemon-service wizards reduced to a
  single line each (no launchd/systemd plumbing); MCP add-error
  references the profile's `.env`; Cleanup row relabelled
  `Stale sessions (>30 days old)`; Peers subtitle replaced with
  `pubkey + capabilities + reachability per peer`.

`tests/test_ui_menu.py` — 4 cases pinning the heading shape, the
non-selectable mask with auto-blank, verbatim text rendering, and the
no-leading-blank-before-first-heading rule.

Suite: 769 passed, 8 skipped.

## v0.2.85 — 2026-04-25

### security — profile `.env` and `config.yaml` are off-limits to tools

Both file tools and the `terminal` shell now refuse to read or write
the active profile's `.env` and `config.yaml`. These files hold
provider API keys, gateway tokens, and security knobs (sandbox flag,
allowlist, model choice); a prompt-injected mailbox or web page must
not be able to coax the agent into leaking or rewriting them. They
remain editable by hand or through `alpi setup`.

- `alpi/tools/_paths.py` — denylist regex now matches
  `~/.alpi/.env`, `~/.alpi/config.yaml`, and the same pair under
  any `~/.alpi/profiles/<name>/`. The error message dropped the old
  "use the terminal tool with sudo" hint, which never applied to
  user-home paths anyway.
- `alpi/tools/_guards.py` — three new dangerous-command patterns:
  `read profile secret` (`cat`/`head`/`tail`/`less`/`more`/`cp`/`mv`/
  `scp`/`rsync`/`grep`/`awk`/`sed`/`xxd`/`hexdump`/`strings`/`od`
  against profile `.env` / `config.yaml`), `write profile config`
  (`>`, `>>`, `tee` into them), and `dump environment` (bare `env`
  / `printenv`, including in pipes). `env VAR=x cmd` and
  `printenv HOME` stay allowed.

A workspace `.env` (a project's own dotenv outside `~/.alpi/`) is
deliberately untouched — the denylist scopes by path, not by basename.

23 new test cases in `tests/test_guards.py` (12 reject, 6 allow) and
`tests/test_paths_denylist.py` (12 — alpi-profile paths refused,
workspace paths with the same basename pass).

`docs/SECURITY.md` § Layer 1 lists the new path patterns and the
terminal-side counterparts; reiterates that skill scripts run inside
the parent's `os.environ` and can still enumerate secrets through
Python — closing that vector requires per-skill env scoping (own
roadmap item).

Suite: 765 passed, 8 skipped (was 734).

## v0.2.84 — 2026-04-25

### budget — daily spending ledger, profile-level cap

Every spend path through alpi now goes through one ledger and one cap.
The cap lives at the profile level (`budget.daily_usd` or
`daily_tokens` in `config.yaml`); per-peer spending sub-caps were
considered and dropped — peer trust lives in capabilities and rate
limits, not in a second ledger.

- `alpi/ledger.py` (new) — JSON ledger at
  `~/.alpi/<profile>/logs/ledger.json` with profile total + per-peer
  observability buckets, atomic writes, midnight UTC reset, and a
  context-var that lets the ALP server attribute a turn's spend to
  the remote peer that asked for it.
- `alpi/engine.py` — admit-check before every turn, record after
  each turn body and after each sub-agent (`research`, `delegate`,
  `read_image`) so the cap covers the whole tree.
- `alpi/alp/server.py` + `handlers.py` — inbound `link.ask` admits
  the same way; over-cap responds with JSON-RPC `-32005
  budget-exceeded` (`cap_kind`/`cap`/`used` in `data`). Engine
  errors now flow into the reply text instead of as a separate
  trace event so gateways with `show_tool_trace: true` don't show
  the message twice.
- `alpi/cli.py` — `alpi setup → Budget` prompts daily USD or daily
  tokens (pick-one; empty leaves the profile uncapped).
- `alpi/status.py` (new) — canonical `(label, value)` rows shared
  by the TUI `/status` panel and the Telegram `/status` shortcut so
  the two surfaces no longer drift. Telegram renders the body as a
  fenced code block to keep column alignment under MarkdownV2.

`alpi/alp/__init__.py`, `docs/CONFIG.md`, `docs/ALP.md`,
`docs/PROFILES.md`, `docs/OPERATIONS.md`, `docs/ARCHITECTURE.md`, and
`docs/ROADMAP.md` updated to describe the budget shape and to use
"workgroup" for the multi-party ALP extension everywhere
(`alpi-rooms` was the old name; the new term reflects that the
primary inhabitant is an autonomous agent, not a chat user).

The landing page picks up the budget mention as a one-line addition
to the operations card — visible without crowding the headline.

19 new tests across `tests/test_ledger.py` (15 — load/save, peer
context, clamping, stale-day reset, corrupt-file resilience,
concurrent writers, `pick-one` precedence) and `tests/test_alp_budget.py`
(3 — over-cap returns `-32005`, under-cap admits, no cap is a
no-op). Plus 1 status-panel adapter test. Suite: 734 passed, 8
skipped.

Verified live in TUI and Telegram with bob @ `daily_usd: $0.05`:
budget reached message renders cleanly in both surfaces, the
`/status` row shows `daily budget $0.0554 / $0.05 · capped`.

## v0.2.83 — 2026-04-24

### alp — inter-machine Noise_XK transport, rate limits, wizard wiring

Ships the inter-machine half of the ALP spec. Peers with an `address`
field in `peers.yaml` now route over a TCP+Noise_XK channel; the
intra-profile Unix socket path from ALP.1 is untouched.

- `alpi/alp/noise.py` — own `Noise_XK_25519_ChaChaPoly_SHA256`
  implementation on `cryptography` primitives (symmetric state, cipher
  state, Ed25519→X25519 birational derivation so peers keep one
  pinned identity).
- `alpi/alp/transport_tcp.py` — TCP framing (u16 handshake, u32 bulk
  capped at 1 MiB), handshake orchestration with timeouts, pinned-key
  cross-check between the Noise-authenticated static and
  `peers.yaml`.
- `alpi/alp/rate_limit.py` — sliding-window counter per peer, default
  60/min overridable via `peers.yaml` `rate_limit.per_minute`. Over-cap
  requests return JSON-RPC `-32005`.
- `alpi/alp/server.py` — binds the TCP listener alongside the Unix
  socket when `alp.tcp_port` is set. Shared dispatch; the TCP path
  additionally cross-checks that the envelope's claimed sender
  matches the Noise-authenticated identity before invoking the
  handler.
- `alpi/alp/client.py` — new `call_tcp()` + `call_peer()` routing by
  peer address. Existing `call()` Unix-socket signature preserved for
  intra-profile callers.
- `alpi/config.py` — new `alp` section (`tcp_host`, `tcp_port`).
  Absent → Unix-only listener.
- `alpi/cli.py` — `alpi alp start --port N --host H` flags with
  config fallback; `alpi peers ping` routes over TCP when the peer
  carries an address and prints the resolved transport in the
  response.

Wizard updates so ALP.2 is configurable end-to-end without editing
YAML by hand:

- `alpi setup → ALP service → TCP port` — sets `alp.tcp_host` and
  `alp.tcp_port`. Prompts host first (changes more often once a port
  is set), with `0.0.0.0` behind a confirm.
- `alpi setup → Peers → Add peer` — new "Remote address" prompt
  accepting `host:port`; a valid address routes that peer over TCP.
- Peer probe in the peer list now uses a real Noise_XK ping for
  peers with an address — the `?` placeholder is gone; remote peers
  surface green/grey like local ones.

17 new tests in `tests/test_alp_noise.py` (derivation, XK handshake
happy path, tampering, bad `rs`, bulk traffic, cipher state) and
`tests/test_alp_tcp.py` (ping roundtrip, silent drop on unpinned
peer, capability denial, `-32005` rate-limit trip, `call_peer`
dispatch + validation). Full suite: 715 passed, 8 skipped.

Verified live between two profiles on the same host and also over
Tailscale (listener bound to a 100.x.x.x address, dialled from
another profile via MagicDNS `<machine>.tail*.ts.net` — same code
path as real remote peers).

### spec — budget roadmap (BG)

`docs/ROADMAP.md` carries a new **BG** item that defines the spending
budget shape the agent will adopt. One ceiling per profile, expressed
as either `daily_usd` or `daily_tokens` — paid models pick the dollar
unit, local Ollama profiles pick tokens, and absent values mean no
ceiling. The same ledger covers every spending path through alpi
(interactive turns, gateways, scheduled jobs, sub-agent spawns, and
inbound ALP from peers). Per-peer spending sub-caps are intentionally
absent: peer trust lives in capabilities and rate limits, not in a
secondary spending ledger. BG is v0.3 and unblocks ALP.3 workgroups,
which double-gate posts against both each member's profile budget
and an optional per-workgroup pool.

## v0.2.82 — 2026-04-24

### site/docs — private agent network narrative

The public narrative now matches the product shape: alpi is a
profile-based personal AI agent that can grow from one terminal into a
private network across machines.

- `README.md` now leads with profiles, model/key ownership,
  multi-machine coordination, and the current ALP surface.
- Landing copy moved from a privacy-only slogan to
  `your private / agent network`, with ALP.1 local links, ALP.2
  machine links, and ALP.3 workgroups stated directly.
- ALP docs now treat ALP.1/ALP.2/ALP.3 as the current launch surface:
  Unix sockets, Noise_XK TCP, budgets/rate limits, and hub-anchored
  workgroups.
- Deployment, security, operations, profiles, config, and roadmap
  docs were aligned so the site no longer presents ALP.2/ALP.3 as
  distant work.

### tools — failure-mode + when-to-use hints on three tool descriptions

Third pass on AT (prompt + tool descriptions audit vs Hermes).
Three targeted additions; most other tools already had "Use when /
Not for / failure modes" from the earlier `ff6bb21` pass and need
no change.

- `browser.py` — added a line on what to do when `click` / `type`
  can't find an element: re-check the latest snapshot for the real
  role + accessible name, don't guess selectors blindly. Stops the
  common loop where the model keeps retrying the same wrong label.
- `search.py` — added a regex gotcha note. The pattern is a regex
  in content mode; literal `{ } ( ) | . * +` must be escaped. If a
  content search returns nothing when hits are expected, metachars
  are usually the cause.
- `stt.py` — added a "Use when" preamble so gateway voice-note
  messages reliably trigger transcription before the reply.

Skipped the Hermes audit's recommendations that didn't match reality
post-`ff6bb21`: `delegate`, `send_message`, and `research` already
carry explicit "Use when" + "Not for" sections, and the memory
"facts vs directives" rule lives in the memory tool description
with an explicit pointer from `system_prompt.md`. Duplicating would
be token tax without signal. Model-specific execution guidance (BD)
stays parked until there's an A/B measurement on `agent.log`.

## v0.2.80 — 2026-04-24

### site — header/nav unified, docs index redesigned, SEO at 100%

Second pass on the static site under `site/`.

- Single shared nav component (`renderNav()` in `build.mjs`) used by
  landing, `/docs/`, and `/docs/*`. Same HTML, same CSS, same shell
  width (1240px + `clamp(24px, 5vw, 64px)` horizontal padding),
  varying only in the breadcrumb tail: landing has no tail, `/docs/`
  shows `DOCS`, doc pages show `DOCS / {slug}`. Fixed a nasty nested
  `<a>` bug (crumbs inside the brand link) that was breaking the
  flex layout on `/docs/*`.
- Combined `alpi-logo.svg` (alpaca + wordmark, 94×42) in the header;
  `alpi-alpaca.svg` as the favicon + mask-icon. Assets reduced to
  three: logo, alpaca, brand social card (`alpi-brand.png`, 1200×800).
- Burger menu on mobile (< 760px) with slide-down drawer — JS under
  20 lines, inline in the landing, zero dependencies.
- `/docs/` rebuilt with the same `.docs > .doc` card grid as the
  landing docs section, sourced from the single `DOCS` array; title
  is now `DOCS` at H1 scale (72px / 600 / -.035em) to match the
  individual doc pages.
- SEO pass across every page: unique `<title>` and
  `<meta name="description">`, canonical URL, `robots`,
  `theme-color`, Open Graph (type/site_name/title/description/url/
  locale + image w/h/alt), Twitter Card `summary_large_image` with
  `@soyjavi` as creator/site, JSON-LD structured data (WebSite +
  SoftwareApplication + Organization on landing, CollectionPage on
  `/docs/`, TechArticle on doc pages). `sitemap.xml` (16 URLs with
  `lastmod` + priority tiers) and `robots.txt` are emitted on every
  build. Deploy URL is configurable via `SITE_URL` env var, default
  placeholder `https://alpi.satoshi-ltd.com`.
- Alignment fixes along the way: breadcrumbs baseline-match the
  "alpi" wordmark inside the logo (`margin-top:4px` on `.bp-tail`),
  `.shell` no longer shadowed by `.row` shorthand padding, `.doc`
  article no longer zeroes horizontal padding.

## v0.2.79 — 2026-04-24

### site — static marketing + docs scaffold under `site/`

Landed the first cut of alpi.site as a zero-dependency static site:
vanilla HTML/CSS/JS plus a single Node build script
(`site/scripts/build.mjs`) that reads `README.md`, `QUICKSTART.md`,
`CHANGELOG.md`, `LICENSE`, and `docs/*.md` at HEAD and bakes
`site/dist/` — landing page at `/`, doc index at `/docs/`, and one
pre-rendered HTML per doc. Versions and copy are derived from
`pyproject.toml` so a rebuild keeps the site in sync with the
shipped release; no runtime fetch from GitHub, no CORS, no API rate
limits. Ships with a tiny zero-dep Markdown renderer
(`site/scripts/markdown.mjs`) covering the subset used in the repo
(headings, fenced code, lists, tables, blockquotes, inline code,
bold/italic, links). Based on a mockup generated by `claude design`;
the mockup folder was removed after migration. Cloudflare Pages
wiring: build command `node site/scripts/build.mjs`, output
`site/dist`.

## v0.2.78 — 2026-04-24

### skills — auto-validate on every mutation

Every mutating action on a user skill (`create`, `edit`, `patch`,
`add_file`, `remove_file`) now runs the script validator
(`_skill_validate.validate_skill` — py_compile, missing imports,
OAuth race pattern, port coherence) and surfaces findings in the
tool output. The LLM sees issues immediately and can iterate in
the same turn without having to call `skill(action="validate")`
separately. 6 new regression tests in
`tests/test_skill_auto_validate.py`.

`alpi/prompts/create_skill_guide.md` extended with a Scripts
section (prefer stdlib, include a dry-run / smoke-test path,
explicit exit codes) and a note about the automatic validation —
so the LLM authors scripts knowing it will get feedback.

### skills — AO position clarified, no bundled skill shipped yet

Reverted the `@alpi/plan` experiment. It restyled output without
adding real capability and imposed a path convention users may not
want. The honest conclusion: don't ship bundled skills from a
hermes-style catalog just because BE's infrastructure is ready.
`docs/ROADMAP.md → AO` and `docs/SKILLS.md` updated to reflect the
new position: the `@alpi/*` namespace is reserved and live, but
nothing ships by default. Bundled skills land when concrete
recurring patterns justify one — not from a catalog import.

## v0.2.77 — 2026-04-24

### skills — bundled infrastructure (BE closed)

Adds a read-only namespace for skills that ship with the alpi
package. No content bundled yet — this is infrastructure only.

- **`@alpi/` namespace.** Bundled skills are addressed as
  `@alpi/<name>`. The `@` sigil is not a legal category name on
  disk, so bundled and user skills cannot collide by construction.
- **Loader.** `_bundled_root()` resolves against
  `importlib.resources.files("alpi.skills")`; `_bundled_skill(name)`
  returns the package resource for a `@alpi/*` name, or `None`.
  `_find_skill` tries bundled first, then falls through to
  `{home}/skills/`.
- **Discovery.** `skills_index_block()` (injected into the system
  prompt every turn) now lists user skills first, then a separate
  `@alpi/ [bundled]:` block with the marker visible. `skill list`
  mirrors the same ordering.
- **Write guards.** `create`/`edit`/`patch`/`add_file`/`remove_file`/
  `delete` on a `@alpi/*` name is rejected with a message pointing
  at the variant pattern (create your own under a non-`@` category).
- **Defense in depth.** `all_skills` skips any category under
  `{home}/skills/` whose name starts with `@`, so a rogue direct
  write cannot shadow a bundled skill.

`pyproject.toml` package-data extended to ship `skills/**/*`; the
`alpi/skills/` package directory is empty except for `__init__.py`.
When we land the first real bundled skill, no loader changes are
needed — drop the SKILL.md in place and it shows up.

14 new regression tests in `tests/test_bundled_skills.py`; 692 green.

Docs: `docs/SKILLS.md` gains a "Bundled vs user skills" section with
the namespace, variant pattern, and discovery ordering.
`docs/ARCHITECTURE.md` package tree + runtime note updated.

## v0.2.76 — 2026-04-24

### tui — markdown link styling + memory panel rewrite (BB closed)

**BB — shared link renderer.** Textual 8.2.3 exposes only `@click`
meta on markdown link spans, no visual style — so links rendered as
plain prose in the chat. New `alpi/tui/_links.py` monkey-patches
`MarkdownBlock._token_to_content` at import time: every span carrying
`@click` meta gets **bold + underline** appended. Idempotent install,
applied globally — works across `AssistantMessage` streaming output
AND every floating panel that uses `Markdown` (same patch, one pipeline).

Per-link hover styling is **not** addressed — Textual renders link
spans as Rich Text inside a single widget, not as per-link widgets.
A hover state would require widget-per-link rewriting of the Markdown
internals, out of scope. Deferred.

### tui — `/memory` panel rewrite

Old `/memory` wrapped each file's content in a ```markdown code block```
so everything rendered with the `.code_inline` accent color. Inconsistent
and the code-block hid real markdown structure.

New layout: three stacked sections, each with a `Static` accent-colored
header + `Markdown` widgets for the content. `USER.md` and `MEMORY.md`
are split on `§` and rendered as N separate `Markdown` widgets so entries
appear visually separated (the `§` character no longer leaks into the
render). `AGENT.md` renders as one unit since it's already markdown.

New `.memory-section` CSS class; all `FloatingPanel Markdown` widgets
share transparent background + tight margins so panels stay compact.

### prompts / template

`alpi/prompts/default_agent.md` — `# Identity` / `# Voice` / `# Defaults`
headers downgraded to `##`. Textual renders `h1` centered (it reads as
"document title" styling); `h2` is left-aligned which is the right look
for in-document sections. Applied to the template that seeds fresh
profiles.

### memory tool / description

`§` entry delimiter guidance tightened (English only, terse). New
`fuzzy_find_unique_entry` error now appends a "note: `§` is the entry
delimiter, not content — strip it from your match string" hint when the
match string contains `§`. Catches the common LLM mis-construction
observed on long-running profiles with many entries.

### tui — streaming input lag

Fixed: typing in the TUI lagged while the assistant streamed output.
Cause: `AssistantMessage.append(delta)` spawned one `asyncio.create_task`
per delta (~60/s from the LLM), each re-parsing markdown — saturating the
event loop so key events queued behind paint work. Fix: deltas now
accumulate in a buffer and a single timer flushes them at 12.5 Hz
(`_FLUSH_INTERVAL = 0.08`). One coalesced write per tick instead of
dozens. Input stays responsive mid-stream.

### docs

`docs/ROADMAP.md` — BF (drop `§` delimiter) removed. Pre-existing
profiles handle it fine with the new description guidance; refactoring
the on-disk format isn't worth the migration surface right now.

## v0.2.75 — 2026-04-24

### wizard / cli — profile lifecycle + polish

- New setup entry `alpi -p <name> setup → Delete profile` (non-default
  profiles only). One-shot teardown: summary → warn about installed
  services → typed-name confirmation → uninstall gateway / schedule /
  alp services → `rmtree` the profile home → exit. Collapses what
  used to be "uninstall each service manually, then run `alpi profile
  remove X`" into a single guided action.
- `alpi profile remove <name>` CLI now redirects to the wizard when
  services are installed, instead of listing per-service uninstall
  hints. CLI remains for the happy path (empty profiles, scripting).
- "Did you mean…?" suggestions in CLI when the target id doesn't
  exist: `alpi profile remove` (closest profile name), `alpi peers
  remove` / `alpi peers ping` (closest peer id), `alpi schedule fire`
  (closest job id). Shared `_suggest()` helper using `difflib`.
- Fixed the misleading "→ Gateway service" hint in `profile remove`
  error — it now names the actually-installed service(s) and points
  at the wizard.
- Dropped `.githooks/` (pre-push CHANGELOG regen). We've been
  running `alpi release notes` manually at release time; the hook
  was opt-in and unused.

### docs
- `docs/PROFILES.md` — documents the wizard-redirect flow.
- `docs/ARCHITECTURE.md` — setup menu outline lists "delete profile".

## v0.2.74 — 2026-04-24

### schedule — ad-hoc job fire (BA closed)

Closes the tightest feedback loop in the schedule lifecycle: add a
cron, verify it works, without waiting for the cron window.

- `alpi/scheduler/run.py::fire_by_id(home, job_id)` — loads
  `jobs.json`, looks up the id, runs the job through the same path
  the daemon tick uses (`run_job` — threat scan + `alpi chat --once`
  subprocess + delivery). Updates `last_run_at`; does **not**
  consume `once` jobs (ad-hoc fire is deliberate testing, not the
  natural trigger).
- CLI: `alpi schedule fire <job_id>`. Exit code 1 on failure.
- Tool: `schedule(action="fire", id=...)` so the LLM can self-test
  a job right after adding it.
- Description updated to list the new action + caveat about
  once-jobs not being consumed.

5 new regression tests in `tests/test_schedule.py`; 675 green.

## v0.2.73 — 2026-04-24

### skills / memory / docs — stop shipping what we don't use

- Deleted the `alpi/skills/` package directory. The only blueprint
  there (`meta/consolidate-memory/SKILL.md`) never reached profiles
  — the `skill` tool only searches `{home}/skills/` and nothing
  seeds the bundle. Keeping dead literature shipped with the binary
  violated the "ship what you use" posture. Runtime skills system
  is untouched — `~/.alpi/skills/<category>/<name>/` still works,
  the `skill` tool still creates / edits / runs user skills, and
  the `/skills` TUI panel still lists them.
- `pyproject.toml` package-data no longer includes `skills/**/*.md`.
- `alpi/tools/memory.py` — the ≥80% hint now says *"consider
  consolidating old entries before adding more"* (generic,
  actionable) instead of pointing at a skill that doesn't exist.
- `alpi/prompts/system_prompt.md` — same substitution: at ≥80%,
  prefer `replace` / `remove` over `add`.
- `alpi/prompts/create_skill_guide.md` — drops the "search the
  bundled `alpi/skills/`" step, since there's nothing to search.
- `docs/ARCHITECTURE.md` — package tree no longer lists `skills/`
  under `alpi/`. Added a bridge paragraph pointing at the Profile
  home layout where runtime skills / sessions / memories / logs /
  ALP state actually live. Skills core-systems section unchanged.
- `docs/ROADMAP.md` — **BE** reframed as "bundled skills
  infrastructure (loader; no content yet)" rather than a loader
  pinned to a specific blueprint. **AO** no longer claims
  consolidate-memory is bundled.
- Two regression tests in `tests/test_memory_tool_v2.py` now
  assert the new generic "consolidating" wording.

## v0.2.72 — 2026-04-24

### memory — v2 rules (AI partial)

Renames PERSONALITY.md → **AGENT.md** across the codebase, prompts,
tests, and docs. The user/agent pair (`USER.md` vs `AGENT.md`) is now
symmetric and readable. The `memory` tool enum, template file
(`alpi/prompts/default_agent.md`), home helper, and tool descriptions
that list memory files are all updated. File migration on existing
profiles is manual — no auto-migration per project policy.

- **A** — AGENT.md now uses paragraph-level fold + Jaccard dedup
  (`is_duplicate_stanza` in `alpi/memory.py`) instead of raw substring
  match. Paraphrased voice blocks no longer accumulate. Error text
  nudges toward `replace` when the user is refining an existing rule.
- **B** — `alpi/prompts/default_agent.md` "Edit me" footer rewritten
  to teach the correct `replace` vs `add` pattern (append new
  sections; replace existing lines; never replace unrelated rules
  to "make room").
- **C** — cross-file duplicate check: `add` to USER.md (or MEMORY.md)
  rejects when the content is already in the other file, pointing
  the caller at the correct target. Prevents the common failure
  where a fact (e.g. vehicle list) lands in both files.
- **E** — operational-state warning: `add` returns a ⚠ line in the
  tool output when the entry matches a session/chat/interaction log
  pattern (`chat_id`, `session_id`, `first interaction`, 5+-digit id
  combined with a date). Non-blocking — the LLM sees the hint; it
  decides whether to honour the user's explicit target.
- **F** — memory char limits bumped: `USER.md` 1375 → **3000**,
  `MEMORY.md` 2200 → **5000**. When either target reaches ≥ 80%
  usage, the tool response carries a `— run the consolidate-memory
  skill` hint so the model can escalate to consolidation before
  adding more.

**D deferred** — the "≤1-token entry dedup" idea (lower Jaccard
guard from 2 → 1) produced false positives on entries that shared
one generic content token (`Dato A` vs `Dato B` both reduced to
`{dato}`). Kept the guard at 2.

**G deferred** — periodic self-consolidation trigger stays out:
explicit over-engineering per the "no fails, no over-engineering"
directive. The user or the model can run the `consolidate-memory`
skill on demand.

11 new regression tests in `tests/test_memory_tool_v2.py`.

## v0.2.71 — 2026-04-24

### engine / prompts (AT partial — 4 of 5 candidate edits applied)
- new per-surface platform hint in the system prompt: `_platform_hint()` in `alpi/engine.py` reads `ALPI_PLATFORM` env and injects a matching block (`cron`, `telegram`, `email`, `gmail`). Gateway (`alpi/gateway/run.py`) sets it to `msg.platform` on every spawn; scheduler (`alpi/scheduler/run.py`) sets it to `cron`. TUI gets no hint (baseline). Concrete wins: cron jobs stop asking phantom users for clarification; Telegram replies arrive Markdown-aware; email replies arrive plain-text-only. 6 regression tests.
- `memory` tool description now enforces declarative phrasing with ✓/✗ examples ("User prefers concise replies" ✓ — "Always reply concisely" ✗). Imperative memory entries were being re-read as directives across sessions.
- `skill` tool description leads with "use when" purpose instead of directory layout.
- `email` tool description leads with "Read, search, send, or move email. Use when…" instead of "Manage the mailbox".
- `alpi/prompts/system_prompt.md` — dropped the "Past conversations" section; `session_search` tool description already carries the same rule. Net: ~10 fewer tokens injected on every turn.

### roadmap
- new **BD** item added for v0.3: model-aware tool-use-enforcement guidance (Claude/MiMo brevity, GPT/Codex/Gemini full block) — requires an A/B measurement on `agent.log` before applying.

### docs
- `docs/ARCHITECTURE.md` — system-prompt assembly section now documents the `ALPI_PLATFORM` contract between callers (gateway, scheduler) and the engine.

## v0.2.70 — 2026-04-23

### license
- repo re-licensed under **Business Source Licence 1.1** (`LICENSE`). Licensor: Satoshi Ltd. Change Date 2030-04-23 → Apache 2.0. Additional Use Grant lets individuals run alpi freely on machines they control for personal / research / non-commercial purposes; commercial production deployment by a legal entity requires a licence from `info@satoshi-ltd.com`. `pyproject.toml` license field updated to `BUSL-1.1`; README License section rewritten to explain the split.

### docs
- repo rooted in Satoshi Ltd.'s six operating principles (Privacy by Design, User Sovereignty, Security First, Open Source, Zero Knowledge, Digital Sovereignty) across `README.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/ALP.md`. Each doc now explicitly maps its content to the principle it expresses.
- new [`QUICKSTART.md`](QUICKSTART.md) at repo root — first-day walkthrough: install → model → workspace → first chat → resume → gateway → second profile → ALP → doctor.
- new [`docs/PROFILES.md`](docs/PROFILES.md) — canonical reference for alpi's core isolation primitive (home resolution, what's isolated per profile, identity in ALP, creation patterns, cost).
- new [`docs/DEPLOYMENTS.md`](docs/DEPLOYMENTS.md) — six topologies from laptop-only to enterprise private agent networks, each with ASCII diagram, trade-offs, and BSL licence boundary.
- new [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — runbook: the five logs, service lifecycle, upgrades, backup + restore, ALP identity rotation, monitoring, disaster recovery, common failure modes.
- `docs/ROADMAP.md` sanitised — 64 shipped-item rows + the "Done — v0.1 + shipped v0.2 items" commit table dropped (they duplicated CHANGELOG which already reconstructs them from `git log`). New top table lists only open items with target version + status.

## v0.2.69 — 2026-04-23

### models
- `docs/MODELS.md` rebuilt around a neutral 3-tier recommendation sourced from a standalone deep-research pass (Tier 1 quality, Tier 2 cost/service, Tier 3 Ollama) with production-setup suggestions. Personal-usage section and deliberately-left-out list dropped to keep the doc unbiased.
- fresh profile scaffold (`config.seed_defaults`) no longer pins a default model — `config.yaml` ships with `model: ""` so the setup wizard is the canonical picker.
- `docs/CONFIG.md` updated to reflect the empty default.

## v0.2.68 — 2026-04-23

### alp (Alpi Link Protocol — ALP.1 closed)
- new `alpi/alp/` package: Ed25519 identity, signed JSON-RPC envelope with replay cache, fail-closed peer list, Unix-socket server + client. `link.ping`, `link.ask` (reject-fast reentrancy), `link.cancel` (idempotent interrupt).
- `peer` tool for LLM-driven cross-profile calls. TUI `@peer rest…` gesture with strict leading-`@` rule and `/peers` panel. Telegram / email / webhook gateway inbound interception hits the same code path without firing the local LLM.
- `alpi alp start|stop|restart` + service install via `alpi setup → ALP service` (launchd / systemd). Doctor granular sub-checks: Identity (key loadable), Socket (listening), Peers (reachable).
- `alpi setup → Peers` wizard: identity page with clipboard copy, probe-based ●/○/? status list, add/remove/inspect flows.
- `alpi peers key|list|add|remove|ping` CLI group for scripting.
- docs: `docs/ALP.md` spec v1 (envelope, verbs, errors, security), `docs/ROADMAP.md` with ALP.1 shipped and ALP.2 / ALP.3 initially tracked for later, `docs/ARCHITECTURE.md` layout + commands.

### setup
- health-check row no longer blocks menu render on 5–10s of live network probes — status reads "open to run checks", actual checks run on-demand when the user opens the page.

## v0.2.54 — 2026-04-23

### gateway
- per-chat session threading (AN closed) + AU backlog entry (`e0f093d`)

## v0.2.1 – v0.2.53 — 2026-04-21 → 2026-04-23

Two days of rapid iteration after the v0.2.0 split. Patch bumps
collapsed into thematic groups; full per-commit detail in `git log`.

### brand
- Project renamed `alf` → `alpi` across the codebase, docs, and
  config paths (~130 files touched).

### TUI
- Theme system + floating panels + scaffold polish (foundation for
  every later panel).
- New panels: `/model`, `/mcps`, `/tools`, `/help` palette; unified
  list-row shape across selectable panels (AH closed).
- Profile disk size + accent diamond + abbreviated path in the
  profile-list top bar; adapts to narrow widths.
- `tui.auto_resume` flag so bare `alpi` continues the last session
  (AL closed).
- Drop questionary; menus + text inputs rebuilt directly on
  `prompt_toolkit`.

### setup wizards
- Normalised UX across every wizard.
- New wizards: Cleanup (AA), Gateway service install/uninstall
  (AB), live Doctor (AD/AE/AF), first-time help text in
  Gateway/MCP wizards (AG), Model wizard reordered (Ollama first).
- `.env.example` scaffold dropped; profile owns its own `.env` (AP).

### voice + gateways
- Voice pack: `tts` + `stt` tools + Telegram voice inbound/outbound
  (M closed).
- TTS autoplay off on gateway surfaces; terse outputs by default.
- Gmail OAuth2 gateway + mail tool dispatch (T closed); internal
  rename `email/` → `mail/imap/`.
- Telegram offset persistence + backlog catch-up logging.

### tools
- `browser`: Playwright with stealth-by-default, humanised typing,
  optional vision; camoufox dismissed.
- `read_image`: vision tool with URL/SVG/model-override (D);
  auto-resize oversized images before vision (S closed).
- `research` + `delegate`: batch parallel tasks (R.3); `delegate`
  becomes write-capable with file/terminal/web toolsets (R.2);
  `research` prefixes inner emit with step counter (R.1).
- `skill`: new `validate` action for correctness checks (Q
  closed); `tools:` field description tightened.
- Removed: `config` tool (config is user-owned).

### security
- Three-severity command gate for terminal (W closed); approval
  panel restyled; YOLO removed.
- Tool budget + OSV malware check + schedule threat-scan (security
  pack).
- Sandbox promoted from "experimental" to per-profile opt-in;
  `allow_network=off` now blocks Python-native network tools too.
- `tos`: removed C (Codex OAuth) and V (Anthropic OAuth) from
  backlog — ToS-violation principle locked in.

### release pipeline
- Auto-generated CHANGELOG from git history (AC closed) +
  pre-push CHANGELOG hook.
- `cli`: surface shrunk, logs unified.
- Filesystem tidied: `PERSONALITY.md` → `memories/`, `gmail_token`
  → `secrets/`.

### MCP + providers
- OpenAI-compat tool names, curated provider lists, context-window
  awareness.
- `/tools` skips MCP-registered tools (rendered in `/mcps` instead).
- Ollama promoted to first-class provider; generic custom slot
  removed.

## v0.2.0 — 2026-04-21

### docs
- add MODELS.md — tiered model recommendations for agent use (`df29cfc`)
- record identity-wizard decision as rejected (`60122b7`)
- split CONTEXT into ARCHITECTURE + ROADMAP, position alf as lighter Hermes, bump to v0.2.0 (`6b946e4`)

### fix
- propagate active profile to tool context + sharpen memory prompt (`1470bdb`)

### gateway
- stream tool traces + typing indicator; simplify allowlist (`fe3a3d4`)

### gateway/schedule
- fail fast if the profile has no usable workspace (`04bdaba`)

### schedule
- fix immediate-fire, UTC vs local tz, duplicate delivery (`3dd4522`)
- kind=once and LLM time grounding (`1fc3610`)

### skills
- unified tool, subdir contract, live-by-default, path guards (`2e67830`)
- auto-inject index into system prompt + render skill name in tool cards (`4035327`)

### tooling
- level-2 comment cleanup across alf/ (`a07e40a`)

### tools
- rename delegate → research, depth tiers driven by config (`d2ceb74`)

### tui
- surface inter-tool prose + reasoning tokens in live indicator (`62f7fa7`)
- reasoning persists across sessions, show_reasoning toggle, tighter layout (`fd1fec4`)

### web_search
- dedup by domain + lean description (`b04b394`)

### misc
- remove stray test artifacts and fix layout in README (`56d1711`)
- send_message tool + delivery refactor (`6e31ace`)
- schedule daemon: tool + CLI + rename from cron (`2245e42`)
- install/uninstall for gateway + schedule (launchd + systemd) (`cd62da0`)
- profile CLI + drop all migration/legacy code (`630f97c`)
- email subsystem + alf setup UX polish (`c67e618`)
- email gateway channel + per-platform config namespace (`4691df8`)
- mcp client — user-configured MCP servers as alf tools (`0d376ac`)
- setup UX: shared ui primitives, profile-scoped status, CLI polish (`7a81770`)
- memory tool: compress description to Hermes-style, keep all invariants (`b214ce6`)
- tool descriptions: compress terminal/email/schedule/send_message/session_search (`19f1287`)
- config polish: minimal seed, config tool, /new session, accent spinners (`2dadc09`)
- tool descriptions: restore CALL directives + English-only language rule (`6be1685`)
- security phase 1: terminal denylist, SSRF block, tool-output injection scan (`a54d99d`)
- security phase 2: opt-in OS sandbox (sandbox-exec / bubblewrap) (`e78b428`)
- merge glob + grep into search; fix relative-path resolution (`2b73091`)
- file tools: drop workspace wall, match terminal's denylist posture (`3e2dc29`)
- skill tool: patch/view actions, state/ subdir, scanner beef-up (`211c022`)

## v0.1.0 — 2026-04-19

### misc
- initial commit — alf v0.1 (`a0c7630`)
