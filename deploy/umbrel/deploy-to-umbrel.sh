#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"

PYPROJECT_VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n 1)"
MANIFEST_VERSION="$(awk -F'"' '/^version:/ {print $2}' deploy/umbrel/alpi/umbrel-app.yml)"
VERSION="${VERSION:-$PYPROJECT_VERSION}"
IMAGE_REPO="${IMAGE_REPO:-satoshiltd/alpi-umbrel}"
IMAGE="$IMAGE_REPO:$VERSION"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
DOCKER_CONTEXT="${DOCKER_CONTEXT:-}"
UMBREL_HOST="${UMBREL_HOST:-umbrel.local}"
UMBREL_USER="${UMBREL_USER:-umbrel}"
UMBREL_APP_ID="${UMBREL_APP_ID:-alpi}"
UMBREL_STORE_DIR="${UMBREL_STORE_DIR:-}"
LOCAL_PACKAGE="${LOCAL_PACKAGE:-/tmp/alpi-umbrel-local/alpi}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SSH_CONTROL_PATH="${SSH_CONTROL_PATH:-/tmp/alpi-umbrel-%r@%h:%p}"

DOCKER=(docker)
if [ -n "$DOCKER_CONTEXT" ]; then
  DOCKER+=(--context "$DOCKER_CONTEXT")
fi
SSH_OPTS=(
  -o ControlMaster=auto
  -o ControlPersist=5m
  -o ControlPath="$SSH_CONTROL_PATH"
)
RSYNC_RSH=(ssh "${SSH_OPTS[@]}")

cleanup_ssh_master() {
  ssh "${SSH_OPTS[@]}" -O exit "$UMBREL_USER@$UMBREL_HOST" >/dev/null 2>&1 || true
}
trap cleanup_ssh_master EXIT

if [ -z "$PYPROJECT_VERSION" ] || [ -z "$MANIFEST_VERSION" ]; then
  echo "could not resolve version from pyproject.toml or umbrel-app.yml" >&2
  exit 1
fi

if [ "$VERSION" != "$PYPROJECT_VERSION" ] || [ "$VERSION" != "$MANIFEST_VERSION" ]; then
  echo "version mismatch: pyproject=$PYPROJECT_VERSION umbrel-app=$MANIFEST_VERSION requested=$VERSION" >&2
  exit 1
fi

if ! "${DOCKER[@]}" info >/dev/null 2>&1; then
  current_context="$(docker context show 2>/dev/null || echo unknown)"
  echo "docker daemon is not reachable for context: ${DOCKER_CONTEXT:-$current_context}" >&2
  echo "start OrbStack / Docker Desktop, or rerun with DOCKER_CONTEXT=desktop-linux" >&2
  exit 1
fi

if [ "$SKIP_BUILD" != "1" ]; then
  echo "Building and pushing $IMAGE for $PLATFORMS"
  "${DOCKER[@]}" buildx build \
    --platform "$PLATFORMS" \
    -t "$IMAGE" \
    -f "$ROOT/deploy/umbrel/alpi/Dockerfile" \
    --push \
    "$ROOT"
else
  echo "Skipping build, reusing $IMAGE from Docker Hub"
fi

echo "Resolving pushed image digest"
DIGEST="$("${DOCKER[@]}" buildx imagetools inspect "$IMAGE" | awk '/^Digest:/ { print $2; exit }')"
if [ -z "$DIGEST" ]; then
  echo "could not resolve digest for $IMAGE" >&2
  exit 1
fi
PINNED_IMAGE="$IMAGE@$DIGEST"
echo "Pinned image: $PINNED_IMAGE"

echo "Preparing local Umbrel package at $LOCAL_PACKAGE"
"$ROOT/deploy/umbrel/prepare-local-package.sh" "$LOCAL_PACKAGE" >/dev/null

tmp_compose="$LOCAL_PACKAGE/docker-compose.yml.tmp"
awk -v image="$PINNED_IMAGE" '
  /^[[:space:]]+image: / {
    print "    image: " image
    next
  }
  { print }
