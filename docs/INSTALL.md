# Installing alpi

alpi runs on Linux and macOS. Windows users are expected to install
under [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) —
native Windows is not supported because alpi relies on POSIX
primitives (Unix-domain sockets, sandbox helpers, launchd / systemd
service backends). The path is the same as Linux once WSL2 is up.

> The PyPI package is `alpi-agent`. The binary, import, and home
> directory are `alpi`:
>
> ```bash
> uv tool install alpi-agent     # install
> alpi setup                     # use
> ```

## Recommended — `uv tool install`

[uv](https://docs.astral.sh/uv/) is alpi's recommended installer. It
puts alpi in its own isolated environment, makes upgrades a single
command, and never pollutes your system Python.

```bash
# Install uv if you don't have it already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install alpi
uv tool install alpi-agent

# Run the setup wizard, then start chatting
alpi setup
alpi
```

Pin a specific version with `uv tool install alpi-agent==0.3.0`.

The first `alpi setup` auto-installs the alpi daemon — one launchd
plist on macOS (`com.alpi.daemon`), one systemd-user unit on Linux
(`alpi-daemon.service`) — and starts it. The daemon supervises
every profile under `~/.alpi/`, so a single install gets you
24/7 cron + ALP listener for every profile you create.
Manage it later with `alpi daemon {status,restart,uninstall}` or
from `alpi setup → Services → Daemon`.

**Linux note.** `systemctl --user` services die when you log out
unless lingering is enabled. The install runs `loginctl
enable-linger $USER` automatically; on minimal containers / WSL
without `systemd=true`, `loginctl` may be missing — alpi logs a
warning and you'll need to keep the daemon foregrounded under
`tmux` / `screen`, or fix lingering by hand.

The first time the agent runs the `browser` tool, alpi downloads
Chromium (~200 MB, one-time, cached at `~/.cache/ms-playwright/`).
No separate install command. If you never use the browser tool,
nothing is downloaded.

## Alternative — `pipx install`

If you already use [pipx](https://pipx.pypa.io/) for your Python
tools, the same package works:

```bash
pipx install alpi-agent
alpi setup
```

## Updating

```bash
alpi update
```

`alpi update` checks PyPI for a newer version, shows what changed,
and runs `uv tool upgrade alpi-agent` (or `pipx upgrade
alpi-agent`) on confirmation. There is no auto-update at launch —
alpi never reaches the network unless you ask it to.

You don't have to remember to run it: alpi already checks PyPI in
the background once every eight hours and surfaces the result in
two places —

- `alpi doctor` prints a `Version` row at the top with the new
  number when one is available.
- The TUI's top bar adds a small `↑ vX.Y.Z` badge next to the
  current version.

`alpi update --check` does just the check and tells you whether
an upgrade exists, without installing anything.

To pin an older version intentionally:

```bash
uv tool install alpi-agent==0.2.99 --force
```

## Uninstalling

```bash
uv tool uninstall alpi   # or: pipx uninstall alpi
rm -rf ~/.alpi           # only if you want to drop profiles too
```

`~/.alpi` holds your profiles, keys, memory, and logs. The
uninstaller leaves it in place by default so you can reinstall and
pick up where you left off.

## Developing alpi

If you're contributing or hacking on alpi, install from source:

```bash
git clone https://github.com/satoshi-ltd/alpi
cd alpi
uv sync
uv run alpi
```

`uv sync` creates a venv from the lock file. Tests run with
`uv run pytest tests/`. Manual integration tests live under
`tests/manual/` and are not collected by `pytest` — read
`tests/manual/README.md` before running them.

## Why we don't ship other install paths

- **No `curl … | bash` installer.** Pasting a remote bash script
  into your shell is the opposite of what alpi stands for. Use the
  PyPI package — it's auditable, version-pinnable, signed by a
  trusted publisher, and updates flow through a tool you already
  trust.
- **No Homebrew formula.** `uv tool install` already covers macOS
  cleanly. Maintaining a Tap is duplicate work without a payoff.
- **No Docker image.** alpi is a personal CLI agent — it lives next
  to your shell, your editor, your dotfiles. Containerising it
  fights its own design.
- **No platform installers (.pkg, .msi).** Same reasoning: install
  via the language toolchain you already have.

## Troubleshooting

- `alpi: command not found` after install — the tool's bin
  directory isn't on your `PATH`. uv suggests the right line during
  install; re-run the suggested `eval "$(uv tool ...)"` command, or
  add `~/.local/bin` to your shell's `PATH`.
- The browser tool's first run fails on Linux with a missing
  shared library (`libgbm`, `libnss3`, etc.) — install the
  system libraries Playwright needs:
  `uvx --from playwright playwright install-deps chromium`.
- `alpi doctor` red lights — run it; the output names the missing
  piece (model, workspace, email credentials, etc.) and tells you which
  wizard step fixes it.
