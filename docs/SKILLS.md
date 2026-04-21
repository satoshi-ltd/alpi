# Skills — how alf learns reusable recipes

A **skill** is a directory under `~/.alpi/skills/<category>/<name>/` that
teaches alf how to do something. The agent creates skills via the
`skill` tool; they go live under their declared category immediately.
The user manages them (view / delete) with `/skills`. There is no
approval gate — structure + security scanner + sandbox provide the
guarantees; a pending-dir ceremony doesn't add real protection and
inflates surface area.

## Directory contract

Every skill lives in a directory with one required file and up to four
optional subdirectories:

```
~/.alpi/skills/<category>/<name>/
  SKILL.md              # REQUIRED — prose instructions the agent reads
  scripts/              # OPTIONAL — executable code the skill invokes
  references/           # OPTIONAL — markdown docs the skill consults
  assets/               # OPTIONAL — templates and data (non-executable)
  secrets/              # OPTIONAL — credentials, mode 0700, gitignored
```

**No other structure is allowed.** Each subdirectory is flat — no
nested folders like `templates/colm2025/` or `scripts/subfolder/foo.py`.
Filenames must match `[a-zA-Z0-9][a-zA-Z0-9._-]{0,100}`. No hidden
files (`.foo`). No `DESCRIPTION.md` at the category level. No
`tools/`, `output/`, `_backup/`, or other invented subdirectories.

This rigidity is intentional: it makes skills **portable** (copy the
directory), **auditable** (`ls` shows you everything in one glance),
**cleanly deletable** (`rm -rf` the directory removes every trace),
and **predictable** (no digging through arbitrary nesting).

## Categories

Closed enum, enforced at creation:

```
software  data       research   productivity  communication  media
system    finance    personal   creative      security       meta
```

If a skill doesn't fit, pick the closest match and put the actual
domain in the description. Never invent a new category.

## Frontmatter

`SKILL.md` begins with YAML-like frontmatter:

```yaml
---
name: whoop-integration
description: Fetch daily health metrics from the Whoop API via OAuth.
category: personal
version: 0.1.0
origin: agent                   # "agent" (proposed) or "user" (hand-written)
requires_env: []                # pre-provisioned env vars in ~/.alpi/.env
tools: [read_file, terminal]    # tools the skill is allowed to call
stores_secrets: true            # if true, secrets/ is created mode 0700
created_at: 2026-04-20
---
```

### `description`

One line, ≤150 chars, starts with a verb. This is what the agent
matches against the current task to decide whether to load the skill.

### `requires_env`

Names of env vars the skill expects in `~/.alpi/.env`. Use this for
**pre-provisioned** secrets — API keys you paste in manually:

```yaml
requires_env: [WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET]
```

Values never land in the skill directory. `~/.alpi/.env` is the single
source of truth for pre-provisioned static secrets.

### `stores_secrets`

Set to `true` when the skill needs to **write** credentials at
runtime — OAuth tokens, refresh tokens, session cookies, anything
that rotates. The skill system creates `secrets/` with mode 0700 and
adds `skills/**/secrets/` to the profile's `.gitignore`.

Scripts inside the skill access these via a path relative to the
skill directory: `Path(__file__).parent.parent / "secrets" / "auth.json"`.

## Where credentials live

Two separate stores, two clear purposes:

| Store | Purpose | Lifecycle |
|---|---|---|
| `~/.alpi/.env` | Pre-provisioned static secrets declared in `requires_env`. User pastes the value in once. | Edited by hand. Shared across skills if they reference the same var. |
| `~/.alpi/skills/<cat>/<name>/secrets/` | Runtime-generated credentials (OAuth access+refresh, session blobs). Per-skill, never shared. | Created at runtime by scripts. Wiped when the skill is deleted. |

**Never** hardcode secrets inside `SKILL.md`, `scripts/`, `references/`,
or `assets/`. The security scanner rejects the most obvious patterns
(`api_key = "sk-..."`, `password = "..."`). It runs on SKILL.md body
and on every file added via `add_file` to `scripts`, `references`, or
`assets`. The `secrets/` subdir skips the scanner by design (the
whole point is that it holds keys).

## Actions on the `skill` tool

```
skill(action="create", name=..., category=..., description=..., body=...,
      [requires_env], [tools], [stores_secrets])
skill(action="edit",   name=..., body=..., [confirm_user_skill])
skill(action="add_file",    name=..., subdir=..., filename=..., content=...,
                             [confirm_user_skill])
skill(action="remove_file", name=..., subdir=..., filename=...,
                             [confirm_user_skill])
skill(action="delete", name=..., [confirm_user_skill])
skill(action="list")
```

### Creating a skill

