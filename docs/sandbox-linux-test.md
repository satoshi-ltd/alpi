# Testing the Linux sandbox from macOS

alf's Phase-2 sandbox uses `bubblewrap` on Linux. If you don't have a
Linux machine handy, a minimal Docker image lets you exercise the
Linux code path from macOS.

## Dockerfile

```dockerfile
# docs/sandbox-linux-test.Dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    bubblewrap curl python3 python3-venv ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH=/root/.local/bin:$PATH

WORKDIR /alf
```

## Build + run

```bash
docker build -t alf-linux-sandbox -f docs/sandbox-linux-test.Dockerfile .
docker run --rm -it \
  --privileged \
  -v "$PWD":/alf \
  alf-linux-sandbox bash
```

The `--privileged` flag lets bubblewrap create user namespaces inside
the container. It's only for this test environment — real users install
bubblewrap on their host, no Docker needed.

## Inside the container

```bash
cd /alf
uv run --with pytest pytest -q tests/test_sandbox.py
uv run --with pytest pytest -q tests/test_guards.py
```

The Linux-specific tests (`test_linux_builds_bwrap_command`,
`test_linux_workspace_write_allowed_escape_blocked`, etc.) run now
instead of being skipped.

## Manual smoke test

```bash
uv run python - <<'PY'
from pathlib import Path
from alf.tools._sandbox import wrap_command
import subprocess

ws = Path("/tmp/ws"); ws.mkdir(exist_ok=True)
ah = Path("/tmp/ah"); ah.mkdir(exist_ok=True)

# allowed: write inside workspace
args = wrap_command("echo hi > /tmp/ws/ok.txt && cat /tmp/ws/ok.txt",
                    workspace=ws, alf_home=ah, allow_network=False)
print("allowed:", subprocess.run(args, capture_output=True, text=True).stdout)

# blocked: write to /etc
args = wrap_command("echo pwn > /etc/zzz",
                    workspace=ws, alf_home=ah, allow_network=False)
r = subprocess.run(args, capture_output=True, text=True)
print("blocked (/etc):", r.returncode, r.stderr[:80])

# blocked: network with --unshare-net
args = wrap_command("curl --max-time 3 https://example.com",
                    workspace=ws, alf_home=ah, allow_network=False)
r = subprocess.run(args, capture_output=True, text=True)
print("blocked (net):", r.returncode, r.stderr[:80])
PY
```

Expected: write to `/tmp/ws/` works, write to `/etc/` fails with
permission error, curl fails because the process has no network.
