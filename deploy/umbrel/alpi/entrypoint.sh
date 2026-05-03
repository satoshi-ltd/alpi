#!/bin/sh
set -eu

export HOME="${HOME:-/data}"
export ALPI_PLATFORM="${ALPI_PLATFORM:-umbrel}"
export ALPI_TTYD_PORT="${ALPI_TTYD_PORT:-8080}"

mkdir -p "$HOME/.alpi"

alpi daemon start &
daemon_pid="$!"

shutdown() {
  kill "$daemon_pid" 2>/dev/null || true
  wait "$daemon_pid" 2>/dev/null || true
}

trap shutdown INT TERM

ttyd \
  --interface 0.0.0.0 \
  --port "$ALPI_TTYD_PORT" \
  --writable \
  --client-option titleFixed=Alpi \
  --client-option fontSize=14 \
  sh -lc 'cd "$HOME"; alpi; exec sh'

shutdown
