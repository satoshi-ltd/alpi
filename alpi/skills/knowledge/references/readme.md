# alpi answer pack

Use this file for "what is alpi?", "what can it do?", and "how is it
different from a generic assistant?"

## Short answer

alpi is a profile-based personal AI agent for the terminal, messaging
gateways, and private peer-to-peer agent networks. It keeps persistent
memory, can use tools, can build reusable skills, and can run as a
local service for Telegram/IMAP/Gmail-style inbound messages.

## Positioning

- Package: `alpi-agent`.
- Import path, binary, and home directory: `alpi`, `alpi`, `~/.alpi`.
- Goal: a lighter, tighter personal-agent system.
- Main surfaces: TUI/CLI, gateway service, scheduler, ALP peer links,
  tools, memory, and skills.

## Common commands

```bash
alpi setup
alpi
alpi -p work
alpi doctor
alpi service start
alpi service stop
alpi update --check
alpi --version
```

## Core concepts

- **Profile**: isolated config, memory, sessions, skills, ALP identity,
  logs, and service state.
- **Workspace**: default root for project-relative file tools and
  terminal commands.
- **Memory**: persistent user/project facts, written through the
  `memory` tool.
- **Skills**: reusable workflows stored under `~/.alpi/skills/...`;
  bundled skills use `@alpi/<name>`.
- **Gateway**: background service that lets messages enter from
  platforms such as Telegram or email.
- **Schedule**: recurring jobs that run through the same agent loop.
- **ALP**: Alpi Link Protocol for trusted alpi-to-alpi communication.

## What ships today

- Tool-calling agent loop through LiteLLM-compatible providers.
- TUI and slash commands.
- Profile isolation.
- File, terminal, browser/search, memory, schedule, research, and
  delegate tools.
- Bundled `@alpi/knowledge` skill.
- Optional OS sandbox for terminal/file isolation.
- Gateway and scheduler service.
- ALP identity and peer/workgroup features.

## Boundaries

- alpi is not a hosted SaaS.
- alpi is not a browser-only assistant.
- alpi does not make weak models reliable; tool discipline still
  depends on model quality.
- The bundled knowledge references describe shipped behavior, not the
  unreleased roadmap.

## Where to look next

- First setup: `quickstart.md`
- Install/update/uninstall: `install.md`
- Config fields: `config.md`
- Profiles: `profiles.md`
- Skills: `skills.md`
- Security: `security.md`
- Operations: `operations.md`
