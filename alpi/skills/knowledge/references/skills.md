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
requires_bins: [ffmpeg]              # optional — exec on PATH
requires_config: [home_assistant.url] # optional — user-set keys in config.yaml
platforms: [macos, linux]            # optional — empty/absent = portable
tools: [terminal]
keywords: [whoop, workout]
created_at: 2026-04-20
---
```

Fields:

- `description`: headline for semantic discovery.
- `keywords`: whole-token boost; avoid generic words.
- `origin`: `agent` | `user` | `bundled`. User-origin mutations need `confirm_user_skill=true`.

Eligibility (any unmet requirement → hidden from prompt + hint; `list` shows compound `[inactive: missing …]`):

| Field | Check |
|---|---|
| `requires_env` | `os.environ.get(var)` truthy after `~/.alpi/.env` is loaded |
| `requires_bins` | `shutil.which(bin)` not None; bin name only, no path separators |
| `requires_config` | dotted path resolves to non-empty value in user's `~/.alpi/config.yaml`; alpi defaults do not count |
| `platforms` | current `sys.platform` (`darwin`→`macos`, `linux`, `win32`→`windows`) in the declared set; empty/absent = portable |

`skill(action="run"|"test"|"invoke")` on an inactive skill rejects with `"skill X is inactive: missing …"` before spawning.

## Env and secrets

| Store | Purpose |
|---|---|
| `~/.alpi/.env` | Shared/static profile secrets named in `requires_env`. |
| `<skill>/secrets/` | Per-skill credential files and runtime auth state such as OAuth access/refresh tokens, cookies, or sessions. |
| `<skill>/state/` | Non-secret state such as caches, JSONL, SQLite. |

When `skill(action="view")` opens a skill, vars declared in
`requires_env` are registered for terminal subprocess passthrough.

Never hardcode secrets in `SKILL.md`, scripts, references, assets, or
the skill root. `secrets/` should be mode `0700`; files containing
credentials should be mode `0600`.

## Actions

Inspection: `list`, `view(name, [file])`, `validate(name)`.

Mutating (user skills need `confirm_user_skill=true`; bundled `@alpi/*` rejects every mutation):

```python
skill(action="create",      name, category, description, body,
      [requires_env], [requires_bins], [requires_config], [platforms],
      [tools], [keywords], [output_schema])
skill(action="edit",        name, body, [confirm_user_skill])
skill(action="patch",       name, subdir, filename, old_string, new_string, [confirm_user_skill])
skill(action="set_meta",    name, fields={…}, [confirm_user_skill])
skill(action="add_file",    name, subdir, filename, content, [confirm_user_skill])
skill(action="remove_file", name, subdir, filename, [confirm_user_skill])
skill(action="delete",      name, [confirm_user_skill])
skill(action="reset_state", name, [confirm_user_skill])
```

Execution: `run(name, [args])`, `test(name, [args])`, `invoke(name, [args])`.

- `delete` archives to `skills/.archive/<category>/<name>__<UTC>/`. Pinned skills (`pinned: true`) refuse `delete` until unpinned via `set_meta`.
- `reset_state` wipes `<skill>/state/`; preserves SKILL.md / scripts / references / assets / secrets.

Use the `skill` tool for all skill file changes. Do not use generic
file-edit tools inside skill directories, because they bypass scanner
and validation behavior.

`view(file=...)` includes `absolute_path` before the file contents.
Use that absolute path when executing a skill script; do not run
`scripts/foo.py` relative to the workspace.

## list tags

- active: no tag.
- `[invalid: <field> (<message>)]` — schema errors. Skill is hidden from prompt entirely.
- `[inactive: missing …]` — eligibility unmet. Multiple reasons compound, e.g. `[inactive: missing env var TOKEN, binary gh]`.

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
