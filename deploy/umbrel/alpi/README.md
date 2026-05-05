# Alpi on Umbrel

This package is the Umbrel app-store shape for Alpi.

It intentionally does not ship a separate web dashboard. Umbrel opens a
browser surface, so the package serves the existing Alpi TUI through
`ttyd` behind Umbrel's authenticated `app_proxy`.

## Runtime shape

- `/data` is the container home directory.
- `/data/.alpi` is the persistent Alpi root.
- Umbrel binds `${APP_DATA_DIR}/data` from the app's host-side data
  directory to `/data` in the container. Container updates recreate the
  container, but they do not replace `${APP_DATA_DIR}/data`, so the
  profile survives normal app updates and restarts.
- `alpi daemon start` runs in the background for gateways, schedules,
  ALP, workgroups, and host verbs.
- `ttyd` listens on port `8080`, launches `alpi` first, and drops to a
  shell when the TUI exits so setup and diagnostic commands remain
  available.
- `ALPI_PLATFORM=umbrel` tells interactive commands that the daemon is
  already managed by the container entrypoint, not by systemd.
- Host API WebSocket traffic for paired desktop / mobile clients is
  published on TCP port `49200`.
- By default the pairing QR advertises Umbrel's `.local` hostname. For
  Tailscale or MagicDNS access, open `alpi setup` → `Devices` →
  `Network` and set the advertised host explicitly.
- The host Unix socket is not exposed to the browser or to Umbrel.

The Docker image downloads the official `ttyd` release binary for
`amd64` or `arm64` during build and verifies it with SHA256.

## Build locally

From the repository root:

```bash
docker build -t satoshiltd/alpi-umbrel:0.4.3 -f deploy/umbrel/alpi/Dockerfile .
```

## Run locally

```bash
docker run --rm -it \
  -p 8080:8080 \
  -p 49200:49200 \
  -v alpi-umbrel-data:/data \
  satoshiltd/alpi-umbrel:0.4.3
```

Open `http://localhost:8080` to use the TUI.

## Backup and restore

Umbrel persists the profile under `${APP_DATA_DIR}/data/.alpi`.
Inside the TUI or a container shell, use Alpi's encrypted archive flow:

```bash
alpi backup create
alpi backup restore <archive>
```

The volume can also be backed up by Umbrel, but the encrypted archive is
the portable format for moving a profile between machines.

## Store assets

Submission assets live in `assets/umbrel/`:

- `alpi-icon.svg`
- `alpi-screenshot-01.png`
- `alpi-screenshot-02.png`
- `alpi-screenshot-03.png`
- `alpi-screenshot-04.png`
