---
name: knowledge
description: ALWAYS load this skill when the user mentions alpi (the Python agent project, NOT a generic assistant). Read the bundled docs FIRST — never answer from training; alpi shipped after your cutoff.
category: meta
version: 0.1.0
origin: bundled
tools: [skill]
---

# alpi:knowledge

You are answering a question about **alpi itself** — how to use it,
how it's configured, how the protocol works, how to deploy it,
where things live, what the security model is, what changed in a
specific version. This skill bundles alpi's user-facing
documentation so you can answer **without** a `web_search`
round-trip and without guessing from your training data (which
predates alpi).

## How to use this skill

1. Decide which reference matches the user's question (the
   routing table below maps topics to files).
2. Read the file with:
   ```
   skill(action="view", name="@alpi/knowledge",
         file="references/<filename>.md")
   ```
3. Read more than one file when the question crosses topics
   (e.g. "how do I install alpi on a Linux server with the
   schedule daemon?" spans `install.md` + `deployments.md`).
4. Synthesize a concise answer. **Quote the relevant fragment**
   when it's short; **summarize and link** when it's long. Do
   not invent details that aren't in the bundled docs.

If the question genuinely isn't covered (e.g. troubleshooting a
specific stack trace, asking about a third-party library), say so
plainly and only then fall back to `web_search` or general
reasoning.

## Routing table — topic → file

| If the user asks about… | Read |
|---|---|
| What alpi is, the project pitch, common commands | `readme.md` |
| First-time setup walkthrough, install + first message | `quickstart.md` |
| Install methods (`uv tool`, `pipx`, dev install), update path, uninstall, troubleshooting, supported platforms | `install.md` |
| Profiles (creating, switching, isolation, identity, keys, memory layout) | `profiles.md` |
| Skills system: bundled vs user, frontmatter, security scanner, where credentials live, the `skill` tool actions | `skills.md` |
| Models — picking a provider, tier guidance for tool-heavy use, local Ollama setup | `models.md` |
| ALP protocol — pinned identity, signed envelopes, peer capabilities, workgroups, group keys, transcript shape, error codes | `alp.md` |
| Internals — code structure, turn loop, gateway, scheduler, MCP, logging, env vars (`ALPI_HOME`, `ALPI_PROFILE`, `ALPI_SKIP_UPDATE_CHECK`, `ALPI_UPDATE_INDEX`) | `architecture.md` |
| Config knobs — every YAML field, its default, what it controls (TUI theme, sandbox, budget, gateway, schedule…) | `config.md` |
| Security model — approval system, SSRF, prompt-injection, sensitive-path denylist, sandbox | `security.md` |
| Deployment — launchd on macOS, systemd on Linux, gateway/schedule daemon shape, keep-alive, log paths | `deployments.md` |
| Day-2 ops — doctor, diagnostics, log rotation, backup, recovery, upgrade workflow | `operations.md` |

## When NOT to use this skill

- Questions about generic Python, the user's own codebase, or
  third-party services (OpenAI, Anthropic, Telegram API, Ollama
  internals). Those go to `web_search` or normal reasoning.
- Questions about the **roadmap** or unreleased features. The
  bundled references only cover what shipped — the roadmap file
  is intentionally NOT bundled because it's planning, not
  knowledge. Say so plainly if asked.
- Questions about **what changed in a specific version** or
  "what's the latest version?". The CHANGELOG is intentionally
  NOT bundled because it stales every release. Point the user at:
  - `alpi --version` for the version they have installed.
  - `alpi update --check` for whether a newer one exists.
  - The GitHub releases page
    (`https://github.com/satoshi-ltd/alpi/releases`) for full
    release notes.
- Operational status of the user's own setup (what their config
  currently is, whether their service is running). That's
  `alpi doctor` and `read_file` against their config.

## Tone

Answer in the user's language. Be concrete: cite the doc you
read, quote the relevant snippet, give the exact command if one
applies. Never make up flag names, paths, or behaviours that
aren't in the references.
