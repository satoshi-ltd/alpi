# Umbrel operations

This document is the step-by-step manual for rebuilding, publishing,
testing, and updating the Alpi Umbrel package.

Umbrel package versions should match Alpi versions exactly.

Examples:

- Alpi `0.4.8` -> Umbrel image tag `0.4.8`
- Alpi `0.4.8` -> `umbrel-app.yml` version `0.4.8`

## 1. Bump the Umbrel package version

When Alpi ships a new version, update these files:

- `deploy/umbrel/alpi/docker-compose.yml`
- `deploy/umbrel/alpi/umbrel-app.yml`
- `deploy/umbrel/alpi/README.md`
- `.github/workflows/umbrel-image.yml`
- `deploy/umbrel/SUBMISSION.md`
- tests that assert the image tag and manifest version

The Docker image tag and the Umbrel manifest version should stay in
lockstep with `pyproject.toml` and `alpi/__init__.py`.

## 2. Build and publish the Docker image

From the Alpi repository root:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t satoshiltd/alpi-umbrel:0.4.8 \
  -f deploy/umbrel/alpi/Dockerfile \
  --push .
```

If you only need a local smoke test first:

```bash
docker build -t satoshiltd/alpi-umbrel:0.4.8 -f deploy/umbrel/alpi/Dockerfile .
docker run --rm -it -p 8080:8080 -v alpi-umbrel-data:/data satoshiltd/alpi-umbrel:0.4.8
```

## 3. Resolve the image digest

Umbrel requires the app-store compose file to pin the image by digest.

After publishing:

```bash
docker buildx imagetools inspect satoshiltd/alpi-umbrel:0.4.8
```

Copy the manifest list digest and use:

```yaml
image: satoshiltd/alpi-umbrel:0.4.8@sha256:<digest>
```

## 4. Update the `umbrel-apps` fork

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

## 5. Test on Umbrel

On the target Umbrel machine:

1. Install or update the app from the forked `umbrel-apps` source.
2. Open the app in the Umbrel dashboard.
3. Confirm the TUI appears in the browser terminal.
4. Exit the TUI and run:

   ```bash
   alpi setup
   alpi doctor
   ```

5. Restart the app and confirm the profile still exists.

Persistence should survive because:

- Umbrel mounts `${APP_DATA_DIR}/data` into `/data`
- `HOME=/data`
- Alpi stores its root under `/data/.alpi`

See `deploy/umbrel/PERSISTENCE.md` for the storage model.

## 6. Update an existing Umbrel PR

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

## 7. Practical release checklist

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
