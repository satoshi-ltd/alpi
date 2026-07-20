# organizations/

Source of truth for every **org** running on the alpi stack. An org is a
self-contained team — its own agents, workgroups, common skills, and
bootstrap script. Orgs are a source-side grouping; the alpi runtime sees
only the union of profiles installed under `~/.alpi/profiles/`.

## Current orgs

| Org | Purpose | Machine |
|---|---|---|
| [`web-factory/`](web-factory/README.md) | Standalone factory producing hotel websites (11 profiles, 3 standing workgroups + one persistent `proj-<slug>` workgroup per hotel) | dedicated factory machine |
| [`lab/`](lab/README.md) | Minimal ALP protocol testbed — 4 profiles, 1 workgroup, a deterministic check of every workgroup invariant (`test-protocol.py`) | any dev box |

Orgs talk to each other peer-to-peer via ALP. Cross-org workgroups are
not supported by convention — keeps the namespace clean.

## Layout convention

Every org folder follows the same shape:

```
<org>/
├── <org>.md              ← design contract (roster, workgroups, lifecycle)
├── org.yaml              ← bootstrap config: workspace, scaffold, sync, voices, common_skills
├── user-memory.md        ← USER.md template fed to every agent (placeholders: {name}, {wg_section}, {peers})
├── agents/
│   └── <name>/
│       ├── agent.md      ← frontmatter (bio, accent, tools_deny, model/tier overrides) + body
│       ├── mcp.yaml      ← optional MCP server config
│       └── skills/
│           └── <cat>/<slug>/SKILL.md
├── workgroups/
│   └── <name>/workgroup.md
├── common/skills/        ← optional shared skills installed across the roster
└── (org-specific tools)  ← e.g. web-factory/recipes/hotel.yaml, lab/test-protocol.py
```

A single `organizations/setup.py` reads `<org>/org.yaml` and does the
mechanical bootstrap work (nuke profiles, write configs, scaffold
workspace, sync templates, create workgroups, install skills). Org
shape lives in YAML; only genuinely org-specific tools (per-project
bootstrap, post-bootstrap task seeding) live next to the org.

Three kinds of file live in an org folder, and only the first is
consumed by `setup.py`:

1. **Definition** (fixed names, every org has them): `org.yaml`,
   `<org>.md`, `user-memory.md`, `agents/`, `workgroups/`, `common/`.
2. **Product content** (only when the org ships something from the
   repo): web-factory's `templates/`, `factory/`, `library/`,
   `briefings/` — synced into the workspace via `org.yaml sync:`.
3. **Operating scripts** (`*.py` at the org root, run by the human, not
   by bootstrap): lab's protocol/recall test harnesses, web-factory's
   `tools/acceptance.py` / `tools/batch.py`.
   An org with no runtime rituals has none; an org that runs a
   production pipeline accumulates them.

## The single entrypoint

[`setup.py`](setup.py) is the only tool you call to operate an org.
Modes:

| Flag | What it does |
|---|---|
| (none) | Full destructive bootstrap. Validates first; aborts on hard errors. |
| `--skills-only` | Re-syncs SKILL.md files into existing profiles. No profile nuke. |
| `--workspace-only` | Re-syncs workspace scaffold + templates/library. No profile or workgroup touch. |
| `--check` | Runs validation only and exits. Suitable for CI. Exits non-zero on hard errors. |
| `--no-check` | Skips the pre-bootstrap validation gate. Use sparingly. |
| `--nuke` | Destroys all profiles for this org under `~/.alpi/profiles/`. Workgroups go with them. No rebuild. Workspace untouched. |
| `--nuke --workspace` | Same as `--nuke` plus deletes the workspace dir (`projects/`, `archive/`, templates, library — everything). Refuses if workspace is `~`. Irreversible. |

Validation runs by default before every destructive action. It checks
SKILL.md structural integrity (`description:` + `category:` required),
tool names in skill frontmatter against the live `alpi/tools/` registry
(warnings), `tools_deny:` in agent.md against the same registry (hard
error: a typo silently leaves the tool enabled), and `reasoning_effort:`
declared explicitly in every agent.md (`off | low | medium | high`).

`--nuke` skips validation — it's destructive without reading skills, so
nothing to validate. Useful when something gets stuck, when
decommissioning an org, or before moving to a different machine.

## Bootstrap commands

```bash
# Web factory org (factory machine):
uv run python organizations/setup.py web-factory
alpi -p mira workgroup launch --recipe organizations/web-factory/recipes/hotel.yaml --param slug=<slug>

# Protocol testbed (any dev box) — bootstrap, then verify every ALP invariant:
uv run python organizations/setup.py lab
uv run python organizations/lab/test-protocol.py           # single-task suite (default)
uv run python organizations/lab/test-protocol.py --live    # drive real agents (watch markers in the apps)
uv run python organizations/lab/test-protocol.py --stress  # edge cases: preemption, pause, budget, rekey

# Iterate on skills (no profile wipe):
uv run python organizations/setup.py <org> --skills-only

# Iterate on workspace assets — templates, brand starters (no profile wipe):
uv run python organizations/setup.py <org> --workspace-only

# Validation only (CI-friendly):
uv run python organizations/setup.py <org> --check

# Destroy everything and start fresh (profiles wiped, workspace kept):
uv run python organizations/setup.py <org> --nuke

# Destroy everything INCLUDING the workspace (web-factory: kills projects/ too):
uv run python organizations/setup.py web-factory --nuke --workspace
```

## Adding a new org

1. `mkdir organizations/<name>/`
2. Write `<name>.md` (the design contract).
3. Write `org.yaml` (workspace, scaffold, voices, common_skills — see
   [`web-factory/org.yaml`](web-factory/org.yaml) as reference).
4. Write `user-memory.md` (template with `{name}`, `{wg_section}`,
   `{peers}` placeholders).
5. Populate `agents/` + `workgroups/`.
6. Register the org in this README's table.
7. `setup.py <new-org>` discovers it automatically via the `org.yaml`
   presence — no other registration needed.
8. Profiles land under `~/.alpi/profiles/` — name collisions across
   orgs are physically resolved by running each org on its own machine.
   If two orgs must coexist on one machine, prefix agent names (e.g.
   `co-vera`, `wf-vera`) — currently an open question per
   `web-factory/README.md` §15.

## Phase 2 · cross-org ALP

The intended runtime: a profile (e.g. `vera`) lives in exactly one org,
on exactly one machine. Other orgs talk to her by peering over ALP —
the standard cluster-exchange flow. No special cross-org primitive.
