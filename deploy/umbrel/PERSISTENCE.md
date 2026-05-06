# Umbrel persistence and release flow

This document explains how Alpi stores state on Umbrel, why that state
survives normal app updates, and which steps are required when shipping
a new Umbrel app version.

## Storage model

The Umbrel app mounts the app data directory into the container:

```yaml
volumes:
  - ${APP_DATA_DIR}/data:/data
```

and the container runs with:

```yaml
environment:
  HOME: /data
```

Alpi resolves its root from `HOME`, so `~/.alpi` becomes:

```text
/data/.alpi
```

That means the real persistent state lives on the Umbrel host at:

```text
${APP_DATA_DIR}/data/.alpi
```

Inside the container it is visible as:

```text
/data/.alpi
```

## What persists

Everything written under `~/.alpi` persists across container restarts
and normal app updates, including:

- profiles
- config
- sessions
- memory
- ALP keys
- workgroup state
- logs and other Alpi-managed state under `.alpi`

## Why updates do not wipe profiles

Umbrel updates replace the container image, not the app data
directory.

During an update:

1. Umbrel pulls a new Docker image.
2. Umbrel recreates the app container from that new image.
3. Umbrel mounts the same `${APP_DATA_DIR}/data` directory back into
   the new container.
4. Alpi starts again with `HOME=/data`.
5. Alpi sees the same `/data/.alpi` directory it was using before the
   update.

So the code changes, but the user state stays in place.

## What can still lose data

Normal app updates should not lose Alpi profiles. Data loss is still
possible in these cases:

- uninstalling the app if Umbrel removes the app data directory
- manually deleting `${APP_DATA_DIR}/data`
- changing the mount target or changing `HOME` away from `/data`
- shipping a broken migration in a future Alpi release

For that reason, the encrypted archive flow is still part of the
operational story:

```bash
alpi backup
alpi restore <archive>
```

## Why the repo includes `data/`

The Umbrel linter expects the source app directory to contain a `data/`
directory when the compose file mounts `${APP_DATA_DIR}/data`.

That is why `deploy/umbrel/alpi/data/.gitkeep` exists. It is not where
runtime state is stored in Git. It exists to make the mount contract
explicit and keep the app-store linter happy.

## Releasing a new Umbrel version

When shipping a new Umbrel app version:

1. Build and publish the Docker image:

   ```bash
   docker buildx build \
     --platform linux/amd64,linux/arm64 \
     -t satoshiltd/alpi-umbrel:<version> \
     -f deploy/umbrel/alpi/Dockerfile \
     --push .
   ```

2. Resolve the manifest digest:

   ```bash
   docker buildx imagetools inspect satoshiltd/alpi-umbrel:<version>
   ```

3. In the `umbrel-apps` PR, pin the image by digest:

   ```yaml
   image: satoshiltd/alpi-umbrel:<version>@sha256:<digest>
   ```

4. Bump `version:` in `umbrel-app.yml`.

5. Leave the volume mount as:

   ```yaml
   - ${APP_DATA_DIR}/data:/data
   ```

6. Keep `HOME=/data`.

If steps 5 or 6 change, Alpi will stop reading the old profile
directory and the app will appear to "lose" state even though the old
data still exists on disk.

## Practical rule

For Umbrel, treat `/data` as the stable user-state boundary:

- image contents are replaceable
- `/data` is not

As long as Alpi continues to store its root under `/data/.alpi`, normal
updates preserve the user's profiles.
