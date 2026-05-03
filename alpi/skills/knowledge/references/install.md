# Install answer pack

Use this for install, update, uninstall, dev install, and supported
install paths.

## Recommended install

```bash
uv tool install alpi-agent
alpi setup
alpi
```

If `uv` is missing:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Alternative install

```bash
pipx install alpi-agent
alpi setup
```

Use `uv tool install` as the default recommendation. Mention `pipx`
only when the user already uses pipx or cannot use uv.

## Update

```bash
uv tool upgrade alpi-agent
alpi --version
```

Check whether a newer release exists:

```bash
alpi update --check
```

## Uninstall

```bash
uv tool uninstall alpi-agent
```

This removes the installed binary, not the user's profile data under
`~/.alpi`. Tell the user to back up or remove `~/.alpi` separately if
they want a full wipe.

## Development install

From a checkout:

```bash
uv sync
uv run alpi
```

Run tests with:

```bash
pytest -q
pytest --integration -q
pytest --llm
```

## Troubleshooting

- `alpi: command not found`: ensure the uv/pipx bin directory is on
  `PATH`.
- Provider auth fails: rerun `alpi setup` or inspect the profile
  `.env`/config.
- Tools fail in a project: check the configured workspace.
- Service does not respond: run `alpi doctor` and `alpi service status`.

## Not supported as primary paths

Do not recommend random install scripts, global editable installs, or
copying source files into a profile. Use uv/pipx or the dev workflow.
