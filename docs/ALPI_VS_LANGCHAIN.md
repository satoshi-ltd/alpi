# Alpi vs LangChain for Agentic Organizations

This document explains the architectural difference between building an
agentic organization on Alpi and building one on a framework such as
LangChain / LangGraph.

The short version:

> LangChain makes it easy to prototype an agent workflow. Alpi makes it
> easier to operate persistent local agents as an organization.

They are not the same product category. LangChain is a developer framework.
Alpi is a local-first agent runtime with profiles, workgroups, memory,
outputs, apps, and a daemon.

## The Work Is Different

A demo agent workflow usually needs:

- a model call;
- a tool call;
- a graph or chain;
- a bit of state.

An agentic organization needs more:

- persistent identities;
- per-agent memory and workspaces;
- model and tool policy per profile;
- coordination between agents;
- durable outputs;
- human-visible progress;
- retries and stuck-turn recovery;
- searchable history;
- app notifications;
- local security boundaries;
- enough audit trail to debug unattended work.

LangChain helps with the first list. Alpi is designed around the second.

## Capability Map

| Need | Alpi | LangChain / LangGraph |
|---|---|---|
| Persistent agents | Profiles with config, memory, tools, model, workspace | Application code must define identity and storage |
| Multi-agent coordination | ALP workgroups, tasks, pipeline metadata, pause/resume, blocked state | Graph state and routing must be designed per app |
| Local-first operation | Daemon, local files, no hosted control plane, no telemetry | Possible, but not the default product posture |
| User apps | TUI, desktop, mobile through host plane | Out of scope |
| Durable outputs | Outputs inbox, notifications, deep links | App-specific design |
| Memory | Markdown memory, learned documents, session recall, workgroup transcript search | Vector store + policies + deletion semantics must be built |
| Workgroup history | Encrypted transcript + hub-local semantic search | App-specific storage |
| Notifications | App notifications + optional gateways | App-specific implementation |
| Security posture | Host pairing, ALP crypto, local filesystem posture, roadmap hardening | Boundary is application-defined |
| Operations | Daemon, schedules, logs, doctor, planned run ledger | Application-defined or external observability |

## Example: Web Factory

With LangChain, a hotel website factory would likely start as a graph:

```text
intake -> content -> translation -> build -> qa
```

That graph is useful, but it is only the orchestration skeleton. A production
workflow still needs answers to product/runtime questions:

- Who is `scout`, `quill`, `lingua`, `pixel`, and `lens` across runs?
- Where does each agent keep its memory?
- Where are project files written?
- How does the user pause the factory?
- Where does a failed QA output appear?
- How does a phone notification link back to the result?
- How do we search old workgroup decisions?
- What happens if a model call stalls for ten minutes?
- How do we know which turn wrote which file?

In Alpi, those are first-class runtime concerns. A workgroup is not just a
graph. It is a persistent collaboration surface between profiles.

## Why Profiles Matter

In Alpi, a profile is the unit of agency:

- identity;
- memory;
- tool set;
- model choice;
- workspace;
- subscriptions;
- peer relationships;
- outputs.

This matters because an organization is not a single program with several
nodes. It is a set of independent agents that can also be used directly.

For example, `lingua` should be useful both inside a workgroup and when a user
asks it directly to review translations for a project. A graph node usually has
no life outside the graph. An Alpi profile does.

## Why Workgroups Are Not Just Graphs

A graph encodes a planned flow. A workgroup encodes collaboration:

- a hub coordinates;
- members respond;
- tasks can be targeted;
- transcripts are durable;
- blocked states are visible;
- pauses stop automatic work;
- semantic search can recall decisions later.

For deterministic ETL, a graph is enough. For long-running agent work that
humans need to inspect and resume, the operational wrapper matters more than
the graph primitive.

## Where LangChain Is Still Useful

LangChain can still be useful as an implementation detail behind a profile or
skill:

- a deterministic extraction pipeline;
- a narrow graph for a domain-specific tool;
- integration with an existing LangChain codebase;
- a one-off experiment that Alpi launches as a script.

The boundary should be clear: LangChain can be a tool an Alpi profile runs.
It should not become Alpi's core runtime model.

## The v0.9 Bar

The v0.8 retrieval cycle gave Alpi the memory spine:

- learned workspace documents;
- semantic recall over sessions;
- workgroup transcript search.

The v0.9 hardening cycle is what makes the comparison stronger for real
operation:

- `OPS.1` gives every long-running turn a compact run ledger;
- `RT.1` makes provider stalls visible and recoverable;
- `SEC.1` scans recalled context before it reaches the model;
- `FS.1` audits credential-file guardrails;
- `AUDIT.1` checks local posture explicitly.

Those are the pieces that turn "agents can collaborate" into "agents can be
operated safely without a hosted orchestration service."

## Positioning

Alpi should not claim to be a better LangChain. That would frame the product
as a framework race.

The stronger claim is:

> LangChain is for developers building agent workflows. Alpi is for users and
> operators running persistent local agents and agentic organizations.

That distinction keeps the product focused and prevents the Swiss-army-knife
failure mode.
