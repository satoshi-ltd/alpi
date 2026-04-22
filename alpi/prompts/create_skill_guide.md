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
4. **Secrets**: never write API keys, tokens, or passwords into `SKILL.md`.
   Declare them via `requires_env: [VAR_A, VAR_B]`. The user sets the
   values in `~/.alpi/.env`.
5. **Tools**: list the tools the skill is allowed to call. Keep it minimal.

## Before creating

- Search `~/.alpi/skills/` and the bundled `alpi/skills/` for an existing
  skill that already covers ≥80% of the need. If one exists, propose
  extending it instead of creating a duplicate.

## After creating

- Report the final path and the frontmatter. Tell the user which env vars
  they need to add to `~/.alpi/.env` before the skill can run.

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
