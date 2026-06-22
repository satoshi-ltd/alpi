# Agentic organization

An **organization** is a team of alpi profiles with a focused mission,
its own bootstrap config, and its own workspace. Each profile has a
unique identity, a set of skills, and a place in a reporting structure.
They communicate through ALP workgroups: one agent opens a workgroup,
invites peers, work happens, and the hub agent calls `#done`. No human
orchestration, no calendared rituals — just persistent workgroups where
decisions accumulate.

## One repo, many organizations

Organizations live under `organizations/<name>/` in this repo. Each
folder is one self-contained team — its own agents, workgroups, common
skills, workspace path, and bootstrap data. A single shared
`organizations/setup.py` reads the org's `org.yaml` and does the
mechanical work to instantiate it.

You can run multiple organizations on the same repo. They share no
runtime state, only the codebase. In practice each org lives on its
own machine (so profile namespaces don't collide under
`~/.alpi/profiles/`) and the orgs talk to each other peer-to-peer over
ALP if they need to.

The orgs the repo ships with today are intentional examples — not a
fixed catalogue. Granularise organizations however your structure
demands: one per team, one per product, one per environment, one per
deal flow. The bootstrap pattern is the same.

## Reference orgs that ship today

- [`company/`](../organizations/company/company.md) — the main team
  building the alpi product. 17 profiles across council / execution /
  on-demand layers, 4 standing workgroups. **This document focuses on
  it as the primary worked example.**
- [`web-factory/`](../organizations/web-factory/web-factory.md) — a
  standalone factory producing ~120 hotel websites a year. 11 profiles,
  3 persistent workgroups, plus a persistent `proj-<slug>` workgroup
  per hotel. Shows how an org can carry its own templates, brand starters,
  and per-project bootstrap script alongside the standard pieces.

See [`organizations/README.md`](../organizations/README.md) for the
multi-org pattern, the YAML schema, and how to add a third org.

---

## Canonical reference

`organizations/company/company.md` — full spec for the company org:
agent roster, skills table, workgroup definitions, operating
principles, and the peer graph. The rest of this document drills into
that scaffold.

---

## Structure

The layout is identical for every org:

```
organizations/
  README.md                       # multi-org index
  setup.py                        # unified bootstrap — reads <org>/org.yaml
  <org>/                          # one folder per organization
    <org>.md                      # design contract (roster, workgroups, lifecycle)
    org.yaml                      # bootstrap config — full schema below
    user-memory.md                # USER.md template (placeholders: name, wg_section, peers)
    agents/
      <name>/
        agent.md                  # frontmatter (bio, accent, tier, daily_usd,
                                  #              reasoning_effort, model?,
                                  #              tools_deny?, peers? — legacy)
                                  # body:        soul written to memories/AGENT.md
        skills/<category>/<skill>/SKILL.md
    common/
      skills/<category>/<skill>/SKILL.md   # shared across multiple agents in this org
    workgroups/
      <name>/workgroup.md         # hub, members, budget_usd?, briefing
    (org-specific tools)          # e.g. company/test-workgroup-tasks.py, web-factory/new-project.py
```

### `org.yaml` — full schema

Every key `setup.py` reads, with the default it falls back to:

| Key | Default | Effect |
|---|---|---|
| `display_name` | `<name>` (the folder name) | Human label used in console output during bootstrap. |
| `workspace` | `~/alpi/organizations/<name>/` | Default project root for file/terminal tools across the org's profiles. `~` is honoured verbatim (e.g. the company org sets workspace to `~` so the agents share the user's home as their workspace). Bare YAML `~` parses to `None` and falls back to the default; a literal home string is `"~"`. |
| `workspace_scaffold` | `[]` | List of relative subdir names created inside `workspace` at bootstrap (`projects`, `templates/hotel-web`, etc.). |
| `sync` | `[]` | List of `{src, dst}` entries copied from `organizations/<name>/` into `workspace` every bootstrap (replace mode). Used for shipping templates / libraries with the org. |
| `peer_edges` | `[]` | Permanent peer graph. **Preferred source** — see _Peer graph_ below. Accepts `"all"` (every agent a mutual peer), a list of `[a, b]` pairs, or empty (workgroup membership alone wires the graph). |
| `models.default` | `openai/gpt-5.4-mini` | Model assigned to agents with `tier: default`. |
| `models.strong` | `anthropic/claude-sonnet-4-6` | Model assigned to agents with `tier: strong`. An agent's `agent.md` can override either with an explicit `model:` field. |
| `budgets.daily_default` | `2.0` | USD daily cap for tier-default agents (used when `agent.md` omits `daily_usd`). |
| `budgets.daily_strong` | `5.0` | USD daily cap for tier-strong agents (same fallback rule). |
| `budgets.workgroup` | `50.0` | Default lifetime USD cap for standing workgroups (each `workgroup.md` can override via `budget_usd`). |
| `agent_voices` | `{}` | Map `<agent-name> → Edge TTS voice id` (e.g. `vera: en-US-AriaNeural`). Written into the profile's `tools.tts.voice`. |
| `common_skills` | `{}` | Map `<category>/<skill> → [agent names]` — shared skills under `common/skills/` that bootstrap copies into each named profile's `skills/`. |

