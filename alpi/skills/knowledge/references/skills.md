# Skills — how alpi learns reusable recipes

A **skill** is a directory under `~/.alpi/skills/<category>/<name>/` that
teaches alpi how to do something. The agent creates skills via the
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
miscellaneous
```

If a skill doesn't fit, pick the closest match and put the actual
domain in the description. Never invent a new category.

## Bundled vs user skills

There are two namespaces, kept strictly apart by construction.

**User skills** live under `{home}/skills/<category>/<name>/` and
are the only ones the `skill` tool can create, edit, or delete.
These are the skills the user (or the agent on the user's behalf)
writes.

**Bundled skills** ship with the alpi package and are addressed
with the prefix `@alpi/<name>`. They live inside the `alpi.skills`
package as importable resources; they never materialise on disk
at `{home}/skills/`.

### Why ship skills with the binary

A bundled skill is a curated capability that ships **with the
binary**. Five properties fall out of that single decision:

1. **No second install step.** `uv tool install alpi-agent` and
   the skill is live. No registry to fetch from, no marketplace
   to browse, no `npm install`-equivalent for capabilities. The
   user gets a useful agent on first run.
2. **Works offline.** Embedded as package resources, not
   downloaded on demand. A laptop on a plane still has every
   bundled skill available.
3. **Version-pinned to the binary.** A bundled skill that uses a
   new tool API cannot drift from the binary that exposes that
   API. There is no compatibility matrix to maintain — the skill
   is built and tested against the same wheel the user installs.
4. **Auditable.** The source is in the wheel. `unzip -l
   alpi_agent-X.Y.Z.whl | grep skills/` shows every file. No
   external fetch, no mystery code path.
5. **Curated, not a catalog.** First-party capabilities Satoshi
   Ltd. ships because they solve a recurring problem we've seen
   in real use, or because the skill is self-referential and
   *can't* be authored by the user (they'd need the answer
   first to write it).

### Properties enforced on every bundled skill

- **Read-only.** `skill(action="create"|"edit"|"patch"|
  "add_file"|"remove_file"|"delete")` on a `@alpi/*` name is
  rejected with a message pointing at the variant pattern below.
- **Always-latest.** Upgrades land on every `uv tool install
  --reinstall`; bundled skills track the binary, no merge, no
  migration, no drift.
- **Discoverable.** `skill(action="list")` shows them under the
  `@alpi/` heading; `skills_index_block` injects them into every
  system prompt with the `[bundled]` marker.

**Collision is impossible by construction.** The `@` sigil is not
a legal category name (the category validator rejects any
`category.startswith("@")`). A user cannot create `@alpi/foo`;
if a rogue write lands at `{home}/skills/@alpi/foo/SKILL.md`
directly via shell, the listing skips any category whose name
starts with `@` as a defence in depth.

**Variant pattern.** If a user wants their own take on a bundled
skill (e.g. "`@alpi/obsidian-writer` but tuned for my vault"),
they create a new user skill with a different name in any non-`@`
category — for example `personal/obsidian-writer`. Both coexist
and both appear in the `skill list` + system-prompt index; the
LLM picks by description fit.

**Discovery primacy.** User skills render first in the system-
prompt index, bundled after with the `[bundled]` marker. That
ordering nudges the LLM toward user-tailored content when a
semantic match exists.

### Currently bundled

| Skill | Description |
|---|---|
| `@alpi/knowledge` | Answer questions about alpi itself — config, commands, ALP protocol, skills, security, gateways, deployment — using the bundled documentation instead of guessing or web-searching. |

Each entry above is a directory under `alpi/skills/<name>/` in
the source tree. The set grows by curation, not by submission.

### Curation policy — when does something become bundled?

A capability earns a slot in `@alpi/*` when **at least one** of
these is true:

- **It's self-referential.** The user can't reasonably author it
  themselves because the skill *is* the knowledge they'd need to
  author it. `@alpi/knowledge` is the canonical example: a user
  who doesn't know how alpi works can't write a skill that
  teaches alpi how alpi works.
- **It must work offline / on first install.** Anything
  intrinsic to the agent's UX from the moment it starts. A user
  who has just typed `alpi setup` for the first time should not
  need network access to ask "how do I do X?".
- **It's a recurring user pattern.** Five users authored the
  same skill across their profiles. A pattern that repeats is a
  candidate to lift into the bundle.

Things that **don't** belong in `@alpi/*`:

- Third-party integrations (Whoop, Strava, Notion, …). Those
  belong in the user namespace, or eventually in the federated
  skills marketplace tracked under `AY` (v0.5 roadmap).
- Vendor-specific or workspace-specific recipes. By definition
  not portable enough to ship for everyone.
- Anything that needs credentials. Bundled skills are read-only
  and stateless; secrets live in the user namespace.


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

| Hermes | alpi |
|---|---|
| `skills/<cat>/<name>/SKILL.md` | `~/.alpi/skills/<cat>/<name>/SKILL.md` |
| `skills/<cat>/<name>/scripts/*.py` | `scripts/*.py` (flat, no subdirs) |
| `skills/<cat>/<name>/references/*.md` | `references/*.md` (flat) |
| `skills/<cat>/<name>/templates/<subfolder>/*` | `assets/*` (flatten, prefix filenames if needed) |
| Credentials in random `whoop.json` at skill root | Move to `secrets/` and set `stores_secrets: true` |
| `DESCRIPTION.md` at category level | Drop; redundant |

The frontmatter also needs adapting: Hermes uses `metadata.hermes`,
alpi uses flat fields (`name`, `description`, `category`, etc.).