' "$LOCAL_PACKAGE/docker-compose.yml" > "$tmp_compose"
mv "$tmp_compose" "$LOCAL_PACKAGE/docker-compose.yml"

if ! grep -qF 'syncthing/data:/data/workspace' "$LOCAL_PACKAGE/docker-compose.yml"; then
  echo "Injecting Syncthing workspace bind into local package compose"
  awk '
    /\$\{APP_DATA_DIR\}\/data:\/data/ {
      print
      print "      - ${APP_DATA_DIR}/../syncthing/data:/data/workspace"
      next
    }
    { print }
  ' "$LOCAL_PACKAGE/docker-compose.yml" > "$tmp_compose"
  mv "$tmp_compose" "$LOCAL_PACKAGE/docker-compose.yml"
fi

if [ -n "$UMBREL_STORE_DIR" ]; then
  remote_app_dir="$UMBREL_STORE_DIR"
else
  echo "Resolving Umbrel app-store path"
  remote_app_dir="$(
    ssh "${SSH_OPTS[@]}" "$UMBREL_USER@$UMBREL_HOST" "sh -s" -- "$UMBREL_APP_ID" <<'REMOTE'
set -eu
app_id="$1"
for root in \
  /home/umbrel/umbrel/app-stores \
  /home/umbrel/umbrel/app-store
do
  [ -d "$root" ] || continue
  candidate="$(
    find "$root" -maxdepth 6 -type d -name "$app_id" 2>/dev/null \
      | awk '
          /getumbrel|umbrel-apps/ { preferred[++p] = $0; next }
          { fallback[++f] = $0 }
          END {
            if (p) { print preferred[1]; exit }
            if (f) { print fallback[1]; exit }
          }
        '
  )"
  if [ -n "$candidate" ]; then
    printf '%s\n' "$candidate"
    exit 0
  fi
done
REMOTE
  )"
  if [ -z "$remote_app_dir" ]; then
    remote_app_dir="$(
      ssh "${SSH_OPTS[@]}" "$UMBREL_USER@$UMBREL_HOST" "sh -s" -- "$UMBREL_APP_ID" <<'REMOTE'
set -eu
app_id="$1"
for root in \
  /home/umbrel/umbrel/app-stores \
  /home/umbrel/umbrel/app-store
do
  [ -d "$root" ] || continue
  store="$(
    find "$root" -mindepth 1 -maxdepth 1 -type d 2>/dev/null \
      | awk '
          /getumbrel|umbrel-apps/ { preferred[++p] = $0; next }
          { fallback[++f] = $0 }
          END {
            if (p) { print preferred[1]; exit }
            if (f) { print fallback[1]; exit }
          }
        '
  )"
  if [ -n "$store" ]; then
    printf '%s/%s\n' "$store" "$app_id"
    exit 0
  fi
done
REMOTE
    )"
  fi
  if [ -z "$remote_app_dir" ]; then
    echo "could not resolve remote Umbrel app-store path for $UMBREL_APP_ID" >&2
    echo "" >&2
    echo "remote Umbrel app-store roots:" >&2
    ssh "${SSH_OPTS[@]}" "$UMBREL_USER@$UMBREL_HOST" \
      "for d in /home/umbrel/umbrel/app-stores /home/umbrel/umbrel/app-store; do [ -d \"\$d\" ] && echo \"\$d\" && ls -1 \"\$d\" | sed 's/^/  /'; done" >&2 || true
    echo "" >&2
    echo "any alpi dirs anywhere under /home/umbrel/umbrel:" >&2
    ssh "${SSH_OPTS[@]}" "$UMBREL_USER@$UMBREL_HOST" \
      "find /home/umbrel/umbrel -maxdepth 4 -type d -name '$UMBREL_APP_ID' 2>/dev/null | sed 's/^/  /'" >&2 || true
    echo "" >&2
    echo "If the app is not installed, install it from the Umbrel UI first." >&2
    echo "If the dir exists but the find missed it, override:" >&2
    echo "  UMBREL_STORE_DIR=<full path> $0" >&2
    exit 1
  fi
