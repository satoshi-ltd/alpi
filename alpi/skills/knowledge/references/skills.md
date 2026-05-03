# Skills answer pack

Use this for user skills, bundled skills, frontmatter, env vars,
secrets, validation, keyword routing, and the `skill` tool.

## Short answer

A skill is a reusable workflow under
`~/.alpi/skills/<category>/<name>/`. It has a required `SKILL.md` plus
optional `scripts/`, `references/`, `assets/`, `secrets/`, and
`state/` directories.

## Namespaces

- User skills: `~/.alpi/skills/<category>/<name>/`
- Bundled skills: `@alpi/<name>`, shipped inside the package and
  read-only.
- Variant pattern: make a user skill with a new name instead of
  editing a bundled skill.

## Frontmatter

```yaml
---
name: whoop-integration
description: Fetch daily health metrics from the Whoop API via OAuth
category: personal
version: 0.1.0
origin: agent
requires_env: [WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET]
tools: [terminal]
keywords: [whoop, workout]
created_at: 2026-04-20
---
```

Important fields:

- `description`: short headline for semantic discovery.
- `requires_env`: env vars required before the skill is shown in the
  system prompt.
- `keywords`: whole-token boost for discovery; avoid generic words.
- `origin`: `agent`, `user`, or `bundled`; user-origin mutations
  require confirmation.

## Env and secrets

| Store | Purpose |
|---|---|
| `~/.alpi/.env` | Static secrets named in `requires_env`. |
| `<skill>/secrets/` | Runtime credentials such as OAuth tokens; created lazily when written. |
| `<skill>/state/` | Non-secret state such as caches, JSONL, SQLite. |

When `skill(action="view")` opens a skill, vars declared in
`requires_env` are registered for terminal subprocess passthrough.

Never hardcode secrets in `SKILL.md`, scripts, references, or assets.

## Actions

```python
skill(action="create", name=..., category=..., description=..., body=...)
skill(action="view", name=...)
skill(action="view", name=..., file="references/foo.md")
skill(action="patch", name=..., old_string=..., new_string=...)
skill(action="add_file", name=..., subdir=..., filename=..., content=...)
skill(action="remove_file", name=..., subdir=..., filename=...)
skill(action="validate", name=...)
skill(action="reset_state", name=...)
skill(action="delete", name=...)
skill(action="list")
```

Use the `skill` tool for all skill file changes. Do not use generic
file-edit tools inside skill directories, because they bypass scanner
and validation behavior.

`view(file=...)` includes `absolute_path` before the file contents.
Use that absolute path when executing a skill script; do not run
`scripts/foo.py` relative to the workspace.

## Validation and list states

`skill(action="list")` shows:

- active skills with no tag,
- invalid skills with `[invalid: ...]`,
- inactive skills with `[inactive: missing env var X]`.

`skill(action="validate")` runs frontmatter checks plus runtime checks
for Python syntax/imports and common OAuth/port mistakes.

## Persistent state

Use the `db` tool for structured per-skill SQLite:

```python
db(action="exec", skill="whoop-tracker",
   sql="CREATE TABLE IF NOT EXISTS workouts (id INTEGER PRIMARY KEY, date TEXT)")
db(action="query", skill="whoop-tracker",
   sql="SELECT * FROM workouts ORDER BY date DESC LIMIT 7")
```

The DB lives at `<skill>/state/db.sqlite`. Use
`skill(action="reset_state", name=...)` to wipe all state files.

## Model quality

Skills depend on correct tool routing. Very small models may ignore
the skill index or skip `skill(action="view")`. For skill-heavy
profiles, use a model recommended for routing in `models.md`.

## Anti-patterns

- Generic keywords such as `run`, `fetch`, `do`, `data`.
- Secret values in skill files.
- Nested subdirectories under `scripts/`, `references/`, or `assets/`.
- Adding third-party dependencies without a `Setup` section.
- Creating duplicate skills when an existing one can be patched.
