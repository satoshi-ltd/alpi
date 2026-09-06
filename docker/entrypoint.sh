#!/bin/sh
set -eu

export HOME="${HOME:-/data}"
export ALPI_PLATFORM="${ALPI_PLATFORM:-docker}"

mkdir -p "$HOME/.alpi"

# A previous container's pid has no meaning here; belt-and-braces with alpi's
# starttime check so `alpi daemon start` never refuses on a stale pidfile.
rm -f "$HOME/.alpi/service.pid"

# exec → alpi is PID 1; `daemon start` forks a reaping init (alpi/pid1.py) in front of the daemon.
exec alpi daemon start