fi

echo "Copying package to $UMBREL_USER@$UMBREL_HOST:$remote_app_dir"
ssh "${SSH_OPTS[@]}" "$UMBREL_USER@$UMBREL_HOST" "mkdir -p '$remote_app_dir'"
rsync -av -e "${RSYNC_RSH[*]}" "$LOCAL_PACKAGE/" "$UMBREL_USER@$UMBREL_HOST:$remote_app_dir/"

echo "Applying package on Umbrel"
remote_script="/tmp/${UMBREL_APP_ID}-umbrel-deploy.sh"
ssh "${SSH_OPTS[@]}" "$UMBREL_USER@$UMBREL_HOST" "cat > '$remote_script'" <<'REMOTE'
#!/usr/bin/env bash
set -euo pipefail
app_id="$1"
app_dir="$2"
pinned_image="$3"
app_data_dir="/home/umbrel/umbrel/app-data/$app_id"
client="umbreld"
if ! command -v "$client" >/dev/null 2>&1; then
  client="umbrel"
fi

image_line="$(grep '^    image:' "$app_dir/docker-compose.yml" || true)"
echo "Remote package image: $image_line"
case "$image_line" in
  *PASTE_DIGEST_HERE*|*@sha256:*@sha256:*)
    echo "remote docker-compose.yml contains an invalid image reference" >&2
    exit 1
    ;;
esac
case "$image_line" in
  *"$pinned_image"*) ;;
  *)
    echo "remote package image does not match expected pinned image" >&2
    exit 1
    ;;
esac

echo "Validating sudo access"
sudo -v

trpc_bool() {
  local out
  out="$("$client" client "$1" --appId "$app_id" 2>&1 || true)"
  printf '%s\n' "$out"
  case "$out" in
    true) return 0 ;;
    false) return 1 ;;
    *) return 2 ;;
  esac
}

server_container() {
  sudo -n docker ps -a --format '{{.Names}}' \
    | grep -E "^${app_id}[-_]server[-_]1$" \
    | head -n 1
}

container_exists() {
  [ -n "$(server_container)" ]
}

sync_app_data() {
  if [ ! -d "$app_data_dir" ]; then
    echo "Umbrel app-data directory not found: $app_data_dir" >&2
    exit 1
  fi
  echo "Syncing app-store manifest into app-data"
  sudo -n rsync -a --exclude=data "$app_dir/" "$app_data_dir/"
  local data_image_line
  data_image_line="$(grep '^    image:' "$app_data_dir/docker-compose.yml" || true)"
  echo "App-data image: $data_image_line"
  case "$data_image_line" in
    *"$pinned_image"*) ;;
    *)
      echo "app-data docker-compose.yml does not match expected pinned image" >&2
      exit 1
      ;;
  esac
}

if container_exists; then
  sync_app_data
  echo "Trying app restart"
  if ! trpc_bool apps.restart.mutate; then
    echo "restart failed — investigate before forcing reinstall" >&2
    container="$(server_container || true)"
    if [ -n "$container" ]; then
      echo "  sudo docker logs $container --tail 80" >&2
    fi
    exit 1
  fi
else
  echo "Trying app install"
  if ! trpc_bool apps.install.mutate; then
    echo "install failed — investigate Umbrel app state before forcing reinstall" >&2
    echo "  $client client apps.install.mutate --appId $app_id" >&2
    exit 1
  fi
fi

echo "Container state:"
sudo -n docker ps --format '{{.Names}} {{.Image}} {{.Status}}' | grep "$app_id" || true
if ! container_exists; then
  echo "alpi container was not created on Umbrel" >&2
  exit 1
fi
REMOTE

ssh -tt "${SSH_OPTS[@]}" "$UMBREL_USER@$UMBREL_HOST" \
  "chmod +x '$remote_script' && '$remote_script' '$UMBREL_APP_ID' '$remote_app_dir' '$PINNED_IMAGE'; status=\$?; rm -f '$remote_script'; exit \$status"

echo "Done: $PINNED_IMAGE"
