#!/bin/sh
set -eu

export HOME="${HOME:-/data}"
export ALPI_PLATFORM="${ALPI_PLATFORM:-docker}"

mkdir -p "$HOME/.alpi"

# A previous container's pid has no meaning here; belt-and-braces with alpi's
# starttime check so `alpi daemon start` never refuses on a stale pidfile.
rm -f "$HOME/.alpi/service.pid"

# exec → the daemon becomes PID 1 and receives SIGTERM/SIGINT directly
# (serve_all installs handlers for graceful shutdown).
exec alpi daemon start
