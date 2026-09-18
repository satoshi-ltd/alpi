# Skills — how alpi learns reusable recipes

A **skill** is a directory under `~/.alpi/skills/<category>/<name>/` that
teaches alpi how to do something. The agent creates skills via the
`skill` tool; they go live under their declared category immediately.
The user manages them (view / delete) with `/skills`. There is no
approval gate — structure + security scanner + sandbox provide the
guarantees; a pending-dir ceremony doesn't add real protection and
inflates surface area.

## Directory contract

Every skill lives in a directory with one required file and up to five
optional subdirectories:

```
~/.alpi/skills/<category>/<name>/
  SKILL.md              # REQUIRED — prose instructions the agent reads
  scripts/              # OPTIONAL — executable code the skill invokes
  references/           # OPTIONAL — markdown docs the skill consults
  assets/               # OPTIONAL — templates and data (non-executable)
  secrets/              # OPTIONAL — credentials, mode 0700, gitignored
  state/                # OPTIONAL — runtime persistence (db.sqlite,
                        #            counters, caches). Gitignored.
                        #            Wiped by `skill(action='reset_state')`.
```

**No other structure is allowed.** Each subdirectory is flat — no
nested folders like `templates/colm2025/` or `scripts/subfolder/foo.py`.
Filenames must match `[a-zA-Z0-9][a-zA-Z0-9._-]{0,100}`. No hidden
files (`.foo`). No `DESCRIPTION.md` at the category level. No
`tools/`, `output/`, `_backup/`, or other invented subdirectories.

`scripts/`, `references/`, and `assets/` are scanned for dangerous
patterns at write time. `secrets/` and `state/` skip the scanner by
design — `secrets/` holds credentials whose entropy looks like the
patterns the scanner catches, and `state/` holds opaque runtime data
(SQLite blobs, JSONL logs) the agent itself manages.

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

## Skills are user-owned

All skills live under `{home}/skills/<category>/<name>/` and the
`skill` tool can create, edit, or delete them. There is no
"bundled" namespace any more: capabilities the runtime needs to
self-describe (e.g. answering questions about alpi itself) are
exposed as **first-class tools**, not as skills.

The single example is the `alpi_knowledge` tool, which reads the
hand-maintained answer packs shipped under `alpi/knowledge/references/`.
It is available on every profile from the moment alpi is installed; the
system prompt instructs the agent to call it before answering any question
about alpi. See [ARCHITECTURE.md](ARCHITECTURE.md) for the tool layer.

## Frontmatter

`SKILL.md` begins with YAML-like frontmatter:

```yaml
---
name: whoop-integration
description: Fetch daily health metrics from the Whoop API via OAuth
category: personal
version: 0.1.0
origin: agent                   # "agent" (proposed) or "user" (hand-written)
requires_env: []                # env vars the skill needs; missing ones hide it
requires_bins: [gh]             # executables on PATH; missing ones hide the skill
requires_config: []             # profile config keys (dotted); missing ones hide it
platforms: [macos, linux]       # supported OSes; empty/absent = portable
tools: [read_file, terminal]    # tools the skill expects to call —
                                # METADATA ONLY, not enforced at runtime
                                # (used by curator / docs / inventory).
                                # Built-ins are snake_case; MCP tools
                                # use the server's native form
                                # (e.g. ``bitbucket__getPullRequests``).
keywords: [whoop, workout]      # optional lowercase tokens for keyword boost
pinned: false                   # set true to protect from delete +
                                # curator archive (default false)
created_at: 2026-04-20
---
```

The frontmatter is validated field-by-field on every `create` /
`edit`; errors block the operation, warnings inform. Run
`skill(action='validate', name=...)` against any installed skill to
see both schema findings and runtime checks (syntax, imports,
OAuth ordering, port coherence) in one pass.

### `description`

One line, ≤150 chars. Headline — drop the trailing period (the
schema warns if you forget). This is what the agent matches against
the current task to decide whether to load the skill.

### Eligibility — four ways a skill can be inactive

A skill is **active** only when every declared requirement resolves
in the current profile. Four kinds of requirement can each gate a
skill independently; missing requirements hide the skill from the
system prompt and from the per-turn keyword hint, and surface in
`skill(action='list')` with `[inactive: missing …]`.

The rule across surfaces: **explicit target → hard error; implicit
availability → silent filter**. Calling `skill(action='run' | 'test'
| 'invoke', name=X)` on an inactive skill fails fast with a clear
"missing …" reason. The agent never sees inactive skills in the
prompt or the keyword hint, so it cannot pick them by accident.

