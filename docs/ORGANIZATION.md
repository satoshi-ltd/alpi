# Agentic organization

An **agentic organization** is a team of alpi profiles, each with a
focused identity, a set of skills, and a place in a reporting structure.
They communicate through ALP workgroups: one agent opens a workgroup,
invites peers, work happens, and the hub agent calls `#done`. No human
orchestration, no calendared rituals — just persistent workgroups where
decisions accumulate.

This document describes the reference scaffold under `organization/`.
The scaffold is a 17-agent company you can instantiate on any machine
with a single command. Use it as-is or strip it down to the roles you
actually need.

---

## Canonical reference

`organization/agent-organization.md` — full spec: agent roster, skills
table, workgroup definitions, operating principles, and the peer graph.

---

## Structure

```
organization/
  agent-organization.md       # canonical reference (start here)
  setup.py                    # bootstrap script — one run builds the org
  agents/
    <name>/
      agent.md                # frontmatter: bio, peers, tier, daily_usd
                              # body:        soul written to memories/AGENT.md
      skills/<category>/<skill>/SKILL.md
  common/
    skills/<category>/<skill>/SKILL.md   # shared across multiple agents
  workgroups/
    <name>/workgroup.md       # hub, members, budget, briefing
```

---

## The 17 agents

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

## The 4 workgroups

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

## Skills

51 skills across all 17 agents. Every skill is self-sufficient: its
state (SQLite or JSONL) lives inside the skill directory, scripts are
co-located, and there are no external service dependencies. The full
table is in the [canonical reference](../organization/agent-organization.md#skills).

---

## Bootstrapping

```bash
uv run python organization/setup.py
```

What it does in order:

1. Removes the 17 org profiles from `~/.alpi/profiles/`.
2. Creates each profile fresh (`alpi profile create`).
3. Copies API keys from `organization/.env` (falls back to `~/.alpi/.env`).
4. Writes `memories/AGENT.md` (soul) and `memories/USER.md` (org context).
5. Patches `config.yaml` — model, bio, accent, daily budget, MCP servers.
6. Installs the daemon (idempotent).
7. Waits for ALP Ed25519 keypairs to be generated.
8. Reads pubkeys and cross-pins the peer graph.
9. Restarts the daemon and verifies every edge responds to ping.
10. Creates the 4 standing workgroups; members join each.
11. Installs skills into each profile.

The bootstrap is fully idempotent — run it again to rebuild from scratch
after editing agent files or skills.

---

## Adapting the scaffold

**Removing an agent.** Delete its folder under `organization/agents/`.
The bootstrap silently drops all edges to/from that agent. No other
file needs editing.

**Adding an agent.** Create `organization/agents/<name>/agent.md` with
the required frontmatter (`bio`, `peers`, `tier`) and a soul in the
body. Add it to any workgroup's `members` list if needed.

**Changing a model.** Edit `tier: strong | default` in the agent's
frontmatter, or override `daily_usd` directly. The two model constants
at the top of `setup.py` control the defaults for each tier.

**Adding a common skill.** Drop the skill under `organization/common/skills/`
and add an entry to the `COMMON_SKILLS` dict in `setup.py` mapping the
skill path to the list of agents that should receive it.

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
