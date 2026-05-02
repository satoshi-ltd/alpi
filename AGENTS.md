# AGENTS.md

Rules for any AI agent (Claude Code, Cursor, Codex, Aider, …) working on
this repository. Hard constraints, not suggestions.

> Behavioural rules the maintainer applies to every project (commit
> hygiene, test discipline, comment style, no AI-attribution lines) live
> in his personal agent config. They apply here too. If your harness
> doesn't load that file, the short version is: **no commits / pushes /
> tags without explicit permission in the current turn; every functional
> change ships with a test; default to no comments — when needed, one-line
> and aimed at the next LLM, not at humans.**

## Project

- **Name:** Alpi. Package `alpi`, binary `alpi`, home directory `~/.alpi`.
  Open-source, solo-maintained.
- **Positioning:** "a lighter, better Hermes." Hermes
  (`~/git/hermes-agent` on the maintainer's machine) is the canonical
  reference codebase. Before designing a non-trivial feature, look there
  first — but evaluate critically: Hermes is feature-rich for a broad
  audience while Alpi is scoped tight. The bar is "the smallest design
  that captures the value", not "port verbatim".

## Code style

- **All source text in English.** No Spanish anywhere in `alpi/` — code,
  docstrings, prompts, tool descriptions, CLI help, error messages,
  commit messages. Only runtime user-facing output (which follows the
  user's language) is exempt. Examples in tool descriptions bias the
  LLM's reply language; English keeps it neutral.
- **Plain JavaScript only — no TypeScript.** Frontend is always `.js` /
  `.jsx`. Do not propose adding TS "later" or scaffold projects with TS
  templates.
- **Minimize dependencies.** Every runtime or build dep needs explicit
  justification. Defaults: CSS Modules over Tailwind, hand-rolled over UI
  kits, vanilla over opinionated state libraries. Solo-maintained — every
  dep is maintenance tax forever.
- **No Claude / Anthropic mentions in the repo.** Hard rule across code,
  commit messages, PRs, docs.

## Releases & versioning

Two products ship from this repo, on independent cadences with
independent version schemes. Don't conflate them.

- **alpi (CLI / Python package).** Tags ``vX.Y.Z`` (no prefix).
  Versioned in ``pyproject.toml`` + ``alpi/__init__.py``.
  Changelog: [CHANGELOG.md](CHANGELOG.md). Pipeline:
  [.github/workflows/publish.yml](.github/workflows/publish.yml)
  (PyPI + GitHub release).
- **Desktop app (Tauri).** Tags ``desktop-vX.Y.Z``. Versioned in
  ``desktop/package.json`` + ``desktop/src-tauri/tauri.conf.json``
  (both must agree, or the release workflow aborts). Changelog:
  [desktop/CHANGELOG.md](desktop/CHANGELOG.md). Pipeline:
  [.github/workflows/desktop-release.yml](.github/workflows/desktop-release.yml)
  (GitHub release only — no PyPI). The Tauri updater reads
  ``releases/download/desktop-latest/latest.json``; the workflow
  re-points the rolling ``desktop-latest`` tag on every release
  so that URL stays stable.

A desktop release pins a minimum compatible alpi version in its
changelog entry — clients require a daemon recent enough to serve
every ``host.*`` verb the UI calls.

## Architecture

- **The desktop / mobile client talks to the daemon, not the filesystem.**
  Verbs in the `host.*` namespace (in `alpi/host/`) are served over
  `~/.alpi/host/host.sock` (Unix socket, 0600 + same-user trust boundary;
  no Noise, no pairing). When adding a desktop feature, add a `host.*`
  verb — never read `~/.alpi/` directly from Rust, never spawn `alpi` as
  a subprocess. ALP (`alpi/alp/`) is a separate plane for cross-machine
  peer-to-peer (`link.*`, `workgroup.*`) and is **not** what the client
  calls.

## Testing

```bash
pytest -q                # fast suite (unit + filesystem)
pytest --integration -q  # adds tests that open sockets / use sandbox-exec
pytest --llm             # adds tests that make real LLM calls
```

CI (`.github/workflows/test.yml`) runs `fast` and `integration` jobs on
every push and PR — backstop only, not a substitute for running the suite
locally before declaring done.
