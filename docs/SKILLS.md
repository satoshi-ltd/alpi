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
description: Fetch daily health metrics from the Whoop API via OAuth
category: personal
version: 0.1.0
origin: agent                   # "agent" (proposed) or "user" (hand-written)
requires_env: []                # env vars the skill needs; missing ones hide it
requires_bins: [gh]             # executables on PATH; missing ones hide the skill
requires_config: []             # profile config keys (dotted); missing ones hide it
platforms: [macos, linux]       # supported OSes; empty/absent = portable
tools: [read_file, terminal]    # tools the skill is allowed to call;
                                # built-ins are snake_case; MCP tools
                                # use the server's native form
                                # (e.g. ``bitbucket__getPullRequests``)
keywords: [whoop, workout]      # optional lowercase tokens for keyword boost
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
system prompt and from `keyword_match_hint`, and surface in
`skill(action='list')` with `[inactive: missing …]`.

The rule across surfaces: **explicit target → hard error; implicit
availability → silent filter**. Calling `skill(action='run' | 'test'
| 'invoke', name=X)` on an inactive skill fails fast with a clear
"missing …" reason. The agent never sees inactive skills in the
prompt or the keyword hint, so it cannot pick them by accident.

#### `requires_env`

Env vars the skill needs. Checked against `os.environ` at
system-prompt build time (the profile's `~/.alpi/.env` is loaded
into the process env at engine bootstrap, so anything there counts).
Missing or empty value → inactive.

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

#### `platforms`

Operating systems the skill supports. One or more of `macos`,
`linux`, `windows`. Empty/absent = portable (no platform check).

```yaml
platforms: [macos, linux]
```

A skill declaring `platforms: [linux]` running on macOS shows up
in `list` as `[inactive: missing platform linux (this is macos)]`.

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
| `~/.alpi/.env` | Pre-provisioned static secrets declared in `requires_env`. User pastes the value in once. | Edited by hand. Shared across skills if they reference the same var. |
| `~/.alpi/skills/<cat>/<name>/secrets/` | Runtime-generated credentials (OAuth access+refresh, session blobs). Per-skill, never shared. | Created lazily when the skill writes a secret. Wiped when the skill is deleted. |

**Never** hardcode secrets inside `SKILL.md`, `scripts/`, `references/`,
or `assets/`. The security scanner rejects the most obvious patterns
(`api_key = "sk-..."`, `password = "..."`). It runs on SKILL.md body
and on every file added via `add_file` to `scripts`, `references`, or
`assets`. The `secrets/` subdir skips the scanner by design (the
whole point is that it holds keys).

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

Backed by `~/.alpi/<profile>/skills/<cat>/<skill>/state/db.sqlite`.
Always parameterised — `params=[…]` binds to `?` placeholders;
never string-interpolate user data into the SQL. Schema is owned
by the skill body — the LLM runs `CREATE TABLE IF NOT EXISTS …`
on first invocation; idempotent.

**Quotas (enforced):**

- 50 MB max file size — prune with `DELETE` or run
  `skill(action='reset_state', name=…)` to nuke and start over.
- 10 000 rows max per `query` result — tighten with `WHERE` /
  `LIMIT`.
- 5 s busy / lock timeout (sqlite-level — query duration is not
  killed mid-flight, but skill DBs are tiny so this hasn't bitten
  in practice).

**Scope:** strictly per-skill. The `skill` argument resolves
against the profile's installed skills; bundled `@alpi/*` skills
cannot use `db` (read-only by design). Backup-friendly: when AW
ships, `db.sqlite` flows through the encrypted archive like any
other file under the skill directory.

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

Inspection / listing:

```
skill(action="list")
skill(action="view",     name=..., [file="scripts/foo.py"])
skill(action="validate", name=...)
```

Mutating (user skills require `confirm_user_skill=true`; bundled
`@alpi/*` rejects every mutation):

```
skill(action="create", name=..., category=..., description=..., body=...,
      [requires_env], [tools], [keywords], [output_schema])
skill(action="edit",        name=..., body=..., [confirm_user_skill])
skill(action="patch",       name=..., subdir=..., filename=...,
                             old_string=..., new_string=...,
                             [confirm_user_skill])
skill(action="set_meta",    name=..., fields={...}, [confirm_user_skill])
skill(action="add_file",    name=..., subdir=..., filename=..., content=...,
                             [confirm_user_skill])
skill(action="remove_file", name=..., subdir=..., filename=...,
                             [confirm_user_skill])
skill(action="delete",      name=..., [confirm_user_skill])
skill(action="reset_state", name=..., [confirm_user_skill])
```

Execution:

```
skill(action="run",    name=..., [args])
skill(action="test",   name=..., [args])
skill(action="invoke", name=..., [args])
```

