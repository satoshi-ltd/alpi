# Organizations answer pack

## Answer directly

- An **org** is a self-contained team of alpi profiles under `organizations/<name>/`.
- Bootstrap is mechanical: `uv run python organizations/setup.py <name>` reads `<name>/org.yaml`, rebuilds profiles and workgroups, then creates scaffold directories and mirrors configured sync destinations into the workspace.
- The runtime sees only the union of profiles under `~/.alpi/profiles/`; org boundaries are source-side, not runtime.
- Two orgs that share a profile name (e.g. `vera`) cannot coexist on one machine — pick a machine per org, or rename agents.

## Layout

```
organizations/
  setup.py                       # unified bootstrap (one entry point, every org)
  README.md                      # multi-org index
  <org>/
    <org>.md                     # design contract
    org.yaml                     # bootstrap config (schema below)
    user-memory.md               # USER.md template ({name}, {wg_section}, {peers})
    agents/<name>/agent.md       # frontmatter + soul
    agents/<name>/skills/<cat>/<skill>/SKILL.md
    common/skills/<cat>/<skill>/SKILL.md   # optional shared skills
    workgroups/<name>/workgroup.md         # hub + members + briefing
```

## `org.yaml` keys (every one `setup.py` consumes)

| Key | Default | Effect |
|---|---|---|
| `display_name` | `<name>` | Console label during bootstrap. |
| `workspace` | `~/alpi/organizations/<name>/` | Default project root for the org's profiles. `~` honoured verbatim; bare YAML `~` → None → default. |
| `workspace_scaffold` | `[]` | Subdirs created inside `workspace`. |
| `sync` | `[]` | `{src, dst}` pairs copied into `workspace` every bootstrap (replace mode). |
| `peer_edges` | `[]` | **Preferred** peer-graph declaration. `"all"` (complete graph), `[[a, b], …]`, or empty. |
| `models.default` | `openai/gpt-5.4-mini` | Tier-default model. |
| `models.strong` | `anthropic/claude-sonnet-4-6` | Tier-strong model. |
| `budgets.daily_default` | `2.0` | USD daily cap for tier-default agents. |
| `budgets.daily_strong` | `5.0` | USD daily cap for tier-strong agents. |
| `budgets.workgroup` | `50.0` | Default lifetime cap per workgroup. |
| `agent_voices` | `{}` | `<agent-name> → Edge TTS voice id`. |
| `common_skills` | `{}` | `<cat>/<skill> → [agent names]` for `common/skills/` redistribution. |

## Peer graph: three sources merged

Deduped union — no runtime precedence; the edge set is computed once by `setup.py::derive_edges`:

1. `org.yaml peer_edges` — preferred declaration site for new orgs.
2. `agent.md peers:` frontmatter — **legacy**, still honoured for back-compat.
3. Workgroup membership — every `workgroup.md` adds hub↔member edges automatically (and can stand alone — an org with no `peer_edges` and no `peers:` still has a working graph through its workgroups).

Overlap is harmless; edges are deduped.

## `agent.md` frontmatter

Only field required to be present: `reasoning_effort` (`off | low | medium | high`). Validation also rejects invalid `tier` values and unknown names in `tools_deny`, but those checks fire only when the field is set.
Optional with defaults: `bio` (`""`), `accent` (`"#888888"`), `tier` (`"default"`; can be `"strong"`), `model` (overrides tier), `daily_usd` (overrides tier budget), `tools_deny` (list of tool names — validation rejects unknown names), `peers` (legacy).

Body is the agent's soul, copied verbatim into the profile's `memories/AGENT.md`.

## `workgroup.md` frontmatter

`hub` (required), `members` (list of agent names), `budget_usd` (optional; defaults to `budgets.workgroup`). Body is the briefing.

## `setup.py` modes

| Flag | Effect |
|---|---|
| (none) | Full destructive bootstrap; runs validation first. |
| `--check` | Validation only (CI). Exits non-zero on hard errors. |
| `--skills-only` | Re-sync SKILL.md files only. No profile nuke. |
| `--workspace-only` | Re-sync workspace scaffold + sync entries. |
| `--no-check` | Skip pre-bootstrap validation. Use sparingly. |
| `--nuke` | Destroy every profile in this org. Workspace untouched. |
| `--nuke --workspace` | Same as `--nuke` plus delete the workspace dir. Refuses if workspace is `~`. |

Validation: SKILL.md structural integrity, `tools_deny` against the live tool registry (hard error on typo), category against alpi's closed enum (hard error — drops the skill from the system-prompt index otherwise), `reasoning_effort` declared on every `agent.md`.

## Persistent workgroups

Workgroups in `<org>/workgroups/` are **persistent**: the hub creates them on bootstrap, members join, and they stay open across days. Ad-hoc workgroups for projects (e.g. `web-factory/`'s per-hotel `proj-<slug>`) are also persistent through launch and into maintenance iterations — not ephemeral.

## Related topics

- Workgroup protocol over the wire: `alp`
- Skills and tool routing: `skills`
- Model selection: `models`
- Profile isolation: `profiles`