#### `requires_env`

Env vars the skill needs. Resolved per profile — the process
environment overlaid with that profile's own `.env` — so a value in
`<profile-home>/.env` counts. Missing or empty → inactive.

```yaml
requires_env: [WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET]
```

Values never land in the skill directory. `~/.alpi/.env` is the
single source of truth for pre-provisioned static secrets.

#### `requires_bins`

Executables the skill expects on `PATH`. Checked with `shutil.which`;
missing binaries → inactive. Use the bin's command name only — no
path separators.

```yaml
requires_bins: [gh, ffmpeg, sqlite3]
```

alpi does not auto-install anything. Declaring `requires_bins` is a
contract with the user: install the bin, the skill becomes active
on the next session.

#### `requires_config`

Profile config keys, dotted, checked against **the user's
``~/.alpi/config.yaml`` only** — not against alpi's merged defaults.
This is deliberate: skills using this gate are declaring that the
user must opt in explicitly. A key counts as "set" when the user
wrote a non-empty value (non-null, non-empty-string, non-empty-list,
non-empty-dict); a key that resolves to its alpi default is treated
as unset.

```yaml
requires_config: [home_assistant.url, home_assistant.token]
```

Use this for skills that depend on user-set profile config the
agent cannot infer (an API base URL, a credential file path, a
feature flag specific to the user's setup). Do not use it to check
alpi's own defaults — those always look "set" to the user but
intentionally do not count here.

`requires_config` is checked wherever a user meets a skill — the
system-prompt index and `skill(action="run"|"test"|"invoke")` — and is a
discovery filter rather than an execution barrier the runtime applies
everywhere.

#### `platforms`

Operating systems the skill supports. One or more of `macos`,
`linux`, `windows`. Empty/absent = portable (no platform check).

```yaml
platforms: [macos, linux]
```

A skill declaring `platforms: [linux]` running on macOS shows up
in `list` as `[inactive: missing platform linux (this is macos)]`.

### `pinned` — protect from delete + curator archive

Optional boolean. Default `false`. When `true`, the skill refuses
`skill(action="delete", ...)` (`set_meta` it back to `false` first)
and is left untouched by `alpi curator apply`'s bulk archive of
stale/cold skills. Use it on skills you have hand-curated, on
mission-critical recipes, or on anything the agent has hooked into
that you do not want autoswept.

```yaml
pinned: true
```

`reset_state` and other surgical actions still apply to pinned
skills — `pinned` guards lifecycle (delete / bulk archive), not
content edits.

### `keywords` — per-turn discovery boost

Optional lowercase tokens. When the user's current message contains
any of them, the engine injects a one-line "skill hint" system
message for that turn pointing at this skill. Helps small models
(local Llama, Haiku) that miss obvious matches from descriptions
alone; big models (Sonnet, Opus) usually don't need it.

```yaml
keywords: [whoop, workout, fitness]
```

The matcher lower-cases the user's message and matches whole tokens.
Use concrete domain terms — `whoop`, `notion`, `pomodoro` — never
generic verbs (`do`, `run`, `fetch`) which hit too often. Inactive
skills (failing any eligibility check — `requires_env`,
`requires_bins`, `requires_config`, or `platforms`) do not get
boosted, even if a keyword matches.

## Where credentials live

Two separate stores, two clear purposes:

| Store | Purpose | Lifecycle |
|---|---|---|
| `~/.alpi/.env` | Pre-provisioned shared/static secrets declared in `requires_env`. User pastes the value in once. | Edited by hand. Shared across skills if they reference the same var. |
| `~/.alpi/skills/<cat>/<name>/secrets/` | Per-skill credential files and runtime auth state (OAuth client files, access+refresh tokens, cookies, session blobs). Per-skill, never shared. | Created lazily when the skill writes a secret. Wiped when the skill is deleted. |

**Never** hardcode secrets inside `SKILL.md`, `scripts/`, `references/`,
`assets/`, or the skill root. The security scanner rejects the most obvious patterns
(`api_key = "sk-..."`, `password = "..."`). It runs on SKILL.md body
and on every file added via `add_file` to `scripts`, `references`, or
`assets`. The `secrets/` subdir skips the scanner by design (the
whole point is that it holds keys). `secrets/` should be mode `0700`;
files containing credentials should be mode `0600`.

## Where generated files go

A skill that produces files picks the destination by the file's nature, never `/tmp` for anything the user receives:

- **Pipeline intermediates** (conversion scraps, temp frames) → the tmp dir; nobody references them after the turn, and the skill deletes them itself (nothing purges tmp automatically).
- **Chat deliveries** (a generated image, an exported document) → `<home>/out/`; print `{"out": "<absolute path>"}` from the runner and the file rides the reply as an attachment. These stay downloadable for ~30 days, then the cleanup wizard offers to remove them; they are excluded from `alpi backup` and by newly bootstrapped Alpi `.gitignore` files; existing or custom profiles should ignore `out/` themselves.
- **Project deliverables** (work that belongs to an ongoing project) → a path inside the profile's workspace, which has its own lifecycle (git, sync, backups).

Never deliver from shared tmp: sessions retain absolute paths, but tmp has no retention guarantee and the producing skill owns its cleanup — `out/` is the delivery surface with retention.

## Model quality matters

Skills rely on tool-calling discipline and correct routing. Weak or
very small models may ignore the skill index, over-trigger generic
tools, or skip `skill(action="view")` even when a skill matches. For
skill-heavy profiles, use a model recommended for routing in
[MODELS.md](MODELS.md); reserve low-end models for simple, low-risk
turns.

## Persistent state — SQLite via the `db` tool

Skills that need structured state (more than a single JSON blob,
multi-row history, set / lookup / aggregate semantics) use the
`db` tool — first-class SQL without writing a Python script:

```
db(action="exec",  skill="whoop-tracker",
   sql="CREATE TABLE IF NOT EXISTS workouts (id INTEGER PRIMARY KEY, date TEXT, mins INTEGER)")

db(action="exec",  skill="whoop-tracker",
   sql="INSERT INTO workouts (date, mins) VALUES (?, ?)",
   params=["2026-05-03", 35])

db(action="query", skill="whoop-tracker",
   sql="SELECT date, mins FROM workouts ORDER BY date DESC LIMIT 7")
```

Backed by `<profile-home>/skills/<cat>/<skill>/state/db.sqlite`.
Always parameterised — `params=[…]` binds to `?` placeholders;
never string-interpolate user data into the SQL. Schema is owned
by the skill body — the LLM runs `CREATE TABLE IF NOT EXISTS …`
on first invocation; idempotent.

**Quotas (enforced):**

- 50 MB max file size — prune with `DELETE` or run
  `skill(action='reset_state', name=…)` to nuke and start over.
- 10 000 rows max per `query` result — tighten with `WHERE` /
  `LIMIT`.
- 5 s busy / lock timeout at the SQLite level.

**Scope:** strictly per-skill. The `skill` argument resolves
against the profile's installed skills, and `alpi backup` includes
`db.sqlite` like any other file under the skill directory.

`skill(action='reset_state', name=…)` wipes everything under
`<skill>/state/` (including `db.sqlite`, JSONL logs, anything
else). Useful when a schema change leaves the DB inconsistent;
preserves the rest of the skill (scripts, secrets, SKILL.md).

## Language: skills are written in English

Every file inside a skill directory — `SKILL.md` (frontmatter +
body), `scripts/`, `references/`, `assets/` — is written in
**English**, regardless of the language the user / author speaks.
SKILL.md bodies reload into the system prompt every time the
agent opens the skill; non-English content there biases the
agent's reply language across every future session and every
profile that has the skill installed.

The rule is enforced at the prompt level (the `skill` tool's own
description tells the LLM to translate before writing). When
authoring a skill by hand, follow the same rule: write in English
even if you happen to be working in another language right now.
The user-facing surface — the agent's chat replies — still
matches the user's language. Only the persisted content is
fixed.

## Actions on the `skill` tool

| Action | What it does |
|---|---|
| `list` | Every installed skill with its status (`active`, `[inactive: missing …]`, invalid). |
| `view` | SKILL.md, or one file under the skill (`file="scripts/foo.py"`), prefixed with its absolute path. |
| `validate` | Schema findings plus runtime checks (syntax, imports, OAuth ordering, port coherence). |
| `create` | Writes **only** `SKILL.md`; the skill is live immediately. |
| `edit`, `patch`, `set_meta` | Replace the body, make a small edit to one file, or change frontmatter fields without touching prose. |
| `add_file`, `remove_file` | Manage files under `scripts/`, `references/`, `assets/`, `secrets/`, `state/`. Flat names only; the scanner runs on everything except `secrets/` and `state/`. |
| `delete` | Archives to `skills/.archive/<category>/<name>__<UTC>/` — recoverable. Refused while `pinned: true`. |
| `reset_state` | Wipes `state/` (including `db.sqlite`) and nothing else. |
| `run`, `test`, `invoke` | Execute the skill (below). |

Mutations on a user-written skill (`origin: user`) require
`confirm_user_skill=true`; agent-created skills are provisional and the agent
may change them freely. The agent can hold at most **40** agent-created
skills; beyond that `create` fails and asks you to prune with `/skills`. For
bulk cleanup, `alpi curator review` flags stale skills and `alpi curator
apply` archives the non-pinned ones after a preview.

### Running a skill

`skill(action="run", name=…)` is the canonical way to execute a skill. With
a `scripts/run.py`, alpi spawns it with the skill directory as `cwd` and
`ALPI_HOME`, `ALPI_WORKSPACE`, `ALPI_SKILL_NAME`, `ALPI_SKILL_DIR` in the
environment — use `$ALPI_WORKSPACE` for project files and `$ALPI_SKILL_DIR`
for files bundled with the skill. Stdout comes back as the tool result;
the timeout is 600 s; a missing `requires_env` variable fails the call before
the script starts. Scripts are plain Python and run in their own process, so they cannot call
alpi's tools or MCP methods the way the agent does — validation refuses the
obvious `from alpi import <tool>`, and a skill that needs a tool should say so
in its prose and let the agent make the call. Without a script, `run` returns
SKILL.md with a directive so the agent follows the prose with the real tools
instead of improvising. Pass `args=[…]` to forward CLI arguments.

If the frontmatter declares `output_schema` (a one-line JSON object using
`type` / `properties` / `required` / `items` / `enum`), `run` validates
stdout against it. `test` runs the same path as a minimal harness for
scripted skills. `invoke` is the strict composition surface: it accepts only
scripted skills that declare `output_schema`, so a skill calling another
skill always gets machine-readable JSON.

## Example skill: Whoop OAuth integration

Start with the prose:

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
)
```

Then add scripts with `skill(action="add_file", subdir="scripts", …)` and a
reference doc under `references/`.

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

When `oauth.py` runs it writes `secrets/auth.json`; `fetch.py` reads the
same file. One place to find or wipe this skill's credentials, and deleting
the skill removes the whole tree, secrets included.

## Anti-patterns

Refused by the code:

- Nested subdirectories (`scripts/subfolder/foo.py`,
  `assets/templates/variant1/template.md`). Flat subdirs only.
- Subdirectories outside the allowed five (`tools/`, `data/`,
  `cache/`, `output/`, `logs/`, `templates/`). Ephemeral output is the
  workspace's job; persistent runtime data has its home in `state/`.
- Hidden files (`.foo`, `.secret`) and any name outside the filename
  pattern.
- Hardcoded API keys, passwords or tokens in `scripts/`,
  `references/` or `assets/` — the security scanner blocks the write.

Conventions the code does **not** police, so they are on you:

- Every skill lives inside a category directory. A directory placed
  straight under `skills/` is not rejected; it is simply read as a
  category, and what sits inside it is read as a skill.
- No `DESCRIPTION.md` at the category level — category metadata lives
  in this document.
- Credentials belong in the skill's `secrets/`, or in the profile's
  `.env` when they are pre-provisioned and shared.

## Migration from other skill layouts

Skills from other agents usually map cleanly for the simple case
(just `SKILL.md`). For richer ones, reshape:

| Source layout | alpi |
|---|---|
| `skills/<cat>/<name>/SKILL.md` | `~/.alpi/skills/<cat>/<name>/SKILL.md` |
| `skills/<cat>/<name>/scripts/*.py` | `scripts/*.py` (flat, no subdirs) |
| `skills/<cat>/<name>/references/*.md` | `references/*.md` (flat) |
| `skills/<cat>/<name>/templates/<subfolder>/*` | `assets/*` (flatten, prefix filenames if needed) |
| Credentials in random `whoop.json` at skill root | Move to `secrets/` |
| Caches, counters, runtime SQLite at skill root | Move to `state/` |
| `DESCRIPTION.md` at category level | Drop; redundant |

The frontmatter also needs adapting: alpi uses flat fields (`name`,
`description`, `category`, etc.) instead of nested tool-specific
metadata.
