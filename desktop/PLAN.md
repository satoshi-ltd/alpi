# desktop — alpi desktop app plan

Living plan for the `feat/desktop-app` branch (item **AX-desktop**, v0.4).
Updated as decisions land. Source of truth for the rationale; the
roadmap (`docs/ROADMAP.md`) carries the headline.

## Goal

A native-feeling desktop app for macOS first, Linux second, that lets
the creator and any future user:

- See the status of `alpi service` and whether updates are available
  (tray icon with badge, like Ollama's download dot).
- Browse and switch profiles.
- Browse and chat with peers (chat surface mirroring the reference UX:
  sidebar with sessions, chat pane, model picker, send composer).
- Browse and act on workgroups (post, read transcript, leave/pause).

Hard constraints inherited from alpi's posture:

- The app is **a filesystem viewer / wizard for the local profile**,
  not an ALP peer. It reads `~/.alpi/<profile>/` directly using normal
  filesystem permissions (the same trust boundary the user has when
  they `cat` a file in the terminal). No keypair, no pairing, no
  `peers.yaml` entry. Rationale: `peers.yaml` exists to gate
  *external* agents (other machines, federated workgroups). The local
  GUI shares the user's filesystem trust — adding a pairing dance is
  bureaucracy without security gain.
- The agent itself stays in `alpi service`. The app does not run an
  LLM, does not own tools, does not duplicate security.
- For **action** surfaces (chat, post to workgroup) — Hito 3+ — the
  right design is a Unix-socket bypass on `alpi service`: requests
  arriving over the local Unix socket skip the `peers.yaml` lookup
  because socket file permissions (mode 0600) already prove same-user.
  Until that bypass lands, the app is read-only.

## Stack — final decisions

| Layer | Choice | Why |
|---|---|---|
| Shell | **Tauri 2.x** (Rust + system WebView) | Native window chrome, vibrancy, tray, signed `.dmg`/`.AppImage`, ~10 MB binaries, mature distribution story. Beats Electron (fat) and pywebview (Linux GTK fragility, PyInstaller distribution pain). |
| Frontend framework | **React 19 + Vite** | Most documented, what the reference (Ollama) uses, mature ecosystem for chat surfaces. |
| Frontend language | **Plain JavaScript** (`.jsx`) | Hard project rule: no TypeScript anywhere. Vite template `react` (not `react-ts`). |
| Styling | **CSS Modules + `tokens.css`** | No Tailwind, no PostCSS step beyond what Vite does natively. Project rule: minimize dependencies. macOS-native look comes from system tokens (`-apple-system-label`, `system-ui` font, etc.) declared once in `tokens.css`. |
| Components | **Hand-rolled in CSS Modules** | No UI kit. Reach for Radix primitives only for components where a11y / focus-management correctness clearly justifies the dep (e.g. modal, dropdown). Default is hand-rolled. |
| State | **Zustand** | Lightweight (~1 KB), no boilerplate. Acceptable dep under the minimize-deps rule. |
| Tauri plugins | None in Hito 1. `tauri-plugin-window-vibrancy` lands in Hito 2 for sidebar blur, `tauri-plugin-updater` in Hito 4 for the tray badge. Add only when needed; declare minimum capabilities. |
| Rust crates | `serde`, `serde_json`, `dirs` | Hito 1 reads files; nothing more. ALP/Ed25519 deps return only when the Unix-socket bypass + action surfaces land (Hito 3+). |

## Architecture

```
┌─────────────────────────────────────────────┐
│  desktop (Tauri app)                        │
│  ┌──────────────────────────────────────┐   │
│  │ React + Vite + CSS Modules           │   │
│  │  - status pill (running/offline)     │   │
│  │  - profile selector                  │   │
│  │  - stat cards (peers, wgs, sessions, │   │
│  │    skills, memory)                   │   │
│  │  - sheet view for raw files          │   │
│  └────────────┬─────────────────────────┘   │
│               │ tauri::invoke               │
│  ┌────────────▼─────────────────────────┐   │
│  │ Rust backend                         │   │
│  │  - home::resolve_home(profile?)      │   │
│  │  - state::snapshot() → service +     │   │
│  │    counts + agent_md + peers_yaml    │   │
│  │  - state::list_profiles              │   │
│  │  - state::read_file_in_home          │   │
│  └────────────┬─────────────────────────┘   │
└───────────────┼─────────────────────────────┘
                │ filesystem reads (no IPC)
                ▼
              ~/.alpi/<profile>/
              ├── service.pid     (read for status)
              ├── alp/peers.yaml  (count + raw view)
              ├── memories/       (size + AGENT.md)
              ├── sessions/       (count)
              ├── skills/         (count)
              └── alp/workgroups/ (count)
```

The agent itself stays in `alpi service` (Python). The desktop app
never speaks ALP in Hito 1-2 — pure filesystem reads with the same
permission boundary the user has at the shell.

**Action surfaces (Hito 3+) reach for `alpi service`** via a Unix-socket
bypass to be added on the service side: requests over the local socket
skip `peers.yaml` lookup because socket file permissions (mode 0600)
already prove same-user. That bypass is a small change in
`alpi/alp/server.py` and lands as part of Hito 3, not earlier.

## Hitos

Schedule in part-time weeks. Each hito is shippable + demoable on its
own.

### Hito 1 — wizard (read-only viewer)

- Tauri scaffold under `desktop/`.
- Filesystem-reader Rust commands: `profiles`, `get_snapshot`,
  `read_file`, `workgroups`.
- React wizard UI: status pill, profile selector, stat cards
  (peers / workgroups / sessions / skills / memory size), sheet view
  for raw `peers.yaml` and `AGENT.md`.

**Done when:** `pnpm tauri dev` opens the window, the wizard renders
status + counts for the default profile with `alpi service` either
running or stopped, no pairing required.

### Hito 2 — sidebar nav + per-section pages

- Sidebar split: Profiles · Peers · Workgroups · Sessions · Skills.
- Each section has its own page (list + detail), reading directly from
  the profile dir.
- Tray icon reflects service status (running / offline).
- `tauri-plugin-window-vibrancy` for translucent sidebar.

### Hito 3 — actions (chat with peers + workgroup posts)

- Add Unix-socket bypass in `alpi/alp/server.py` so local clients skip
  `peers.yaml` lookup.
- Bring back the Rust ALP client (envelope + Ed25519 sign) — but now
  using the profile's own keypair, talking to its own service over the
  bypass.
- Chat composer: `link.ask` to a peer, render reply.
- Workgroup view: `workgroup.pull` transcript, `workgroup.post`
  composer.

### Hito 4 — updater + settings + signed `.dmg`

- `tauri-plugin-updater` polls `alpi update` cache, surfaces tray badge.
- Settings panel: switch active profile, edit a small subset.
- `tauri build` → signed `.dmg` for macOS (Apple Developer ID assumed
  available — if not, ad-hoc signed for personal use).

### Hito 5 — Linux `.AppImage` (later, scope-permitting)

- `tauri build --target` for `x86_64-unknown-linux-gnu` and `aarch64`.
- Vibrancy degradation: Linux fallback to opaque sidebar.

## Open scoping question (carried from chat — answer pending)

The roadmap commits v0.4 to ALSO ship BC (audit), AV (env scoping), AW
(backup), Matrix gateway, BF 1-3, BG. The desktop app at this scope is
6-10 part-time weeks. Two options:

1. **Reescalar v0.4** around the desktop app; BC/AV/AW shift to v0.4.x
   patches or v0.5.
2. **Keep original scope**, accept the app's first release sits past
   v0.4 cut with only Hitos 1-2.

Decision pending. Hito 1 is safe to start under either. `docs/ROADMAP.md`
gets updated once decided.

## Repository layout (current)

```
desktop/
├── PLAN.md                  # this file
├── README.md                # how to open / close / develop
├── package.json
├── pnpm-lock.yaml
├── vite.config.js
├── index.html
├── src/                     # React frontend (.jsx)
│   ├── main.jsx
│   ├── App.jsx
│   ├── App.module.css
│   └── styles/
│       ├── tokens.css
│       └── reset.css
└── src-tauri/               # Rust backend
    ├── Cargo.toml
    ├── tauri.conf.json
    ├── build.rs
    ├── icons/
    └── src/
        ├── main.rs
        ├── lib.rs           # #[tauri::command] surface
        ├── home.rs          # ~/.alpi/<profile>/ resolution
        └── state.rs         # snapshot, profiles, file reads
```

## Risks & mitigations

- **Tauri 2.x capability surface drift** — we declare too much, app
  becomes a target. Mitigation: only `core:default` in Hito 1; add
  capabilities one at a time with a one-line note per addition.
- **macOS code signing & notarization** — friction for distribution.
  Mitigation: ad-hoc signing for dev; Developer ID + notarization once
  there's a real release. Document the steps in `desktop/README.md`.
- **Rust learning curve for the maintainer** — risk of stalling.
  Mitigation: Hito 1 keeps Rust surface ~150 LOC of pure stdlib;
  React layer carries the iteration weight.

## What this app explicitly does NOT do

- Run an LLM. Own tools. Hold secrets.
- Register itself as an ALP peer or write to `peers.yaml`.
- Mobile (iOS / Android) — that's `AX-mobile` in v0.5.
- Standalone mode (no `alpi service` running) — degrades to "service
  offline" message; does not try to start the agent.
- Theme marketplace, plugins, extensions. Boring shell on the agent.
