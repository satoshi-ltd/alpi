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

Optional: install Chromium for the browser tool. alpi does not
install it automatically because most users don't need it.

```bash
playwright install chromium
```

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
and runs `uv tool upgrade alpi` (or `pipx upgrade alpi`) on
confirmation. There is no auto-update at launch — alpi never reaches
the network unless you ask it to.

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
- `playwright install chromium` fails on Linux — install the
  system libraries Playwright needs first
  (`uv run playwright install-deps chromium`).
- `alpi doctor` red lights — run it; the output names the missing
  piece (model, workspace, gateway env, etc.) and tells you which
  wizard step fixes it.