`delete` archives to `skills/.archive/<category>/<name>__<UTC>/`
(recoverable) instead of removing. Skills with `pinned: true` in
their frontmatter refuse `delete` until unpinned via `set_meta`.
`reset_state` wipes everything under `<skill>/state/` (db.sqlite,
JSONL logs, anything else) but preserves `SKILL.md`, `scripts/`,
`references/`, `assets/`, and `secrets/`. `set_meta` surgically
updates frontmatter (description, category, requires_env, tools,
keywords, output_schema, or `pinned`) without touching the prose
body. `patch` does the inverse: small edits to a file under
`scripts/` / `references/` / `assets/` without rewriting the whole
file.

### Creating a skill

`create` writes **only** `SKILL.md` and goes live immediately under
`~/.alpi/skills/<category>/<name>/`. Subdirectories come later via
`add_file`. A just-created skill has no scripts, no references, no
assets, no secrets. If the skill later writes a file under `secrets/`,
the tool creates that directory mode 0700 automatically.

The agent is capped at 40 agent-created skills total (tweakable via
`MAX_AGENT_SKILLS`). Beyond that, `create` errors and asks the user
to prune with `/skills` first.

### Adding files

```
skill(action="add_file",
      name="whoop-integration",
      subdir="scripts",          # scripts | references | assets | secrets | state
      filename="fetch.py",       # flat, no '/' or '..'
      content="<full file text>")
```

- `scripts/`, `references/`, `assets/` content is scanned for
  dangerous patterns (rm -rf, curl|sh, eval(), hardcoded keys, etc).
- `secrets/` content is not scanned (by design). Files written there
  create the directory mode 0700 and are `chmod 0600`.
- `state/` content is not scanned either — runtime data (SQLite
  blobs, JSONL caches) is the skill's own working memory. Use
  `skill(action="reset_state")` to wipe it.

### Viewing and running skill files

`skill(action="view", name=..., file="scripts/foo.py")` returns the
file content prefixed with `absolute_path: ...`. Use that absolute
path when executing a script. Do not run `scripts/foo.py` relative to
the current workspace; skill files live under the active profile home.

### Running a skill end-to-end

`skill(action="run", name=...)` is the canonical way to execute a
skill from the agent. Two paths:

- **`scripts/run.py` exists** — alpi spawns it with `cwd` = the skill
  directory and an env enriched with `ALPI_HOME`, `ALPI_SKILL_NAME`,
  `ALPI_SKILL_DIR`. Stdout (and stderr, if any) is returned as the
  tool result. Timeout: 600 s. If the skill declares `requires_env:`
  fields and any of those vars are missing from the process env, the
  call fails up-front instead of half-running the script. Scripts are
  normal Python; built-in tools and MCP methods are not importable
  Python APIs. MCP-backed skills should stay prose-only until there is
  an explicit runtime bridge.
- **No script** — alpi returns SKILL.md prefixed with a directive so
  the agent follows the prose and calls the tools it names instead of
  improvising.

Pass `args=["--foo", "bar"]` to forward extra CLI arguments to
`scripts/run.py`. Scheduled jobs should invoke this action from their
prompt when they need a skill result; the scheduler itself still runs
through `alpi chat --once --emit-events --no-save`.

If the skill declares `output_schema:` in frontmatter, it must be a
one-line JSON object using a small JSON Schema subset
(`type`/`properties`/`required`/`items`/`enum`). `skill(run)` validates
**stdout** against that schema; invalid JSON or a shape mismatch fails
the call.

The agent should prefer `skill(action="run")` over manually chaining
`view` + `terminal` calls. For scripted skills, `run` owns the script
execution. For prose-only skills, `run` loads the instructions and the
agent executes them with the real tools.

### Testing a scripted skill

`skill(action="test", name=...)` is the minimal harness for scripted
skills. It runs `scripts/run.py` through the same runtime path as
`skill(run)` and, when `output_schema:` is declared, checks that stdout
matches it. Prose-only skills do not support `test`; exercise those in
chat by running the real tools they mention.

### Invoking one skill from another flow

`skill(action="invoke", name=...)` is the strict composition surface.
Use it when another skill or agent step needs a machine-readable result
from a sub-skill. Unlike `run`, `invoke` only accepts scripted skills
that declare `output_schema:`. That keeps composition explicit: the
callee must return JSON and the caller can trust the contract.

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
- Extensions outside the allowed 5 (`tools/`, `data/`, `cache/`,
  `output/`, `logs/`, `templates/` at the skill root). Ephemeral
  output is the workspace's job, not the skill's — and persistent
  runtime data already has its home in `state/`.
- Credentials anywhere outside `secrets/` (or `~/.alpi/.env` for
  pre-provisioned ones).
- Files in `scripts/` / `references/` / `assets/` that contain
  hardcoded API keys, passwords, or tokens. Security scanner blocks.
- Hidden files (`.foo`, `.secret`). Rejected by the filename regex.

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
