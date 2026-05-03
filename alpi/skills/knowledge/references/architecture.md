# Architecture answer pack

Use this for internals, code layout, engine loop, tools, daemon,
gateway, scheduler, MCP, logging, and where to edit.

## Mental model

alpi is a local agent runtime:

1. Load profile config, memory, skills index, and system prompt.
2. Run an LLM turn with tool schemas.
3. Execute approved tools.
4. Persist session/log/budget state.
5. Optionally run as a service for gateways and schedules.

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
| `alpi/gateway/` | Telegram/email inbound gateways. |
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

- `alpi service start` runs the profile service.
- Gateways receive inbound messages and hand them to the engine.
- Scheduler jobs also run through the agent loop.
- Run one service per profile.

## Host/API boundary

Desktop/mobile clients talk to the daemon through `host.*` verbs served
from `alpi/host/` over `~/.alpi/host/host.sock`. They should not read
`~/.alpi/` directly and should not spawn `alpi` as a subprocess.

ALP (`alpi/alp/`) is separate: it is for peer-to-peer alpi links, not
the local desktop host API.

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
