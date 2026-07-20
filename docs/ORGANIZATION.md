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

- [`web-factory/`](../organizations/web-factory/README.md) — a
  standalone factory producing ~120 hotel websites a year. 11 profiles,
  3 standing workgroups, plus a persistent `proj-<slug>` workgroup per
  hotel. Carries its own brand starters, factory contract, and a launch
  recipe alongside the standard pieces. **This document
  focuses on it as the primary worked example.**
- [`lab/`](../organizations/lab/README.md) — the minimal ALP protocol
  testbed: 4 profiles, 1 workgroup, deterministic harnesses that verify
  every workgroup invariant.

See [`organizations/README.md`](../organizations/README.md) for the
multi-org pattern, the YAML schema, and how to add a third org.

---

## Canonical reference

`organizations/web-factory/README.md` — full spec for the
web-factory org: agent roster, workgroups, producer contract, and the
per-project pipeline. The rest of this document drills into that
scaffold.

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
        agent.md                  # frontmatter (bio, accent, daily_usd,
                                  #              reasoning_effort, model?,
                                  #              model_fast?, model_deep?,
                                  #              tools_deny?, peers? — legacy)
                                  # body:        soul written to memories/AGENT.md
        skills/<category>/<skill>/SKILL.md
    common/
      skills/<category>/<skill>/SKILL.md   # shared across multiple agents in this org
    workgroups/
      <name>/workgroup.md         # hub, members, budget_usd?, briefing
    (org-specific tools)          # e.g. web-factory/recipes/hotel.yaml, lab/test-protocol.py
