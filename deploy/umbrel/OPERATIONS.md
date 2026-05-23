# Umbrel operations

This document is the step-by-step manual for rebuilding, publishing,
testing, and updating the Alpi Umbrel package.

Umbrel package versions should match Alpi versions exactly.

Examples:

- Alpi `0.4.47` -> publish-umbrel tag `0.4.47`
- Alpi `0.4.47` -> `umbrel-app.yml` version `0.4.47`

## 1. Bump the Umbrel package version

When Alpi ships a new version, update these files:

- `deploy/umbrel/alpi/docker-compose.yml`
- `deploy/umbrel/alpi/umbrel-app.yml`
- `deploy/umbrel/alpi/README.md`
- `.github/workflows/publish-umbrel.yml`
- `deploy/umbrel/SUBMISSION.md`
- tests that assert the image tag and manifest version

The Docker image tag and the Umbrel manifest version should stay in
lockstep with `pyproject.toml` and `alpi/__init__.py`.

## 2. One-shot local deploy

For day-to-day sideloading onto a real Umbrel, use the one-shot script:

```bash
deploy/umbrel/deploy-to-umbrel.sh
```

The script:

1. Verifies that `pyproject.toml` and `deploy/umbrel/alpi/umbrel-app.yml`
   agree on the version.
2. Builds and pushes `satoshiltd/alpi-umbrel:<version>`.
3. Resolves the Docker Hub manifest digest.
4. Generates the local Umbrel package with public icon and gallery URLs.
5. Pins `deploy/umbrel/alpi/docker-compose.yml` to
   `satoshiltd/alpi-umbrel:<version>@sha256:<digest>`.
6. Detects the Umbrel app-store path on the remote box.
7. Copies the package to Umbrel with `rsync`.
8. For an existing install, syncs the new compose/manifest from the
   app-store copy into Umbrel's `app-data/<app>/` directory, excluding
   the persistent `data/` subtree.
9. Tries `install`, or `restart` for an existing install.
10. Stops with a diagnostic error instead of auto-uninstalling the app,
    so a broken Umbrel state cannot silently wipe `/data/.alpi`.
11. Prints the final container state.

Expected interaction:

- Docker Hub login must already exist on the Mac running the script.
- SSH access to `umbrel@umbrel.local` must already work.
- The script may prompt for the Umbrel SSH password and `sudo` password.

Useful overrides:

```bash
VERSION=0.6.5 deploy/umbrel/deploy-to-umbrel.sh
SKIP_BUILD=1 deploy/umbrel/deploy-to-umbrel.sh
PLATFORMS=linux/amd64,linux/arm64 deploy/umbrel/deploy-to-umbrel.sh
UMBREL_HOST=umbrel.local deploy/umbrel/deploy-to-umbrel.sh
UMBREL_STORE_DIR=/home/umbrel/umbrel/app-stores/<store>/alpi deploy/umbrel/deploy-to-umbrel.sh
```

## 3. Migrate an existing local `~/.alpi` to Umbrel

If you already have real profiles on another machine, do not copy
directories by hand. Use the encrypted machine backup flow:

```bash
deploy/umbrel/migrate-home-to-umbrel.sh
```

The migration script:

1. Reads your local Alpi home from `~/.alpi` by default.
2. Prompts once for a migration passphrase.
3. Creates an encrypted whole-home backup with `alpi backup`.
4. Copies that archive to the Umbrel host.
5. Restores it inside the running `alpi_server_1` container with
   `alpi restore --force`.
6. Restarts the Umbrel app.
7. Keeps the encrypted local archive in `/tmp` so you still have a
   portable rollback artifact.

Useful overrides:

```bash
SOURCE_HOME=/Users/javi/.alpi deploy/umbrel/migrate-home-to-umbrel.sh
LOCAL_ARCHIVE=/tmp/alpi-macbook-to-umbrel.alpi-backup deploy/umbrel/migrate-home-to-umbrel.sh
UMBREL_HOST=umbrel.local deploy/umbrel/migrate-home-to-umbrel.sh
```

Notes:

- Run this only after Alpi is already installed on Umbrel.
- The restore is a full replace of Umbrel's `/data/.alpi`, not a merge.
- This is the right path for migrating `default` plus named profiles such
  as `etxea`, `doc`, and `abby`.

## 4. Build and publish the Docker image

From the Alpi repository root:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t satoshiltd/alpi-umbrel:0.4.47 \
  -f deploy/umbrel/alpi/Dockerfile \
  --push .
