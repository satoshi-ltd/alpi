# Skills answer pack

Use this for skill frontmatter, env vars, secrets, validation,
keyword routing, and the `skill` tool.

## Answer directly

- Skills are user-owned directories under `~/.alpi/skills/<category>/<name>/`.
- Use the `skill` tool for skill file changes; generic file tools bypass validation.
- Static env vars go in profile `.env`; runtime credentials go in `<skill>/secrets/`.
- `alpi_knowledge` is not a skill; it is a native tool for alpi docs.

## Shape

Required:

- `SKILL.md`

Optional:

- `scripts/`
- `references/`
- `assets/`
- `secrets/`
- `state/`

All skills are user-owned. There is no bundled skill namespace.

## Frontmatter

```yaml
---
name: whoop-integration
description: Fetch daily health metrics from the Whoop API via OAuth
category: personal
version: 0.1.0
origin: agent
requires_env: [WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET]
requires_bins: [ffmpeg]
requires_config: [home_assistant.url]
platforms: [macos, linux]
tools: [terminal]
keywords: [whoop, workout]
created_at: 2026-04-20
---
```

Important fields:

- `description`: headline for semantic discovery.
- `keywords`: whole-token boost; avoid generic words.
- `origin`: `agent` or `user`; user-origin mutations need
  `confirm_user_skill=true`.
- `requires_env`, `requires_bins`, `requires_config`, `platforms`:
  hide inactive skills from prompt/hints and reject execution until met.

## Secrets and state

| Store | Purpose |
|---|---|
| Profile `.env` | Static env vars named in `requires_env`. |
| `<skill>/secrets/` | OAuth tokens, cookies, sessions, credentials. |
| `<skill>/state/` | Non-secret cache, JSONL, SQLite, sync cursors. |

Never put secret values in `SKILL.md`, scripts, references, assets, or
the skill root. `secrets/` should be mode `0700`; credential files
should be `0600`.

## Tool actions

Inspect:

- `list`
- `view(name, [file])`
- `validate(name)`

Mutate:

- `create`
- `edit`
- `patch`
- `set_meta`
- `add_file`
- `remove_file`
- `delete`
- `reset_state`

Execute:

- `run`
- `test`
- `invoke`

Notes:

- User-origin skills need `confirm_user_skill=true` for mutation.
- `delete` archives to `skills/.archive/...`.
- Pinned skills refuse delete until unpinned.
- `reset_state` wipes only `<skill>/state/`.
- `view(file=...)` returns `absolute_path`; use that path to run scripts.

## Validation and eligibility

- Invalid skills are hidden from the prompt.
- Inactive skills show `[inactive: missing …]` in list output and reject
  `run` / `test` / `invoke`.
- `validate` checks frontmatter plus script/runtime mistakes such as
  Python syntax/import issues and common OAuth/port problems.

## Per-skill DB

Use the `db` tool for structured SQLite state:

```python
db(action="exec", skill="whoop-tracker",
   sql="CREATE TABLE IF NOT EXISTS workouts (id INTEGER PRIMARY KEY, date TEXT)")
db(action="query", skill="whoop-tracker",
   sql="SELECT * FROM workouts ORDER BY date DESC LIMIT 7")
```

DB path: `<skill>/state/db.sqlite`.

## Anti-patterns

- Generic keywords such as `run`, `fetch`, `do`, `data`.
- Secret values in skill files.
- Nested subdirectories under `scripts/`, `references/`, or `assets/`.
- Third-party dependencies without a setup note.
- Duplicate skills instead of patching an existing one.

## Related topics

- Secrets and sandboxing: `security`
- Profile isolation: `profiles`
- Model choice for skill routing: `models`
- Architecture paths: `architecture`
