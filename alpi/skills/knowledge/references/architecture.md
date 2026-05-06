# Architecture answer pack

Use this for internals, code layout, engine loop, tools, daemon,
gateway, scheduler, MCP, logging, and where to edit.

## Mental model

alpi is a local agent runtime:

1. Load profile config, memory, skills index, and system prompt.
2. Run an LLM turn with tool schemas.
3. Execute approved tools.
4. Persist session/log/budget state.
5. Optionally run under the daemon for gateways, schedules, workgroups,
   and host verbs.

## Important directories

| Path | Purpose |
|---|---|
| `alpi/engine.py` | Main turn loop. |
| `alpi/llm.py` | LiteLLM transport. |
| `alpi/config.py` | Config loading and model resolution. |
| `alpi/tools/` | Tool registry and tool implementations. |
| `alpi/tools/skill.py` | User/bundled skill management. |
| `alpi/skills/` | Bundled skills packaged with alpi. |
| `alpi/memory.py` | Memory file management. |
| `alpi/tui/` | Terminal UI. |
| `alpi/gateway/` | Telegram/IMAP/Gmail/Matrix inbound gateways. |
| `alpi/scheduler/` | Scheduled jobs. |
| `alpi/service.py` | Background daemon/service management. |
| `alpi/alp/` | Alpi Link Protocol. |
| `alpi/mcp/` | MCP client support. |
| `desktop/` | Tauri desktop app, if present. |

## Engine loop

`Engine.run_turn()` binds the active home/profile, serializes turns,
checks budget, injects transient context, appends user input, streams
LLM output, executes tool calls, records usage, and saves the session.

Skills are exposed through a compact index in the system prompt.
Keyword hints can add a one-turn system message nudging toward matching
skills.

## Tools

Tools live under `alpi/tools/` and register through
`alpi/tools/__init__.py`. Each tool exposes:

- `name`,
- `description`,
- JSON schema `parameters`,
- `run(...) -> ToolResult`.

Use existing tool patterns before adding abstractions.

## Skills

User skills live in profile home. Bundled skills live in
`alpi/skills/` package resources and are addressed as `@alpi/<name>`.
The desktop/mobile client should talk to daemon host verbs, not read
profile files directly.

## Daemon and gateways

- `alpi daemon ...` manages the per-machine daemon.
- Gateways receive inbound messages and hand them to the engine.
- Scheduler jobs also run through the agent loop.
- One daemon supervises every profile on the machine.

## Host/API boundary

Desktop/mobile clients use `host.*` verbs in `alpi/host/`. Two
transports: Unix socket (`~/.alpi/host/host.sock`, local, no token)
and WebSocket on Tailscale or RFC1918 LAN (per-device token in
`params.auth_token`). Desktop should support multiple host-plane
connections: local socket plus paired remote daemons. Bind never goes
to `0.0.0.0`/public on normal hosts. `Devices -> Network` controls the
advertised companion endpoint; it can differ from the bind address
(notably on Umbrel, where the daemon binds inside Docker but the QR
advertises the host's external name or Tailscale IP). Tokens at
`~/.alpi/host/devices.yaml`, generated from `alpi setup → Devices`.
The host surface includes chat, sessions, workgroups, pairing-token
management, probes, schedule verbs, and daemon restart.

Clients must not read `~/.alpi/` directly or spawn `alpi` as a
subprocess. ALP (`alpi/alp/`) is separate (peer-to-peer). `Peer TCP
listener` configures ALP's optional TCP listener; it is not the same
as the host-plane companion endpoint.

## Security boundary

File tools and terminal commands are guarded by application-level
checks. Optional OS sandboxing can restrict filesystem/network access
for stronger isolation. See `security.md`.

## Tests

Common commands:

```bash
pytest -q
pytest --integration -q
pytest --llm
```

Fast tests cover unit/filesystem behavior. Integration tests cover
sockets and sandbox paths. LLM tests make real provider calls.
