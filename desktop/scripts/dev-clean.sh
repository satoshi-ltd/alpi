#!/usr/bin/env bash
# Full clean relaunch of the desktop app.
# Use after touching Tauri config or when `pnpm tauri dev` misses changes.
#
# What it does:
#   1. Kills the desktop binary, Vite dev server, and frees port 1420.
#   2. Drops Vite's transform cache.
#   3. Cleans only this crate's Cargo build so rebuilds stay fast.
#   4. Re-runs `pnpm tauri dev` from the desktop/ root.
#
# Usage:  desktop/scripts/dev-clean.sh

set -euo pipefail

cd "$(dirname "$0")/.."

echo "→ killing alpi-desktop, vite, and port 1420 listeners…"
lsof -ti:1420 2>/dev/null | xargs -r kill -9 2>/dev/null || true
pkill -9 -f "alpi-desktop|vite" 2>/dev/null || true
sleep 1

echo "→ clearing Vite cache…"
rm -rf node_modules/.vite || true

echo "→ ensuring cargo is on PATH…"
if ! command -v cargo >/dev/null 2>&1; then
  if [ -d "$HOME/.cargo/bin" ]; then
    export PATH="$HOME/.cargo/bin:$PATH"
  else
    echo "cargo not found and ~/.cargo/bin missing — install rustup first" >&2
    exit 1
  fi
fi

echo "→ cleaning alpi-desktop crate build (deps stay cached)…"
(cd src-tauri && cargo clean -p alpi-desktop)

echo "→ launching pnpm tauri dev…"
exec pnpm tauri dev
