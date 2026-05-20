# Configuration answer pack

Use this for `config.yaml`, `.env`, model/provider settings, tools,
gateway, budget, service, and "when does a setting take effect?"

## Locations

- Default profile config: `~/.alpi/config.yaml`
- Named profile config: `~/.alpi/profiles/<name>/config.yaml`
- Static secrets: matching `.env` file in the same profile home.

## Core fields

| Field | Meaning |
|---|---|
| `model` | Primary LiteLLM model string. Empty on fresh setup. |
| `fallback_models` | Stored list of fallback model strings. Do not promise automatic runtime escalation unless the installed version implements it. |
| `workspace` | Default project root for relative file/terminal work. |
| `budget` | Daily/monthly spend limits for paid providers. |
| `providers` | Provider-specific saved choices/endpoints. |
| `tools` | Tool-specific settings such as sandbox, vision model, TTS/STT. |
| `gateway` | Telegram/Matrix/IMAP/Gmail inbound settings. Chat platforms expose `show_tool_trace`; email exposes `poll_interval` + `mark_as_read`. Typing indicators hardcoded per platform (chat on, email off). |
| `schedule` | Scheduler/service settings. |
| `service` | Local daemon toggles and host options. |
| `alp` | ALP peer/workgroup configuration. |
| `host` | Host-plane companion endpoint (`host.tcp_port`, `host.tcp_host`, `host.device_name`). Empty `host.tcp_host` = auto-detect Tailscale then LAN; explicit value advertises a stable host to paired desktop/mobile clients. `host.device_name` sets the pairing label shown in `Devices`. |

## Model examples

OpenRouter:

```yaml
model: openrouter/xiaomi/mimo-v2-pro
```

Anthropic:

```yaml
model: anthropic/claude-sonnet-4.6
```

Ollama endpoint configured under providers:

```yaml
model: local/qwen3.6
providers:
  ollama:
    - name: local
      url: http://localhost:11434
```

## How to change settings

Recommended:

```bash
alpi setup
```

Also valid:

- `/model` inside the TUI for model switching.
- Edit `config.yaml` directly for advanced fields.

## Takes effect when

| Setting | Takes effect |
|---|---|
| `model` | Next turn/session depending on caller. |
| `workspace` | Next tool call after reload. |
| `budget` | Next turn; engine rereads budget. |
| `tools.terminal.sandbox` | Next terminal call. |
| Gateway config | Service restart usually required. |
| Scheduler config/jobs | Scheduler/service reload or restart depending on path. |
| `host.tcp_host`, `host.device_name` | Daemon restart. Desktop `Settings -> Devices -> pairing` can save the values and request the restart via `host.network.*`. |

## Memory

| Key | Default | Effect |
|---|---|---|
| `memory.review_interval` | `0` (off) | `N > 0` → daemon-thread reviewer fires every N user turns; append-only via `memory(action="add")` |

Internal constants (`alpi/memory.py`, `alpi/compaction.py`), not user knobs:

- `USER_CHAR_LIMIT = 3000`, `MEMORY_CHAR_LIMIT = 5000`
- `LOW_CONFIDENCE_MAX_AGE_DAYS = 30`
- Jaccard `0.7` near-duplicate threshold
- compaction policy: `trigger_ratio=0.75`, `target_ratio=0.40`, `keep_head=2`, `keep_tail=8`

Calibration gated on v0.6 evidence (`CM.1` + `logs/compaction.jsonl`).

## `.env`

Use `<home>/.env` for provider keys and static secrets. Skills
declare needed variables with `requires_env`; values stay in `.env`
and are only passed to subprocesses after the skill is opened.

Do not store secret values inside `SKILL.md`, docs, or scripts.

**Per-profile, daemon-isolated** (v0.4.52). The daemon supervises
many profiles in one process and never mutates `os.environ`. Every
profile-scoped lookup goes through
`alpi.home.effective_profile_env(home, *, base=None, extra=None)` =
`base` (default `os.environ`) ∪ `<home>/.env` ∪ `extra`. Migrated
sites: gateway adapters (`self.env` frozen at construction; Matrix
`_build_client`, IMAP `from_env_map`), `tools/{email, terminal,
skill, web_extract, read_image}`, `mail/{imap, gmail_auth}`, model
selector / TUI provider gating (`Provider.has_key(env=…)`),
`alpi.identity.draft_bio_from_agent`. LLM override paths
(`web_extract.model`, `read_image.model`) MUST go through
`config.resolve_model(replace(cfg, model=override))` so the
override picks up the profile's api_key; passing raw `model=…` to
`llm.complete` falls back to `os.environ` and breaks isolation.
`config.load()` no longer touches `os.environ`. `_deep_merge`
deep-copies defaults so a `cfg.providers.setdefault().append()` in
one profile cannot leak into `DEFAULT_CONFIG` (and from there into
every later load).

## Terminal approval allowlist

`tools.terminal.approval.allowlist` skips the interactive prompt for entries that match. Two shapes share the list:

- Pattern desc (e.g. `recursive rm`, `sudo`, `git force-push`) → bypass entire severity-category. Persisted by the TUI `Always` button.
- Anything else → command glob, `fnmatch` against trimmed command.

```yaml
tools:
  terminal:
    approval:
      allowlist:
        - recursive rm                       # category
        - sudo apt *                         # glob
        - git reset --hard origin/main       # glob
```

Invariants:

- DANGEROUS classifications (`mkfs`, `dd of=/dev/…`, pipe-to-interpreter, ssh-key reads, system-dir writes, fork bombs) are always blocked — allowlist has no effect.
- Globs do not apply to compound commands (`&&`, `||`, `;`, `|`, newline, backtick, `$( … )`). Falls back to prompt. Category-desc bypass still applies on compound.
- `classify()` returns the worst severity across the entire command, not the first match. `rm -rf build && mkfs.ext4 /dev/sda` → DANGEROUS even with `recursive rm` in allowlist.

## Common questions

- "Where do I set the workspace?" -> `workspace` in config or setup.
- "Why is alpi using the wrong model?" -> check active profile and
  `model` field.
- "Why does service ignore my config edit?" -> restart the profile's
  service.
- "Can work and personal use different models?" -> yes, use profiles.
- "What's the difference between `Devices -> Network` and `Peer TCP listener`?" -> `Devices` configures the host-plane companion endpoint (`host.*`); `Peer TCP listener` configures ALP peer traffic (`link.*`, `workgroup.*`).
- "Can I clear only the advertised host without changing the pairing name?" -> yes. `host.network.set_advertised` treats missing keys as preserve and explicit `""` as unset, so clients can update `host` and `device_name` independently.
