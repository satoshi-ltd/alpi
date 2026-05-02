# AGENTS.md

Rules for any AI agent (Claude Code, Cursor, Codex, Aider, etc.)
working on this repository. These are not suggestions — they are
hard constraints the project owner has set explicitly.

## Project

- **Name:** Alpi. Package `alpi`, binary `alpi`, home directory
  `~/.alpi`. Open-source, solo-maintained.
- **Positioning:** "a lighter, better Hermes." Hermes
  (`~/git/hermes-agent` on Javi's machine) is the canonical
  reference codebase. Before designing a non-trivial feature, look
  there first — but evaluate critically, since Hermes is
  feature-rich for a broad audience while alpi is scoped tight.
  The bar is "the smallest design that captures the value", not
  "port verbatim".

## Code style

- **Comments rule (HARD).** Two laws, no exceptions:
  1. Comments are **not for humans** — they exist only to give an
     LLM context it cannot recover from the code itself.
  2. **One line, preferably.** Multi-line comments are forbidden
     unless a single line cannot carry the load-bearing *why*
     (concrete external bug, library quirk, protocol invariant).
  Narrative, banner, decorative, "explains what the code does",
  paragraph-style commentary, and section-divider blocks are token
  tax — delete on sight. When in doubt, delete. Applies to the
  whole `alpi/` tree and the desktop sources. Tests and docs are
  out of scope (those are read by humans).
- **All source text in English.** No Spanish anywhere in `alpi/`
  — code, docstrings, prompts, tool descriptions, CLI help, error
  messages, commit messages. Only runtime user-facing output (which
  naturally follows the user's language) is exempt. Examples in
  tool descriptions bias the LLM's reply language; English keeps
  it neutral.
- **Plain JavaScript only — no TypeScript.** Frontend code is
  always `.js` / `.jsx`. Do not propose adding TS "later" or
  scaffold projects with TypeScript templates.
- **Minimize dependencies.** Every runtime or build dep needs
  explicit justification. Defaults: CSS Modules over Tailwind,
  hand-rolled over UI kits, vanilla over opinionated state
  libraries. The project is solo-maintained — every dep is
  maintenance tax forever.

## Workflow

- **Always test what you ship.** Every functional change ships
  with a test. Run `pytest -q` (or the targeted module) before
  declaring done. Don't rely on reading the diff. Don't hide
  failures behind `@pytest.mark.skip` or `@pytest.mark.integration`
  to silence them — markers are load-bearing decisions, only for
  tests that genuinely need real sockets / sandboxes / external
  processes. Comment-only or pure-rename changes are exempt.
  GitHub CI is a backstop, not a substitute — internal CI is the
  agent's job.
- **Never commit without explicit permission.** No `git commit`,
  `git push`, `git tag`, or any ref-mutating op unless the user
  asked in the current turn. Even when a task looks "done", a
  proactive commit strips the user's review window.
- **Don't auto-bump the version.** Don't change `pyproject.toml`
  or `alpi/__init__.py` versions on commits. Version bumps mark
  *releases*, not iterations — a long branch may take many commits
  before being release-worthy. Bump only when the user asks.
- **No Claude / Anthropic mentions in the repo.** Hard rule. No
  "Claude Code", "Co-Authored-By: Claude", "🤖 Generated with…"
  in code, commit messages, PR descriptions, or docs.

## Architecture

- **The desktop / mobile client talks to the daemon, not the
  filesystem.** Verbs in the `host.*` namespace (in `alpi/host/`)
  are served over `~/.alpi/host/host.sock` (Unix socket, 0600 +
  same user is the trust boundary; no Noise, no pairing). When
  adding a new desktop feature, add a `host.*` verb — never read
  `~/.alpi/` directly from Rust, never spawn `alpi` as a
  subprocess. ALP (`alpi/alp/`) is a separate plane for
  cross-machine peer-to-peer (`link.*`, `workgroup.*`) and is not
  what the client calls.

## Testing

```bash
pytest -q                # fast suite (unit + filesystem)
pytest --integration -q  # adds tests that open sockets / use sandbox-exec
pytest --llm             # adds tests that make real LLM calls
```

The repo's CI (`.github/workflows/test.yml`) runs both `fast` and
`integration` jobs on every push and PR.
