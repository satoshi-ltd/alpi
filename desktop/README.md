# alpi · desktop

A read-only wizard over your local `~/.alpi/` profile. macOS first,
Linux next. See [`PLAN.md`](./PLAN.md) for the full hito-by-hito plan.

The app is **not** an ALP peer. It reads the profile directory directly
and never writes to `peers.yaml`. No pairing, no keypair, no setup
beyond launching it.

## Prerequisites

- Rust (stable) — `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- pnpm — bundled via Corepack on Node 24+, or `npm i -g pnpm`
- An `alpi` install (the app reads `~/.alpi/`; the service does not need
  to be running for the wizard to render).

## Open the app

From `desktop/`:

```sh
pnpm install              # first time only
pnpm tauri dev            # launches the window in dev mode
```

`pnpm tauri dev` starts Vite + Tauri together. The window opens once
the Rust binary finishes building (~15 s after the first big build).
Hot-reload is on for both the React side and the Rust side — saving a
file rebuilds and refreshes automatically.

## Close the app

Three equivalent ways:

- **⌘Q** in the app window (or click the red traffic light) — quits
  the window cleanly.
- **Ctrl+C** in the terminal where you ran `pnpm tauri dev` — kills
  Vite + the Tauri binary.
- `pkill -f alpi-desktop` from any other terminal if it ever gets
  stuck.

## Pick a profile

By default the app shows the profile at `~/.alpi/`. If you have other
profiles under `~/.alpi/profiles/`, the header shows a dropdown to
switch. To force a profile from the start, set the env var when you
launch:

```sh
ALPI_PROFILE=alice pnpm tauri dev
ALPI_HOME=/custom/path pnpm tauri dev
```

These match `alpi/home.py` exactly, so what the CLI sees is what the
app sees.

## What's wired (Hito 1)

- Tauri 2 shell, native window with overlay title bar, vibrancy in the
  header, system fonts.
- React 19 + Vite, plain JavaScript (no TypeScript).
- CSS Modules + a `tokens.css` driven by system colors and fonts.
- Filesystem-only reads. Rust deps: `serde`, `serde_json`, `dirs`. No
  ALP, no Ed25519, no Tokio.
- Tauri commands: `profiles`, `get_snapshot`, `workgroups`, `read_file`.
- Wizard view: status pill (running / offline), service card (home,
  pid, socket), stat cards (peers, workgroups, sessions, skills,
  memory size), sheet view for raw `peers.yaml` and `AGENT.md`.

## What's not yet

- Sidebar nav per section, tray icon — Hito 2.
- Chat with peers, workgroup posts (this needs a Unix-socket bypass
  on `alpi service`) — Hito 3.
- Updater badge, settings, signed `.dmg` — Hito 4.
- Linux `.AppImage` — Hito 5.

## Production build

Not for Hito 1. Once we get there:

```sh
pnpm tauri build          # produces .dmg under src-tauri/target/release/bundle/
```