```

If you only need a local smoke test first:

```bash
docker build -t satoshiltd/alpi-umbrel:0.4.47 -f deploy/umbrel/alpi/Dockerfile .
docker run --rm -it -p 8080:8080 -v alpi-umbrel-data:/data satoshiltd/alpi-umbrel:0.4.47
```

## 5. Resolve the image digest

Umbrel requires the app-store compose file to pin the image by digest.

After publishing:

```bash
docker buildx imagetools inspect satoshiltd/alpi-umbrel:0.4.47
```

Copy the manifest list digest and use:

```yaml
image: satoshiltd/alpi-umbrel:0.4.47@sha256:<digest>
```

## 6. Update the `umbrel-apps` fork

In the fork of `getumbrel/umbrel-apps`, only copy:

- `deploy/umbrel/alpi/docker-compose.yml`
- `deploy/umbrel/alpi/exports.sh`
- `deploy/umbrel/alpi/umbrel-app.yml`

Do not copy:

- `Dockerfile`
- `README.md`
- tests
- repo docs
- screenshots

Before opening or updating the PR in `umbrel-apps`:

1. Replace the image in `alpi/docker-compose.yml` with the digest-pinned
   form.
2. Set `submission:` in `alpi/umbrel-app.yml` to the exact PR URL.
3. Leave `icon: ""` and `gallery: []` for a new app submission.

## 6. Install on a real Umbrel

Use this path when testing Alpi on a real Umbrel before the official
Umbrel App Store submission is merged.

The official package keeps `icon: ""` and `gallery: []` because Umbrel's
new-app linter requires those fields to be empty in the store PR. For a
local side-load, generate a temporary package with public icon and
gallery URLs first:

1. Build and push the Docker image:

   ```bash
   docker buildx build \
     --platform linux/amd64 \
     -t satoshiltd/alpi-umbrel:0.4.47 \
     -f deploy/umbrel/alpi/Dockerfile \
     --push .
   ```

   Use `--platform linux/amd64,linux/arm64` when preparing a public
   release. For a local Intel Umbrel smoke test, `linux/amd64` is enough.

2. Resolve the pushed digest:

   ```bash
   docker buildx imagetools inspect satoshiltd/alpi-umbrel:0.4.47
   ```

   Copy the top-level `Digest:` value.

3. Generate the local package with icon and gallery URLs:

   ```bash
   deploy/umbrel/prepare-local-package.sh
   ```

   The command prints the generated package directory. By default it is:

   ```text
   /tmp/alpi-umbrel-local/alpi
   ```

4. Pin the generated local package to the pushed digest:

   ```bash
   python3 - <<'PY'
   from pathlib import Path

   version = "0.4.47"
   digest = "sha256:<digest>"
   compose = Path("/tmp/alpi-umbrel-local/alpi/docker-compose.yml")
   text = compose.read_text()
   text = text.replace(
       f"image: satoshiltd/alpi-umbrel:{version}",
       f"image: satoshiltd/alpi-umbrel:{version}@{digest}",
   )
   compose.write_text(text)
   PY
   ```

5. Copy the generated local package into the local Umbrel app store:

   ```bash
   rsync -av \
     /tmp/alpi-umbrel-local/alpi/ \
     umbrel@umbrel.local:/home/umbrel/umbrel/app-stores/getumbrel-umbrel-apps-github-53f74447/alpi/
   ```

6. Install the app from Umbrel:

   ```bash
   ssh umbrel@umbrel.local
   umbreld client apps.install.mutate --appId alpi
   ```

   If your Umbrel does not expose `umbreld`, use `umbrel` instead:

   ```bash
   umbrel client apps.install.mutate --appId alpi
   ```

7. Open the app in the Umbrel dashboard.
8. Confirm the app icon appears.
9. Confirm the TUI appears in the browser terminal.
10. Exit the TUI and run:

   ```bash
   alpi setup
   alpi doctor
   ```

11. Restart the app and confirm the profile still exists.

Persistence survives because:

- Umbrel mounts `${APP_DATA_DIR}/data` into `/data`
- `HOME=/data`
- Alpi stores its root under `/data/.alpi`

## 7. Update an existing Umbrel install

When you are updating a box that already has Alpi installed, the
sequence is:

1. Build and push the new Docker image.
2. Resolve the new image digest.
3. Regenerate the local package with icon and gallery:

   ```bash
   deploy/umbrel/prepare-local-package.sh
   ```

4. Pin `/tmp/alpi-umbrel-local/alpi/docker-compose.yml` to the new
   digest.
5. Copy the generated package into the local Umbrel app store:

   ```bash
   rsync -av \
     /tmp/alpi-umbrel-local/alpi/ \
     umbrel@umbrel.local:/home/umbrel/umbrel/app-stores/getumbrel-umbrel-apps-github-53f74447/alpi/
   ```

6. Ask Umbrel to restart the app:

   ```bash
   ssh umbrel@umbrel.local
   umbreld client apps.restart.mutate --appId alpi
   ```

   If Umbrel does not pick up the new package on restart, reinstall
   instead:

   ```bash
   umbreld client apps.uninstall.mutate --appId alpi
   umbreld client apps.install.mutate --appId alpi
   ```

7. Verify the running container uses the new tag:

   ```bash
   sudo docker ps --format '{{.Names}} {{.Image}}' | grep alpi
   ```

8. Open the app and confirm:

   - the icon is visible
   - the browser TUI still works
   - the profile persisted under `/data/.alpi`

See `deploy/umbrel/PERSISTENCE.md` for the storage model.

## 8. Update an existing Umbrel PR

If the Umbrel linter complains:

- `invalid image name`:
  you forgot the digest suffix
- `manifest unknown`:
  the image tag was not pushed
- `submission field`:
  `submission:` must be the PR URL, not the Alpi repo URL
- `icon and gallery need to be empty`:
  keep them empty in `umbrel-app.yml` for new submissions
- `mounted file/directory ... doesn't exist`:
  keep `deploy/umbrel/alpi/data/.gitkeep` in the source package
- `unsafe user`:
  keep `user: "1000:1000"` in compose and run the image as non-root

## 9. Practical release checklist

1. Sync Umbrel package version to the current Alpi version.
2. Run:

   ```bash
   uv run pytest tests/core/test_umbrel_deploy.py -q
   ```

3. Build and push the multi-arch image.
4. Resolve the digest.
5. Update the `umbrel-apps` fork with the three package files.
6. Pin the image by digest there.
7. Set `submission:` to the PR URL there.
8. Re-test on a real Umbrel box.