`create` writes **only** `SKILL.md` and goes live immediately under
`~/.alpi/skills/<category>/<name>/`. Subdirectories come later via
`add_file`. A just-created skill has no scripts, no references, no
assets, no secrets (unless `stores_secrets=true`, which creates the
empty `secrets/` directory alongside SKILL.md).

The agent is capped at 40 agent-created skills total (tweakable via
`MAX_AGENT_SKILLS`). Beyond that, `create` errors and asks the user
to prune with `/skills` first.

### Adding files

```
skill(action="add_file",
      name="whoop-integration",
      subdir="scripts",          # scripts | references | assets | secrets
      filename="fetch.py",       # flat, no '/' or '..'
      content="<full file text>")
```

- `scripts/`, `references/`, `assets/` content is scanned for
  dangerous patterns (rm -rf, curl|sh, eval(), hardcoded keys, etc).
- `secrets/` content is not scanned (by design). Files written there
  are `chmod 0600`.

### Origin gate

Every mutation on a user-owned skill (`origin: user` in frontmatter)
requires `confirm_user_skill=true`. Agent-created skills (`origin:
agent`) can be modified by the agent freely — they're provisional by
nature.

### Skill quota

The agent can hold at most **40 agent-created skills** at a time
(`MAX_AGENT_SKILLS`). User-created skills don't count. Beyond the cap,
`create` errors and asks the user to prune with `/skills`.

## Example skill: Whoop OAuth integration

Start with the prose + secrets flag:

```python
skill(
    action="create",
    name="whoop-integration",
    category="personal",
    description="Fetch daily Whoop health metrics via OAuth.",
    body=(
        "## When to use\n"
        "The user asks about today's recovery, strain, or sleep data.\n\n"
        "## How it works\n"
        "1. If secrets/auth.json is missing or expired, run "
        "scripts/oauth.py to refresh.\n"
        "2. Read scripts/fetch.py for the metric the user asked about.\n"
    ),
    stores_secrets=True,
)
```

Add the scripts:

```python
skill(action="add_file", name="whoop-integration",
      subdir="scripts", filename="oauth.py", content="<OAuth flow>")
skill(action="add_file", name="whoop-integration",
      subdir="scripts", filename="fetch.py", content="<API call>")
```

Add a reference doc:

```python
skill(action="add_file", name="whoop-integration",
      subdir="references", filename="api-endpoints.md",
      content="# Whoop API\n- /cycles\n- /recovery\n- /sleep\n")
```

The resulting directory:

```
~/.alpi/skills/personal/whoop-integration/
  SKILL.md
  scripts/
    oauth.py
    fetch.py
  references/
    api-endpoints.md
  secrets/              # empty until oauth.py runs
```

When `oauth.py` runs, it writes `../secrets/auth.json` with the
tokens. Next time the agent fetches metrics, `fetch.py` reads from
the same path. The user knows **one place** to find or wipe
credentials for this skill.

Deleting the skill removes the whole tree including secrets — no
residue left behind.

## Anti-patterns (enforced)

- Skills at the top of `skills/` with no category directory (e.g.
  `skills/orphan-skill/`) — always inside a category.
- `DESCRIPTION.md` at the category level (`skills/apple/DESCRIPTION.md`).
  Category metadata lives in this doc; per-category annotation is
  noise.
- Nested subdirectories (`scripts/subfolder/foo.py`,
  `assets/templates/variant1/template.md`). Flat subdirs only.
- Extensions outside the allowed 4 (`tools/`, `data/`, `cache/`,
  `output/`, `logs/`). Ephemeral output is the workspace's job, not
  the skill's.
- Credentials anywhere outside `secrets/` (or `~/.alpi/.env` for
  pre-provisioned ones).
- Files in `scripts/` / `references/` / `assets/` that contain
  hardcoded API keys, passwords, or tokens. Security scanner blocks.
- Hidden files (`.foo`, `.secret`). Rejected by the filename regex.

## Migration from Hermes or other sources

Hermes skills map cleanly for the simple case (just `SKILL.md`). For
richer ones, reshape:

| Hermes | alf |
|---|---|
| `skills/<cat>/<name>/SKILL.md` | `~/.alpi/skills/<cat>/<name>/SKILL.md` |
| `skills/<cat>/<name>/scripts/*.py` | `scripts/*.py` (flat, no subdirs) |
| `skills/<cat>/<name>/references/*.md` | `references/*.md` (flat) |
| `skills/<cat>/<name>/templates/<subfolder>/*` | `assets/*` (flatten, prefix filenames if needed) |
| Credentials in random `whoop.json` at skill root | Move to `secrets/` and set `stores_secrets: true` |
| `DESCRIPTION.md` at category level | Drop; redundant |

The frontmatter also needs adapting: Hermes uses `metadata.hermes`,
alf uses flat fields (`name`, `description`, `category`, etc.).
