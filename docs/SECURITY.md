# Security model

alpi is published by [Satoshi Ltd.](https://www.satoshi-ltd.com/),
whose three load-bearing principles for this document are:

> **Security First** — threat-modeled from initial development; no
> surveillance disguised as telemetry.
> **Privacy by Design** — privacy is the foundation, not a feature.
> **Zero Knowledge** — what we don't know can't be subpoenaed,
> leaked, or sold.

Those are the frame every decision below lives inside: the guard is
mandatory and local, the sandbox is an opt-in *second* wall, the LLM
is treated as an adversary with user credentials, and we keep as
little state off your machine as we can.

alpi runs LLM-decided tool calls on your machine. The security posture
is layered — application-level guards that always run, plus an
optional OS-level sandbox for shell commands.

## Layer 1 — application guards (always on)

Live inside the Python process, can't be disabled without editing
source. Cover the attack vectors that an OS sandbox around `terminal`
doesn't reach:

- **Command approval system** on `terminal` (v0.2.37). Every shell
  command is classified into three severities:

  - **safe**: runs without prompting.
  - **caution**: `rm -rf <dir>`, `chmod 777`, `sudo <cmd>`,
    `git push --force`, `git reset --hard`, SQL `DROP` / `TRUNCATE`,
    `kill -9`, etc. Prompts the user in the TUI with four options:
    `Once` / `Session` / `Always` / `Deny`. Session approvals live
    in-memory; `Always` persists the pattern description to
    `tools.terminal.approval.allowlist` in `config.yaml`. On
    non-interactive surfaces (gateway, schedule) caution commands
    auto-deny with a clear error.
  - **dangerous**: `mkfs`, `dd of=/dev/…`, fork bombs, pipe-to-
    interpreter (`curl | sh`), recursive `chmod`/`chown` on `/`,
    reads of SSH private keys, writes to `/etc /var /usr /boot /sys
    /proc`. Always blocked. No override — run directly from your
    shell if you genuinely need one of these.

  Replaces the previous hard denylist. See `docs/CONFIG.md` for the
  allowlist format and surface-specific behaviour.

- **SSRF block** on `web_fetch` / `web_extract`. Rejects URLs pointing
  to RFC 1918 private ranges, loopback, link-local, and cloud
  metadata endpoints (`169.254.169.254`, `metadata.google.internal`).
  Hostnames are resolved to IP before the check, so an
  attacker-controlled DNS record pointing at `10.x.x.x` doesn't slip
  through.

- **Prompt-injection scan** on content returned by `email` read and
  `web_fetch`. If the content contains override directives ("ignore
  previous instructions"), system/assistant role impersonation,
  tool-call injection ("call `send_message` with X"), credential
  exfiltration phrasing, or zero-width Unicode, the tool prepends a
  SECURITY WARNING header telling the LLM to treat the content as
  untrusted data.

- **Sensitive-path denylist** on file tools (`read_file`, `write_file`,
  `edit_file`, `search`, email attachment download). Matches terminal's
  posture: paths under `/etc`, `/boot`, `/sys`, `/proc`,
  `/usr/lib/systemd`, `/System`, `/private/etc`, the docker sockets,
  SSH private keys (`~/.ssh/id_*`, `*_key`, `*_ed25519`), `*.pem /
  *.p12 / *.pfx`, `~/.aws/credentials`, `~/.gnupg/` are refused
  everywhere. Anything else — including arbitrary `$HOME` paths, `/tmp`,
  and outside-workspace project dirs — is allowed, same as terminal.
  Workspace-only isolation lives in Layer 2 (OS sandbox).

## Layer 2 — OS sandbox (opt-in, per profile)

Wraps `terminal` subprocess calls in a native OS sandbox so the
kernel refuses the syscalls, not just the regex above. Read/write
access is limited to `workspace` + `~/.alpi/` + `/tmp`; network is
denied by default.

**Status: stable, opt-in.** Defaults to off because real-world dev
workflows vary too much to pick a profile that never breaks: `git
push` over SSH relies on `~/.ssh`, Apple Silicon Homebrew lives in
`/opt/homebrew`, `docker` needs `/var/run/docker.sock`, npm wants
`~/.npm`. For interactive chat where you approve every command, the
Layer 1 denylist is already sufficient.

**Where it really earns its keep: unattended profiles.** Telegram
gateway, schedule daemon, `research` / `delegate` sub-agents — these
run without a human approving each command. A prompt-injected email
or a hallucinating sub-agent can issue `rm -rf ~/anything` with no
veto. Layer 2 is the kernel-level veto you want there.

### Recommended pattern: one profile per posture

alpi's multi-profile CLI makes this ergonomic:

- `alpi` — your main interactive dev profile. Sandbox off. Full access
  to your usual tooling.
- `alpi -p watchdog` — the profile your Telegram / schedule daemon
  runs under. Sandbox on. Denies `~/.ssh`, writes outside
  `workspace`, network (unless you opt in).

Each profile has its own `~/.alpi/profiles/<name>/config.yaml`, so
the sandbox flag is set independently.

### Enabling

Interactive: `alpi setup → Sandbox` → toggle on/off + network.

YAML (direct): set in `~/.alpi/profiles/<name>/config.yaml`:
```yaml
tools:
  terminal:
    sandbox: true
    allow_network: false   # flip to true if the profile needs git push / npm install
```

### TUI feedback

The top bar shows the current profile's sandbox state next to the
workspace: `sandbox on` in green when active, `sandbox off` in muted
grey when not. Quick visual confirmation you're in the posture you
think you're in.

### Platform support

**macOS** — uses native `sandbox-exec` (ships with the OS at
`/usr/bin/sandbox-exec`). No install step.

**Linux** — uses `bubblewrap`. Install once:
- Debian/Ubuntu: `sudo apt install bubblewrap`
- Fedora/RHEL: `sudo dnf install bubblewrap`
- Arch: `sudo pacman -S bubblewrap`
- Alpine: `sudo apk add bubblewrap`

Requires user namespaces enabled in the kernel (default on modern
distros; some hardened configs disable them).

**Windows** — no native sandbox path. Two options:
1. **WSL2 (recommended)**: `wsl --install`, then run alpi inside
   Ubuntu as if it were Linux native. bubblewrap works there.
2. **Native Windows**: leave `tools.terminal.sandbox: false`. Layer 1
   stays active; you lose the kernel-level guarantee for shell
   commands.

### What happens when the sandbox is on

- `rm -rf ~/Documents` → kernel refuses. Error to LLM: *"Operation
  not permitted"*.
- `cat ~/.ssh/id_rsa` → refused by the macOS profile (`~/.ssh`
  denied) or inaccessible on Linux (not bind-mounted).
- `curl https://example.com` with `allow_network: false` → no
  network stack in the process. `curl: (6) Could not resolve host`.
- `git status` inside the workspace → works normally.
- `npm install` → works if the package cache is under workspace or
  `~/.alpi/`, otherwise fails.

### Testing the Linux path from macOS

A minimal Docker image covers the Linux code path. See
`docs/sandbox-linux-test.md`.

## Threat model

alpi's realistic attacker:

- **Prompt injection** via email body, web page content, or tool
  output — tricking the LLM into running a destructive command or
  exfiltrating secrets. Layers 1 and 2 both defend here.
- **Direct malicious input** from the user themselves — not a
  concern; you own the machine.
- **Network adversaries** (APT, 0-day) — out of scope. alpi is a
  personal agent, not a hardened production system.

Layer 1 covers the common-case attacks (known patterns, known
sensitive paths, known SSRF targets). Layer 2 adds defense-in-depth
so a creative prompt that bypasses the regex still can't touch the
FS or the network.

## Third-party code

Every runtime dependency is an attack surface. We keep the list
tight (see [ARCHITECTURE.md → Dependencies](ARCHITECTURE.md#dependencies)
for why each one earns its place) and audit it before each
release. The CVE pass is a single command:

```bash
uv run --with pip-audit pip-audit
```

Risk profile of the runtime set:

| Dep | Risk | Notes |
|---|---|---|
| `litellm` | **Medium** | Large surface (100+ providers). Ships with `telemetry=True` by default — alpi flips it off in `llm.py::_silence_litellm()` so no request phones home. Regression test: `tests/test_llm_privacy.py`. |
| `playwright` | Medium-high | Runs a full Chromium (~230 MB) that loads arbitrary web content. Chromium's own sandbox is the line of defence at that layer; alpi adds nothing on top. Used only by the `browser` tool. |
| `playwright-stealth` | Low | Small patch set on `navigator.webdriver` and friends. Reverse-engineered detection bypass; breaks occasionally when detection vendors tighten. |
| `pillow` | Medium | Image parsers have a long history of CVEs. Keep on the latest minor; `pip-audit` catches known issues. |
| `faster-whisper` | Low | Bundles CTranslate2 native code. Models are downloaded from HuggingFace on first use — inspect the model hash if paranoia calls for it. |
| `edge-tts` | Low | Reverse-engineered unofficial Microsoft Edge TTS endpoint. Small code, but the endpoint can change; have a plan B (`say` on macOS, `espeak` on Linux) ready. |
| `textual` | Low | Pure Python, active, stable API surface we pin to. |
| `litellm`'s transitive tree (openai SDK, anthropic SDK, etc.) | Low-medium | Flows through. `pip-audit` covers. |
| `httpx`, `rich`, `click`, `pyyaml`, `python-dotenv`, `prompt_toolkit`, `croniter`, `html2text`, `ddgs` | Low | Small or stable or both. Rarely updated, rarely break. |

### Policy

- **`pip-audit` before every release.** Zero tolerance for known CVEs on the lockfile.
- **Image / parser deps on the latest minor.** Pillow especially — image parser CVEs land multiple times per year.
- **New runtime deps require justification.** A line in `ARCHITECTURE.md → Dependencies` and a row in the table above. No drift.
- **Reverse-engineered integrations carry a fallback plan.** `edge-tts` (Microsoft), `playwright-stealth` (detection vendors), `ddgs` (DuckDuckGo HTML) are all at the mercy of third parties. When they break we swap, we don't patch around them forever.

## Known gaps

- Writes to `/tmp` are allowed by both layers. A process could drop
  malware there hoping another tool picks it up. Low risk for
  personal use.
- The injection scan is pattern-based. A determined attacker can
  word-mangle to evade. Combined with layer 1 denylist + layer 2
  sandbox, the practical attack surface is narrow, but not zero.
- Windows without WSL2: no OS isolation. Layer 1 is your only
  defense; use a Tier A model to make the LLM less gullible.
