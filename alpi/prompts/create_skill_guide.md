# Creating a skill

Invoke the `create_skill` tool only when the user explicitly asks for a
skill. Never create one proactively.

## Rules the tool enforces (don't fight them)

1. **Name**: kebab-case, 2–60 chars, starts with a letter. E.g.
   `telegram-notifier`, `github-pr-review`. No spaces, no emojis.
2. **Category**: must be exactly one of this closed list — do not invent new
   ones:
   - `software`    (code, git, devops, CI/CD)
   - `data`        (analysis, ML, viz)
   - `research`    (web research, summarization)
   - `productivity` (notes, todos, email, calendar)
   - `communication` (Telegram, WhatsApp, Slack, SMS)
   - `media`       (images, audio, video, diagrams)
   - `system`      (smart-home, self-hosted, infra)
   - `finance`     (Bitcoin, accounts, investments)
   - `personal`    (family, health, logistics)
   - `creative`    (writing, art, generation)
   - `security`    (red-team, audits, pentesting)
   - `meta`        (skills about skills; agent self-improvement)
3. **Description**: one line, ≤150 chars, starts with a verb ("Send…",
   "Fetch…", "Generate…"). This is the line used to match future tasks to
   this skill, so be specific.
4. **Secrets**: never write API keys, tokens, or passwords into
   `SKILL.md`, `scripts/`, `references/`, `assets/`, or the skill root.
   Use the right store:
   - shared/static profile secrets → `requires_env: [VAR_A, VAR_B]`;
     the user sets values in `~/.alpi/.env`;
   - per-skill credential files or runtime auth state (OAuth client
     files, access/refresh tokens, cookies, sessions) →
     `<skill>/secrets/`.
   `secrets/` must be mode `0700`; files containing credentials should
   be mode `0600`.
5. **Tools**: list the tools the skill is allowed to call. Keep it minimal.

## Before creating

- Search `~/.alpi/skills/` for an existing skill that already covers
  ≥80% of the need. If one exists, propose extending it instead of
  creating a duplicate.

## Persistent state — pick the right format

Three formats, three different jobs. Pick by **how the data will
be read**, not by what feels modern:

| Use this | When |
|---|---|
| **Markdown** in `references/<topic>.md` | Human-glanceable list / table, < 50 entries, edits rare. The user might peek by hand. |
| **`state/foo.json`** | One config-like blob or short list. Full-replace on write. No querying. |
| **`state/log.jsonl`** | Append-only event log. One JSON object per line. No schema, no queries — `tail`/grep is enough. |
| **SQLite via `db` tool** | Rows you'll filter / sort / aggregate. Hundreds+ entries. Scripts AND the LLM both touch it. Transactions matter. |

**Decision rules** (apply top-down, first match wins):

1. Will it grow past ~50 rows in normal use? → **SQLite**.
2. Do I need `WHERE` / `ORDER BY` / `GROUP BY` / `COUNT` to read it usefully? → **SQLite**.
3. Is it one settings-like object? → **JSON**.
4. Is it append-only events with no query needs? → **JSONL**.
5. Is it a list / table the user wants to glance at and maybe edit? → **Markdown**.

If torn between Markdown and SQLite — start Markdown. Migrating
Markdown → SQLite later is a 10-line script (parse + `INSERT`).
Migrating SQLite → Markdown is a sign SQLite was overkill from
day one.

**Using the `db` tool** when you do pick SQLite:

```
db(action="exec",  skill="<this-skill>", sql="CREATE TABLE IF NOT EXISTS …")
db(action="exec",  skill="<this-skill>", sql="INSERT …", params=[…])
db(action="query", skill="<this-skill>", sql="SELECT …")
```

The DB lands at `<skill>/state/db.sqlite`. Schema is owned by the
skill body — call `CREATE TABLE IF NOT EXISTS …` idempotently on
first use. Use parameterised SQL via `params=[…]`; never
string-interpolate user data into the statement.

## Scripts

When a skill includes scripts under `scripts/`:

- Prefer stdlib. Every non-stdlib import is a deployment dependency the
  user will have to install — justify each one.
- **Reading env vars.** Use `os.getenv("VAR_NAME")` directly. The
  runtime loads `~/.alpi/.env` into the engine's environment and
  forwards every name declared in `requires_env` to your subprocess.
  Do NOT call `load_dotenv()` from your script and do NOT read
  `~/.alpi/.env` yourself — both are redundant and `load_dotenv` is
  not guaranteed to be installed.
- **Reading skill-owned files.** Use `Path(__file__).parent.parent`
  to resolve `secrets/`, `state/`, `references/`, `assets/` relative
  to the script. Never hardcode `~/.alpi/...`.
- **Writing secrets.** Create `secrets/` with `mkdir(mode=0o700,
  exist_ok=True)` and then call `chmod(0o700)` because `mkdir` does not
  fix an existing directory's mode. For the credential files themselves,
  prefer `from alpi.secrets_io import safe_write_secret` (uses
  `tempfile.mkstemp` + `os.replace` — no TOCTOU window, immune to a
  stale `<target>.tmp` at looser perms). If the skill runs outside the
  alpi venv (e.g. a `no_agent` cron under system python), inline-copy
  the helper instead of `write_text(...)` + `chmod(0o600)`: the two-
  syscall pattern leaves the file briefly at umask perms (typically
  0o644) before being tightened.
- Include a dry-run / smoke-test path (e.g. `--dry-run` flag, or a
  `--help` branch that works without side effects). Mention the exact
  command in SKILL.md so the user (or a future agent) can verify the
  script runs at all.
- Use explicit exit codes: `0` on success, non-zero on failure. Clear
  error messages to stderr.

## After creating / editing

Every `create`, `edit`, `patch`, `add_file`, and `remove_file` call
auto-validates the skill's Python scripts (syntax, imports, OAuth race,
port coherence) and returns any findings in the tool output. If the
output contains `validation:` lines, fix them in the same turn with
another `patch` / `add_file` before telling the user you are done.

- Report the final path and the frontmatter. Tell the user which env vars
  they need to add to `~/.alpi/.env`, and which per-skill credential
  files they need to create under `secrets/`, before the skill can run.

## External services (MCPs)

If the skill needs an external service (GitHub, Notion, a database,
a SaaS API), first check whether an MCP server exists for it (search
the Anthropic registry or common names like
`@modelcontextprotocol/server-<name>`, `mcp-server-<name>`). If one
does:

1. Document it as a **Prerequisite** at the top of SKILL.md — not as
   a step the skill performs. Example:

       ## Prerequisites
       - `github` MCP server configured in `config.yaml`
         (see `alpi setup → MCPs`). Needs `GITHUB_TOKEN` in `.env`.

2. In the skill body, assume the MCP's tools are already registered
   (`github:create_issue`, etc.) and invoke them directly.

Skills REFERENCE MCPs; they never install or configure them. The user
adds MCPs once via `alpi setup → MCPs`; skills use them afterwards.