### Peer graph — `peer_edges` vs legacy `peers:`

Three sources are **merged into a deduped union** (no precedence at
runtime; pin order is irrelevant — `setup.py::derive_edges` builds the
edge set once):

1. **`org.yaml peer_edges`** — the preferred declaration site for new
   orgs. Declarative, lives next to the rest of the org's configuration.
   `"all"` (complete graph) or `[[a, b], …]`.
2. **`agent.md peers:` frontmatter** — **legacy** back-compat; still
   read so older orgs keep working without rewrite. Treat as deprecated
   for new orgs: peers are network infrastructure, not agent identity.
3. **Workgroup membership** — every `workgroup.md` automatically adds
   hub↔member edges. This source can stand alone — an org with no
   `peer_edges` and no `peers:` still has a working graph through its
   workgroups.

Overlap between the three is harmless; edges are deduped.

### `agent.md` — frontmatter fields

Every `agents/<name>/agent.md` carries a YAML frontmatter block; the
body is the agent's soul (copied verbatim into the profile's
`memories/AGENT.md`).

| Field | Required | Notes |
|---|---|---|
| `reasoning_effort` | **yes** (validation) | `off \| low \| medium \| high`. Validation hard-fails if the field is missing or holds anything else. `False` / `no` / `none` / `disabled` normalise to `off`. The only field required to be present — validation also rejects invalid `tier` values and unknown names in `tools_deny`, but those checks fire only when the field is set. |
| `bio` | no (default `""`) | One-line public tag-line; broadcast to every workgroup the agent joins (truncated to fit ALP's bio limit). Empty = no broadcast. |
| `accent` | no (default `"#888888"`) | CSS color (hex / named / rgb). Drives the TUI accent for the profile. |
| `tier` | no (default `"default"`) | `default` or `strong`. Picks the org's `models.default` / `models.strong` unless overridden by `model:`. Validation rejects any other value. |
| `model` | no | Explicit LiteLLM string that overrides the tier-derived model. |
| `daily_usd` | no | USD daily cap; defaults to `budgets.daily_strong` for tier-strong, `budgets.daily_default` otherwise. |
| `tools_deny` | no (default `[]`) | List of tool names hidden from this profile's LLM schema. Validation rejects unknown names (a typo here is a security gap — the deny silently misses). |
| `peers` | no (default `[]`) | **Legacy.** Per-agent peer list; honoured for back-compat. Prefer `org.yaml peer_edges` for new orgs. |

`workgroup.md` frontmatter uses `hub` (required), `members` (list of
agent names), and optional `budget_usd` (defaults to
`budgets.workgroup`). The body is the briefing, loaded into every
member's context.

The unified `setup.py` consumes all of this and runs the same
mechanical pipeline for every org.

---

## Worked example: the company org

The rest of this document walks through the `company/` org concretely.
The same structure applies to any organization you write — only the
roster, workgroups, and `org.yaml` settings change.

### The 17 agents

Agents are grouped into three layers:

**Council (5)** — strategic; each owns a domain and has standing access
to any workgroup.

| Agent | Role |
|---|---|
| Vera | Chief Strategist |
| Zeta | Chief Architect |
| Prism | Product Manager |
| Echo | Growth Strategist |
| Ledger | Finance |

**Execution (9)** — operational; report to a Council member and do the
work inside their domain.

| Agent | Role | Reports to |
|---|---|---|
| Forge | Senior Engineer | Zeta |
| Sentinel | Quality Engineer | Zeta |
| Canvas | Product Designer | Prism |
| Quill | Content & Copy | Echo |
| Rex | Sales | Echo |
| Fern | Customer Success | Echo |
| Hub | Customer Service | Echo |
| Lumen | Data Analyst | Ledger |
| Flux | Operations | Ledger |

**On-demand (3)** — specialist; no fixed reporting line, invoked when
their domain is in play.

| Agent | Role |
|---|---|
| Lex | Legal Counsel |
| Atlas | Market Intelligence |
| Archive | Knowledge Management |

---

### The 4 workgroups

| Workgroup | Hub | Fixed peers |
|---|---|---|
| Roadmap | Prism | Vera, Zeta, Echo |
| Architecture | Zeta | Forge, Sentinel |
| Growth | Echo | Quill, Rex |
| Customers | Fern | Hub |

Each workgroup has a `briefing` (loaded into every invited peer's
context) and explicit `rules` defining what tasks belong and what
`#done` requires.

---

### Skills

51 skills across all 17 agents. Every skill is self-sufficient: its
state (SQLite or JSONL) lives inside the skill directory, scripts are
co-located, and there are no external service dependencies. The full
table is in the [canonical reference](../organizations/company/company.md#skills).

---

### Bootstrapping

The bootstrap pipeline below applies to **every** org — only the
roster, workgroups, and workspace differ. For the company org:

```bash
uv run python organizations/setup.py company
```

What it does in order:

1. Removes the 17 org profiles from `~/.alpi/profiles/`.
2. Creates each profile fresh (`alpi profile create`).
3. Copies API keys from `organizations/company/.env` (falls back to `~/.alpi/.env`).
4. Writes `memories/AGENT.md` (soul) and `memories/USER.md` (org context from `user-memory.md`).
5. Patches `config.yaml` — model, bio, accent, daily budget, voice, tool denylist, MCP servers, reasoning effort.
6. Installs the daemon (idempotent).
7. Scaffolds the workspace from `org.yaml` (creates dirs, syncs templates/assets if any).
8. Waits for ALP Ed25519 keypairs to be generated.
9. Reads pubkeys and cross-pins the peer graph.
10. Restarts the daemon and verifies every edge responds to ping.
11. Creates the persistent workgroups; members join each.
12. Installs skills into each profile (from `agents/<name>/skills/` plus `common/skills/` per `org.yaml.common_skills`).

The bootstrap is fully idempotent — re-run to rebuild from scratch
after editing agent files, skills, or `org.yaml`. Flags scope the work
for different intents:

- `--check` — validation only (CI-friendly): SKILL.md structure +
  tool-name correctness + `tools_deny`/`reasoning_effort` declarations
  in agent.md. Exits non-zero on hard errors. No filesystem changes.
- `--skills-only` — re-sync SKILL.md files into existing profiles. No
  profile wipe.
- `--workspace-only` — re-sync workspace scaffold + templates/assets
  (useful when iterating on `web-factory/templates/` or
  `web-factory/library/`; no-op for orgs without a synced
  workspace).
- `--no-check` — skip the pre-bootstrap validation gate. Use sparingly,
  only when iterating on tooling itself.
- `--nuke` — destroy all profiles for this org under `~/.alpi/profiles/`.
  Workgroups go with them. No rebuild. Workspace untouched. Skips
  validation (nothing to validate when not building).
- `--nuke --workspace` — same as `--nuke`, plus deletes the workspace
  directory (e.g. `~/git/web-factory/` for the web-factory org, with
  every in-flight project under `projects/`). **Refuses if workspace
  resolves to `~`** (your home directory). Irreversible.

---

### Adapting the company scaffold

**Removing an agent.** Delete its folder under
`organizations/company/agents/`. The bootstrap silently drops all edges
to/from that agent. No other file needs editing.

**Adding an agent.** Create `organizations/company/agents/<name>/agent.md`
with the required frontmatter (`reasoning_effort`; the recommended
identity fields are `bio`, `accent`, `tier`; `model` / `daily_usd` /
`tools_deny` are optional) and a soul in the body. Add it to any
workgroup's `members` list if needed. Network edges are picked up
automatically — declare them via `org.yaml peer_edges` (legacy `peers:`
in `agent.md` still honoured).

**Changing a model.** Edit `tier: strong | default` in the agent's
frontmatter, or override `daily_usd` directly. Per-org model defaults
live in `organizations/company/org.yaml` under `models:`. Vision is **not
a tier** — every agent reasons on a text model; an agent that needs to SEE
calls a per-call vision SKILL (e.g. web-factory's muse → `analyze-image`,
which sends the image to a vision model via OpenRouter), never a vision
base model.

**Adding a common skill.** Drop the skill under
`organizations/company/common/skills/` and add an entry to the
`common_skills:` mapping in `organizations/company/org.yaml` (skill path
→ list of agents that should receive it).

### Adding a new organization

The same scaffold-and-bootstrap pattern grows the system:

1. `mkdir organizations/<name>/`
2. Write `<name>.md` (design contract), `org.yaml` (the file must exist
   and contain a YAML mapping; `{}` is valid — every key falls back to
   the default in the schema above), and `user-memory.md` (USER.md
   template).
3. Populate `agents/` and `workgroups/` following the company layout.
4. `uv run python organizations/setup.py <name>` — `setup.py`
   auto-discovers any subdir of `organizations/` that contains an
   `org.yaml`.

Profile names share the global `~/.alpi/profiles/` namespace, so two
orgs with the same agent name (e.g. `vera`) cannot coexist on one
machine. The intended pattern is one org per machine, with ALP peer
pings handling cross-org communication.

---

## Design principles

- **Specialization beats fusion.** Each agent has a focused soul so its
  responses are sharp. Merging roles dilutes context.
- **The hub owns the workgroup.** One agent creates it, opens tasks,
  invites peers, and decides `#done`. No consensus; clear accountability.
- **Skills are self-sufficient.** State, scripts, and references live
  inside the skill directory. No external MCPs required. The org runs
  offline.
- **Briefings carry context.** New peers do not need mid-conversation
  onboarding — the workgroup briefing does it.
