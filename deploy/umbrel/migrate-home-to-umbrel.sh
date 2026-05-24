#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT"

SOURCE_HOME="${SOURCE_HOME:-$HOME/.alpi}"
UMBREL_HOST="${UMBREL_HOST:-umbrel.local}"
UMBREL_USER="${UMBREL_USER:-umbrel}"
UMBREL_APP_ID="${UMBREL_APP_ID:-alpi}"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOCAL_ARCHIVE="${LOCAL_ARCHIVE:-/tmp/${UMBREL_APP_ID}-migration-${STAMP}.alpi-backup}"
REMOTE_ARCHIVE="/tmp/${UMBREL_APP_ID}-migration-${STAMP}.alpi-backup"
SSH_CONTROL_PATH="${SSH_CONTROL_PATH:-/tmp/alpi-umbrel-%r@%h:%p}"

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

if [ ! -d "$SOURCE_HOME" ]; then
  echo "source home not found: $SOURCE_HOME" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to run the repo's alpi backup command" >&2
  exit 1
fi

printf "Migration passphrase: " >&2
stty -echo
IFS= read -r PASSPHRASE
stty echo
printf '\n' >&2

if [ -z "$PASSPHRASE" ]; then
  echo "passphrase must not be empty" >&2
  exit 1
fi

echo "Creating encrypted backup from $SOURCE_HOME"
printf '%s\n' "$PASSPHRASE" | ALPI_HOME="$SOURCE_HOME" uv run alpi backup \
  --out "$LOCAL_ARCHIVE" \
  --passphrase-stdin

echo "Copying backup to Umbrel: $REMOTE_ARCHIVE"
rsync -av -e "${RSYNC_RSH[*]}" "$LOCAL_ARCHIVE" "$UMBREL_USER@$UMBREL_HOST:$REMOTE_ARCHIVE"

echo "Preparing remote restore"
remote_script="/tmp/${UMBREL_APP_ID}-umbrel-migrate.sh"
ssh "${SSH_OPTS[@]}" "$UMBREL_USER@$UMBREL_HOST" "cat > '$remote_script'" <<'REMOTE'
#!/usr/bin/env bash
set -euo pipefail
app_id="$1"
archive="$2"
container="${app_id}_server_1"
client="umbreld"
if ! command -v "$client" >/dev/null 2>&1; then
  client="umbrel"
fi

echo "Validating sudo access"
sudo -v

printf "Migration passphrase: " >&2
stty -echo
IFS= read -r passphrase
stty echo
printf '\n' >&2

if [ -z "$passphrase" ]; then
  echo "passphrase must not be empty" >&2
  exit 1
fi

if ! sudo -n docker ps -a --format '{{.Names}}' | grep -qx "$container"; then
  echo "Umbrel app container not found: $container" >&2
  echo "Install Alpi on Umbrel first with deploy/umbrel/deploy-to-umbrel.sh" >&2
  exit 1
fi

echo "Copying archive into container"
sudo -n docker cp "$archive" "$container:/tmp/alpi-migration.alpi-backup"

echo "Restoring /data/.alpi from archive"
printf '%s\n' "$passphrase" | sudo -n docker exec -i "$container" \
  alpi restore /tmp/alpi-migration.alpi-backup --passphrase-stdin --force

sudo -n docker exec "$container" rm -f /tmp/alpi-migration.alpi-backup || true
rm -f "$archive"

echo "Restarting Umbrel app"
if ! "$client" client apps.restart.mutate --appId "$app_id"; then
  sudo -n docker restart "$container" >/dev/null
fi

echo "Profiles now present on Umbrel:"
sudo -n docker exec "$container" sh -lc '
  echo default
  if [ -d /data/.alpi/profiles ]; then
    ls -1 /data/.alpi/profiles | sed "s/^/profiles\\//"
  fi
'
REMOTE

ssh -tt "${SSH_OPTS[@]}" "$UMBREL_USER@$UMBREL_HOST" \
  "chmod +x '$remote_script' && '$remote_script' '$UMBREL_APP_ID' '$REMOTE_ARCHIVE'; status=\$?; rm -f '$remote_script'; exit \$status"

echo "Migration complete"
echo "Local encrypted archive kept at: $LOCAL_ARCHIVE"
