#!/bin/sh
set -eu

export HOME="${HOME:-/data}"
export ALPI_PLATFORM="${ALPI_PLATFORM:-umbrel}"
export ALPI_TTYD_PORT="${ALPI_TTYD_PORT:-8080}"

mkdir -p "$HOME/.alpi"

ttyd_pid=""
alpi daemon start &
daemon_pid="$!"

shutdown() {
  if [ -n "$ttyd_pid" ]; then
    kill "$ttyd_pid" 2>/dev/null || true
    wait "$ttyd_pid" 2>/dev/null || true
  fi
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
  sh -lc 'cd "$HOME"; alpi; exec sh' &
ttyd_pid="$!"

while true; do
  if ! kill -0 "$daemon_pid" 2>/dev/null; then
    kill "$ttyd_pid" 2>/dev/null || true
    wait "$ttyd_pid" 2>/dev/null || true
    exit 1
  fi
  if ! kill -0 "$ttyd_pid" 2>/dev/null; then
    shutdown
    exit 0
  fi
  sleep 2
done
