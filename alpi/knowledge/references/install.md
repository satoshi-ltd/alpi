# Install answer pack

## Answer directly

- Default install: `uv tool install alpi-agent`.
- First run: `alpi setup` (auto-installs + starts the daemon), then `alpi`.
- Update: `uv tool upgrade alpi-agent`, then restart the daemon if running.
- Uninstalling the binary does not delete `~/.alpi`.
- Platforms: Linux + macOS; Windows via WSL2 only.

## Recommended — `uv tool install`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # only if uv missing
uv tool install alpi-agent
alpi setup
alpi
```

Pin a version with `uv tool install alpi-agent==0.3.0`.

## Alternative — `pipx install`

```bash
pipx install alpi-agent
alpi setup
```

Recommend `uv tool` by default; offer `pipx` only when the user already uses pipx or can't use uv.

## Update

```bash
uv tool upgrade alpi-agent   # or: alpi update (checks PyPI, upgrades on confirm)
alpi update --check          # check only, no install
alpi daemon restart
alpi --version
```

Pin older: `uv tool install alpi-agent==0.2.99 --force`.

## Uninstall

```bash
uv tool uninstall alpi-agent   # or: pipx uninstall alpi
rm -rf ~/.alpi                 # only for a full wipe of profile data
```

Removes the binary, not `~/.alpi`.

## Development install

```bash
uv sync                            # from a checkout; venv from lock file
uv run alpi
uv tool install -e . --reinstall   # editable into tool env, matches end-user daemon
```

Tests: `pytest -q`, `pytest --integration -q`, `pytest --llm`.

## Troubleshooting

- `alpi: command not found`: uv/pipx bin dir not on `PATH`.
- Provider auth fails: rerun `alpi setup` or inspect the profile `.env`/config.
- Tools fail in a project: check the configured workspace.
- Daemon features unresponsive: `alpi doctor` and `alpi daemon status`.

## Not supported

No `curl | bash` installers, Homebrew, Docker, platform installers (.pkg/.msi), or global editable/source-copy installs. Use uv/pipx or the dev workflow.
