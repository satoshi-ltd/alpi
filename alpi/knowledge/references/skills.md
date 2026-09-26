# Skills answer pack

## Answer directly

- Skills are user-owned directories under `~/.alpi/skills/<category>/<name>/`. No bundled namespace.
- Use the `skill` tool for skill file changes; generic file tools bypass validation.
- Static env vars go in profile `.env`; runtime credentials go in `<skill>/secrets/`.
- Skill `scripts/run.py` runs with `cwd` = the skill dir: use `$ALPI_WORKSPACE` for workspace/project files and `$ALPI_SKILL_DIR` for bundled files — a bare relative path roots at the skill dir, not the workspace.
- `alpi_knowledge` is not a skill; it is a native tool for alpi docs.

## Shape

`SKILL.md` required. Optional flat subdirs: `scripts/`, `references/`, `assets/`, `secrets/`, `state/`. No other structure, no nesting, no hidden files. All skills user-owned.

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
pinned: false
created_at: 2026-04-20
---
```

- `description`: headline for semantic discovery.
- `keywords`: whole-token boost; avoid generic words.
- `origin`: `agent` or `user`; user-origin mutations need `confirm_user_skill=true`.
- `tools`: metadata only, not enforced at runtime; used for documentation / curator / inventory.
- `pinned`: `true` blocks `skill(delete)` and `alpi curator apply` archive (unpin via `set_meta` to remove).
- `requires_env`, `requires_bins`, `platforms`: always checked; hide inactive skills from prompt/hints and reject execution.
- `requires_config`: opt-in gate — checked only when the caller passes the raw profile config; `skills_index_block` and `skill(run|test|invoke)` do so, programmatic callers that omit `cfg_raw` skip it.

## Secrets and state

| Store | Purpose |
|---|---|
| Profile `.env` | Static env vars named in `requires_env`. |
| `<skill>/secrets/` | OAuth tokens, cookies, sessions, credentials. |
| `<skill>/state/` | Non-secret cache, JSONL, SQLite, sync cursors. |

Never put secret values in `SKILL.md`, scripts, references, assets, or the skill root. `secrets/` mode `0700`; credential files `0600`.

## Generated files (where a skill writes its artifacts)

| Destination | Use for | Lifecycle |
|---|---|---|
| tmp dir | Pipeline intermediates never delivered or re-referenced | The skill deletes them itself; nothing purges tmp automatically |
| `<home>/out/` | Chat-delivered artifacts (generated images, documents) — print `{"out": "<abs path>"}` so the file attaches to the reply | Downloadable for ~30 days (`GENERATED_KEEP_DAYS`), then offered by cleanup; excluded from backups and from newly bootstrapped Alpi `.gitignore` files (existing/custom profiles should ignore `out/` themselves) |
| workspace path | Project deliverables that belong to ongoing work | The workspace's own lifecycle (git/sync/backup) |

Never deliver from shared tmp: sessions retain absolute paths, but tmp has no retention guarantee and the producing skill owns cleanup — `out/` is the delivery surface with retention. A document printed from tmp or from elsewhere in the home is not attached at all (images still are).

## Tool actions

- Inspect: `list`, `view(name, [file])`, `validate(name)`.
- Mutate: `create`, `edit`, `patch`, `set_meta`, `add_file`, `remove_file`, `delete`, `reset_state`.
- Execute: `run`, `test`, `invoke`.

Notes:

- User-origin skills need `confirm_user_skill=true` for mutation.
- `delete` archives to `skills/.archive/...`; pinned skills refuse delete until unpinned.
- Bulk cleanup is CLI-only: `alpi curator review` flags stale/cold skills, `alpi curator apply` archives non-pinned ones after preview + confirm (idempotent; pinned untouched).
- `reset_state` wipes only `<skill>/state/`.
- `view(file=...)` returns `absolute_path`; use it to run scripts.

## Validation and eligibility

- Invalid skills are hidden from the prompt.
- Inactive skills show `[inactive: missing …]` in `list` and reject `run`/`test`/`invoke`.
- `validate` checks frontmatter plus runtime mistakes (Python syntax/import issues, common OAuth/port problems).

## Per-skill DB

Use the `db` tool for structured SQLite state (path `<skill>/state/db.sqlite`):

```python
db(action="exec", skill="whoop-tracker",
   sql="CREATE TABLE IF NOT EXISTS workouts (id INTEGER PRIMARY KEY, date TEXT)")
db(action="query", skill="whoop-tracker",
   sql="SELECT * FROM workouts ORDER BY date DESC LIMIT 7")
```

`exec` without `params` runs several `;`-separated statements in one transaction (all or none; the error names the failing statement); with `params` it takes exactly one. A script with its own `BEGIN`/`COMMIT`/`ROLLBACK`/`SAVEPOINT`/`RELEASE` is refused by the SQLite authorizer, not by matching text. `RETURNING` rows (or a `SELECT` sent as `exec`) come back under `returned:`, drained in batches and capped at 10 000 shown. Attaching or writing another database file (`ATTACH '<file>'`, `VACUUM INTO '<file>'`) is refused on every action, including targets computed at run time or bound as a parameter (the authorizer allows only the anonymous `""` target), so a skill reaches only its own database; plain `VACUUM` (whose scratch database is anonymous) still works.

## Anti-patterns

- Generic keywords (`run`, `fetch`, `do`, `data`).
- Secret values in skill files.
- Nested subdirs under `scripts/`, `references/`, `assets/`.
- Third-party deps without a setup note.
- Duplicate skills instead of patching an existing one.

## Related topics

- Secrets and sandboxing: `security`
- Profile isolation: `profiles`
- Model choice for skill routing: `models`
- Architecture paths: `architecture`
