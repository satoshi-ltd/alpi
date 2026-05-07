# Umbrel Store Submission

This file tracks the official Umbrel App Store submission for Alpi.

## Release checklist

- [ ] Build and publish `satoshiltd/alpi-umbrel:0.4.9` for
  `linux/amd64` and `linux/arm64`.
- [ ] Verify the Docker Hub image digest and keep the tag immutable
  after submission.
- [ ] Test install on a physical Umbrel device.
- [ ] Restart the app and confirm `/data/.alpi` persists.
- [ ] Run `alpi setup` from the browser terminal after exiting the TUI.
- [ ] Run `alpi doctor` from the browser terminal.
- [x] Capture 3-5 screenshots at 1440x900.
- [x] Export a 256x256 SVG icon with no rounded corners.
- [ ] Open a pull request against `getumbrel/umbrel-apps`.

## Docker image

Manual publish:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t satoshiltd/alpi-umbrel:0.4.9 \
  -f deploy/umbrel/alpi/Dockerfile \
  --push .
```

GitHub Actions publish:

1. Add repository secrets:
   - `DOCKERHUB_USERNAME`
   - `DOCKERHUB_TOKEN`
2. Run the `publish-umbrel` workflow manually with tag `0.4.9`.

## Files for `getumbrel/umbrel-apps`

Copy these files into a new `alpi/` directory in a fork of
`getumbrel/umbrel-apps`:

- `deploy/umbrel/alpi/docker-compose.yml`
- `deploy/umbrel/alpi/umbrel-app.yml`
- `deploy/umbrel/alpi/exports.sh`

Keep `deploy/umbrel/alpi/Dockerfile` in the Alpi repository; the
official app-store repo only needs to pull the published image.

Before opening the PR in `getumbrel/umbrel-apps`, update two fields in
the copied files:

- In `alpi/docker-compose.yml`, pin the image by digest:
  `satoshiltd/alpi-umbrel:0.4.9@sha256:<digest>`
- In `alpi/umbrel-app.yml`, set `submission:` to the URL of that PR.

Umbrel app versions should track the Alpi release version exactly.
For example, Alpi `0.4.9` ships as publish-umbrel tag `0.4.9` and
manifest version `0.4.9`.

## Pull request

Title:

```text
App Submission: Alpi
```

Body:

```md
# App Submission

### App name
Alpi

### 256x256 SVG icon
Use `assets/umbrel/alpi-icon.svg`.

### Gallery images
Use:
- `assets/umbrel/alpi-screenshot-01.png`
- `assets/umbrel/alpi-screenshot-02.png`
- `assets/umbrel/alpi-screenshot-03.png`
- `assets/umbrel/alpi-screenshot-04.png`

### I have tested my app on:
- [ ] umbrelOS on a Raspberry Pi
- [x] umbrelOS on an Umbrel Home
- [ ] umbrelOS on Linux VM
```

## Review notes

- The app uses Umbrel's authenticated `app_proxy`.
- The browser surface is a terminal session running the existing Alpi
  TUI via `ttyd`.
- `alpi daemon start` runs as the container-managed background service.
- `ALPI_PLATFORM=umbrel` prevents interactive setup from attempting
  host systemd installation inside the container.
- Profile state is persisted under `/data/.alpi`.
- The host Unix socket and raw profile files are not exposed to the
  browser.
