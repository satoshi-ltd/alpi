#!/usr/bin/env sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
src_dir="$repo_root/deploy/umbrel/alpi"
dest_dir="${1:-/tmp/alpi-umbrel-local/alpi}"
asset_base="${ASSET_BASE:-https://raw.githubusercontent.com/satoshi-ltd/alpi/main/assets/umbrel}"

case "$dest_dir" in
  ""|"/"|"/tmp"|"${HOME:-}"|"$repo_root"|"$repo_root/"*)
    echo "refuse to rm -rf unsafe dest_dir: ${dest_dir}" >&2
    exit 2
    ;;
esac

rm -rf "$dest_dir"
mkdir -p "$dest_dir"
cp -R "$src_dir/." "$dest_dir/"

awk -v asset_base="$asset_base" '
  $0 == "gallery: []" {
    print "gallery:"
    print "  - " asset_base "/alpi-screenshot-01.png"
    print "  - " asset_base "/alpi-screenshot-02.png"
    print "  - " asset_base "/alpi-screenshot-03.png"
    print "  - " asset_base "/alpi-screenshot-04.png"
    next
  }
  $0 == "icon: \"\"" {
    print "icon: " asset_base "/alpi-icon.svg"
    next
  }
  { print }
' "$src_dir/umbrel-app.yml" > "$dest_dir/umbrel-app.yml"

if grep -qE '^(gallery: \[\]|icon: "")$' "$dest_dir/umbrel-app.yml"; then
  echo "rewrite missed gallery/icon — source manifest format changed" >&2
  exit 3
fi

printf '%s\n' "$dest_dir"