```

### `org.yaml` — full schema

Every key `setup.py` reads, with the default it falls back to:

| Key | Default | Effect |
|---|---|---|
| `display_name` | `<name>` (the folder name) | Human label used in console output during bootstrap. |
| `workspace` | `~/alpi/organizations/<name>/` | Default project root for file/terminal tools across the org's profiles. `~` is honoured verbatim (an org may set workspace to `~` so agents share the user's home). Bare YAML `~` parses to `None` and falls back to the default; a literal home string is `"~"`. |
| `workspace_scaffold` | `[]` | List of relative subdir names created inside `workspace` at bootstrap (`projects`, `archive`, etc.). |
| `sync` | `[]` | List of `{src, dst}` entries copied from `organizations/<name>/` into `workspace` every bootstrap (replace mode). Used for shipping templates / libraries with the org. |
| `peer_edges` | `[]` | Permanent peer graph. **Preferred source** — see _Peer graph_ below. Accepts `"all"` (every agent a mutual peer), a list of `[a, b]` pairs, or empty (workgroup membership alone wires the graph). |
| `models.main` | `{model: openai/gpt-5.6-terra, effort: medium}` | Turn model written to every profile's `config.yaml model`. `effort` is **required** (`low \| medium \| high`) — the org-wide reasoning default every agent inherits unless its `agent.md` declares `reasoning_effort`. |
| `models.fast` | `{model: openai/gpt-5.6-terra, effort: low}` | Written to every profile's `tiers.fast` — serves `delegate`/`research` fast paths and engine plumbing (compaction, memory review). String or `{model, effort}` map; effort must be `low \| medium \| high` or omitted. |
| `models.deep` | `{model: anthropic/claude-sonnet-5, effort: high}` | Written to every profile's `tiers.deep` — the engine's automatic escalation target (after repeated tool failures / empty replies) and the `delegate`/`research` deep option. Same shape as `fast`. The old `models.default` / `models.strong` keys are a hard bootstrap error. |
| `budgets.daily_default` | `2.0` | USD daily cap used when `agent.md` omits `daily_usd`. |
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
| `reasoning_effort` | no (default: org `models.main.effort`) | `off \| low \| medium \| high`. Declare it only where the agent's identity deviates from the org default (a low-effort mechanical role, a high-effort hub, a deliberate `off`). `False` / `no` / `none` / `disabled` normalise to `off`; any other value hard-fails validation, as do unknown names in `tools_deny` and any leftover `tier:` field. |
| `bio` | no (default `""`) | One-line public tag-line; broadcast to every workgroup the agent joins (truncated to fit ALP's bio limit). Empty = no broadcast. |
| `accent` | no (default `"#888888"`) | CSS color (hex / named / rgb). Drives the TUI accent for the profile. |
| `model` | no | Explicit LiteLLM string that overrides the org's `models.main` for this profile only. |
| `model_fast` | no | Per-profile model override for the `fast` routing tier (the org tier's `effort` is kept). |
| `model_deep` | no | Per-profile model override for the `deep` routing tier (same rule). |
| `tier` | removed | Legacy `default`/`strong` selector — now a hard validation error; use `model` / `model_fast` / `model_deep`. |
| `daily_usd` | no | USD daily cap; defaults to `budgets.daily_default`. |
| `tools_deny` | no (default `[]`) | List of tool names hidden from this profile's LLM schema. Validation rejects unknown names (a typo here is a security gap — the deny silently misses). |
| `peers` | no (default `[]`) | **Legacy.** Per-agent peer list; honoured for back-compat. Prefer `org.yaml peer_edges` for new orgs. |

`workgroup.md` frontmatter uses `hub` (required), `members` (list of
agent names), and optional `budget_usd` (defaults to
`budgets.workgroup`). The body is the briefing, loaded into every
member's context.

The unified `setup.py` consumes all of this and runs the same
mechanical pipeline for every org.

---

## Worked example: the web-factory org

The rest of this document walks through the `web-factory/` org concretely.
The same structure applies to any organization you write — only the
roster, workgroups, and `org.yaml` settings change.

### The 11 agents

One strategic lead (vera), one project-manager hub (mira), one tech
lead (forge), one brand steward (canvas), and seven producers (scout,
quill, lingua, muse, pixel, atlas, lens) — one owner per pipeline
phase. The full roster with reasoning tiers and souls lives in the
[canonical reference](../organizations/web-factory/README.md).

---

### The workgroups

| Workgroup | Hub | Fixed peers |
|---|---|---|
| brand-library | canvas | scout, quill, lingua |
| quality | vera | mira, lens, atlas |
| template | forge | canvas, atlas, lingua, lens |
| `proj-<slug>` (one per hotel) | mira | scout, quill, lingua, muse, pixel, lens |

The three standing workgroups carry meta-work (brand starters, the
launch checklist, the master template). Each hotel gets a persistent
`proj-<slug>` pipeline workgroup launched from
`organizations/web-factory/recipes/hotel.yaml`, with a briefing carrying
project facts + the phase map only.

---

### Skills

Each agent ships its own skills under `agents/<name>/skills/`
(intake rubric, voice/tone, image analysis/generation, build gates,
lifecycle/maintenance procedures…). Every skill is self-sufficient:
state lives inside the skill directory, scripts are co-located, no
external service dependencies.

---

### Bootstrapping

The bootstrap pipeline below applies to **every** org — only the
roster, workgroups, and workspace differ. For the web-factory org:

```bash
uv run python organizations/setup.py web-factory
```

What it does in order:

1. Removes the 11 org profiles from `~/.alpi/profiles/`.
2. Creates each profile fresh (`alpi profile create`).
3. Copies API keys from `organizations/web-factory/.env` (falls back to `~/.alpi/.env`).
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
  (useful when iterating on `web-factory/library/`; no-op for orgs
  without a synced workspace).
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

### Adapting the scaffold

**Removing an agent.** Delete its folder under
`organizations/web-factory/agents/`. The bootstrap silently drops all edges
to/from that agent. No other file needs editing.

**Adding an agent.** Create `organizations/web-factory/agents/<name>/agent.md`
with the identity frontmatter (`bio`, `accent`; `model` / `model_fast` /
`model_deep` / `reasoning_effort` / `daily_usd` / `tools_deny` are
optional overrides of org policy) and a soul in the body. Add it to
any workgroup's `members` list if needed. Network edges are picked up
automatically — declare them via `org.yaml peer_edges` (legacy `peers:`
in `agent.md` still honoured).

**Changing a model.** The org's `models:` palette (`main` / `fast` /
`deep`) in `org.yaml` is what every profile gets; override a single
profile with `model:` (main) or `model_fast:` / `model_deep:` (routing
tiers) in its frontmatter. Escalate one profile at a time, on evidence —
never the whole org. Vision is **not a tier** — every agent reasons on a
text model; an agent that needs to SEE calls a per-call vision SKILL
(e.g. web-factory's muse → `analyze-image`, which sends the image to a
vision model via OpenRouter), never a vision base model.

**Adding a common skill.** Drop the skill under
`organizations/<org>/common/skills/` and add an entry to the
`common_skills:` mapping in `organizations/<org>/org.yaml` (skill path
→ list of agents that should receive it).

### Adding a new organization

The same scaffold-and-bootstrap pattern grows the system:

1. `mkdir organizations/<name>/`
2. Write `<name>.md` (design contract), `org.yaml` (the file must exist
   and contain a YAML mapping; `{}` is valid — every key falls back to
   the default in the schema above), and `user-memory.md` (USER.md
   template).
3. Populate `agents/` and `workgroups/` following the web-factory layout.
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
