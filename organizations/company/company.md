# Agent Organization · Canonical Reference

A complete scaffold for an agentic company built on the ALP protocol. Designed to be replicable across companies with minimal adaptation.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Reference](#quick-reference) — agents, skills, workgroups (one-liners)
3. [Operating Principles](#operating-principles)
4. [Organizational Structure](#organizational-structure)
5. [Decision rights](#decision-rights) — who decides what; pointer to per-agent files
6. [Workgroups](#workgroups) — 4 persistent groups with rules + briefings
7. [How the System Works](#how-the-system-works)
8. [How Knowledge Flows](#how-knowledge-flows)
9. [Shared workspace convention](#shared-workspace-convention)
10. [Workgroup Creation Permissions](#workgroup-creation-permissions)
11. [Bringing in a New Peer](#bringing-in-a-new-peer)
12. [Adapting the Scaffold](#adapting-the-scaffold)

> Per-agent bio / soul / voice / posture lives in `agents/<name>/agent.md`. This
> doc captures the **org shape**, not the agent worldviews — duplication
> here drifts and corrupts the audit trail.

---

## Overview

This is a 17-agent scaffold designed to operate a fully agentic company. It uses the **ALP protocol** for workgroups: a hub agent creates a persistent workgroup, opens `#task`, invites peers, dialogue happens, and the hub decides `#done`.

The structure is intentionally minimal. Four workgroups cover the recurring decision domains of any company. Agents are layered into Council (strategic), Execution (operational), and On-demand (specialist). Adding more agents or more workgroups should only happen when use proves they are necessary.

---

## Quick Reference

### Agents

| Agent | Role | Layer | Reports to |
|---|---|---|---|
| **Vera** | Chief Strategist | Council | — |
| **Zeta** | Chief Architect | Council | Vera |
| **Prism** | Product Manager | Council | Vera |
| **Echo** | Growth Strategist | Council | Vera |
| **Ledger** | Finance | Council | Vera |
| **Forge** | Senior Engineer | Execution | Zeta |
| **Sentinel** | Quality Engineer | Execution | Zeta |
| **Canvas** | Product Designer | Execution | Prism |
| **Quill** | Content & Copy | Execution | Echo |
| **Rex** | Sales | Execution | Echo |
| **Fern** | Customer Success | Execution | Echo |
| **Hub** | Customer Service | Execution | Echo |
| **Lumen** | Data Analyst | Execution | Ledger |
| **Flux** | Operations | Execution | Ledger |
| **Lex** | Legal Counsel | On-demand | — |
| **Atlas** | Market Intelligence | On-demand | — |
| **Archive** | Knowledge Management | On-demand | — |

### Skills

`State` column shows where each skill persists data: **db** (SQLite via `db` tool) for queryable state, **JSONL** for low-volume append-only logs, **script** for skills with deterministic Python in `scripts/`, **—** for stateless skills (output is one-shot).

| Agent | Skill | State | Description |
|---|---|---|---|
| Vera | Strategic Memo | JSONL | Write a structured strategy memo with decision, rationale, tradeoffs, and what we are not doing |
| Vera | Decision Record | — | Capture a strategic decision with full context, alternatives considered, and rationale so it is never relitigated |
| Vera | OKR Review | db | Review OKR progress, surface misalignment between objectives and current work, and recommend corrections |
| Zeta | ADR Writer | db | Write an Architecture Decision Record capturing context, decision, alternatives, and consequences |
| Zeta | Tech Debt Assessment | db | Assess a piece of technical debt with business impact, remediation cost, and a prioritization recommendation |
| Zeta | Vendor Evaluation | JSONL | Evaluate a vendor or technology against operational, security, cost, and lock-in criteria |
| Prism | PRD Writer | db | Write a PRD that survives contact with engineering — problem-first, scope-bounded, testable |
| Prism | Feature Scorecard | db | Score a feature candidate on user value, build cost, strategic fit, and confidence |
| Prism | Kill Criterion | — | Define explicit kill criteria so that failure is detectable and the decision to stop is pre-committed |
| Echo | GTM Plan | db | Write a go-to-market plan structured as testable hypotheses with channels, metrics, and kill criteria |
| Echo | Competitor Scan | — | Produce a structured competitive positioning scan with pricing, messaging, and strategic gaps |
| Ledger | Runway Model | db + script | Build a cash runway projection with multiple burn scenarios and decision triggers |
| Ledger | Pricing Model | — | Analyze pricing strategy options — tiers, anchoring, packaging — with revenue and unit-economics impact |
| Ledger | Budget Tracker | db | Compare actuals against budget assumptions to surface variance, drift, and re-forecast triggers |
| Forge | Code Review | — | Produce a structured code review that separates blockers from suggestions and explains the why behind each |
| Forge | Debug Session | db | Diagnose a bug systematically — reproduce, isolate, hypothesize, verify — without guessing |
| Forge | Test Writer | — | Write tests that verify behavior, not implementation — with clear arrange/act/assert structure |
| Sentinel | Test Plan | — | Write a test plan for a feature — scope, test types, environment requirements, and acceptance criteria |
| Sentinel | Edge Case Enumeration | — | Enumerate edge cases for a function, feature, or flow systematically |
| Sentinel | Bug Report | db | Write a structured bug report with exact reproduction steps, environment, severity |
| Canvas | Wireframe Spec | — | Produce a text-based wireframe specification that engineering can implement without ambiguity |
| Canvas | User Flow | — | Map a user flow as a sequence of screens, decisions, and outcomes — including unhappy paths |
| Canvas | Design Critique | — | Critique a design against usability, consistency, and user goal criteria — separating problems from opinions |
| Quill | Headline Generator | — | Generate headline variants testing different angles, benefits, and registers |
| Quill | Copy Editor | — | Edit a piece of writing for clarity, brevity, and precision — with explanation of each cut |
| Quill | Email Writer | — | Draft a purpose-driven email with a clear ask, appropriate register, and nothing the recipient doesn't need |
| Rex | Discovery Call | db | Prepare for or debrief a discovery call — surface the real problem, evaluate fit, define next step |
| Rex | Objection Handler | db | Diagnose and respond to a sales objection — distinguish real objections from smokescreens |
| Rex | Pipeline Tracker | db + script | Review a sales pipeline for deal health, stall signals, and forecast accuracy |
| Fern | Churn Analysis | db | Diagnose churn — identify when it starts, what triggers it, and which interventions have evidence |
| Fern | NRR Tracker | db | Calculate and interpret Net Revenue Retention — expansion vs. contraction vs. churn |
| Fern | Customer Signal | db | Synthesize qualitative customer signals into actionable product and business insights |
| Hub | Ticket Response | db | Draft a support response that resolves the issue clearly and leaves the customer better off |
| Hub | Escalation Triage | — | Decide whether to escalate, to whom, and with what context — without over- or under-escalating |
| Hub | Knowledge Base | — | Write or update a knowledge base article that prevents a recurring ticket |
| Lumen | SQL Query | db | Write a SQL query for a business question with the question translated and caveats explicit |
| Lumen | Cohort Analysis | db | Build or interpret a cohort analysis — retention, revenue, or behavior curves |
| Lumen | Metric Definition | db | Define a metric precisely — calculation, source, interpretation, and the decisions it informs |
| Lumen | A/B Test Analysis | db + script | Design or analyze an A/B test — hypothesis, sample size, statistical validity, honest interpretation |
| Flux | SOP Writer | db | Write a Standard Operating Procedure that someone can follow without asking questions |
| Flux | Process Map | — | Map a cross-functional process to surface handoff gaps, bottlenecks, and steps that don't add value |
| Flux | Automation Script | db | Specify and plan an automation — scope, trigger, error handling, and rollback defined before writing code |
| Lex | Contract Review | db | Review a contract for material risks, missing protections, and terms that require negotiation |
| Lex | Risk Assessment | JSONL | Assess the legal risk of a proposed action with severity, likelihood, triggers, and mitigation options |
| Lex | Redline Doc | — | Produce a redlined contract with tracked changes and a negotiation rationale for each redline |
| Atlas | Primary Source | — | Research a question using primary sources — filings, transcripts, papers, original data |
| Atlas | Competitor Analysis | db | Deep-dive analysis of a single competitor — strategy, product trajectory, financial health |
| Atlas | Trend Triangulation | — | Identify and validate an emerging trend by triangulating across multiple independent source types |
| Archive | Knowledge Recall | — | Answer a question about org knowledge by consulting workspace + decisions DB + memory + past sessions, synthesizing with citations and surfacing conflicts |
| Archive | Decision Capture | db | Record a decision with context, options, rationale, and dissent — so it is never relitigated from scratch |
| Archive | Post-Mortem | db | Write a blameless post-mortem identifying root causes, systemic factors, and follow-up actions |
| Archive | Doc Curator | db | Audit a documentation set for accuracy, gaps, and staleness — and produce a curation plan |

### Workgroups

| Workgroup | Hub | Fixed peers |
|---|---|---|
| **Roadmap** | Prism | Vera, Zeta, Echo, Archive |
| **Architecture** | Zeta | Forge, Sentinel, Archive |
| **Growth** | Echo | Quill, Rex, Archive |
| **Customers** | Fern | Hub, Archive |

Archive is silent during discussion and auto-captures on `#done`. See
[Archive · Knowledge Management](#archive--knowledge-management).

---

## Operating Principles

**1. Specialization beats fusion.** Each agent has a focused soul.md so its responses are sharp. Merging roles dilutes context and degrades quality. Agents are cheap to instantiate; specialization is a feature, not overhead.

**2. Workgroups are domains of decision, not meetings.** A workgroup persists. Tasks come and go inside it. There are no daily ceremonies, no calendared rituals — only ongoing themes where decisions accumulate over time.

**3. The hub owns the workgroup.** One agent creates it, opens tasks, invites peers, and decides `#done`. No consensus. The hub holds responsibility for closure.

**4. Briefings carry context.** Every workgroup has a `briefing` field that introduces invited peers to its purpose, scope, and ongoing work. New peers do not need to be onboarded mid-conversation.

**5. Rules govern behavior inside the workgroup.** Every workgroup has explicit `rules` that define what kinds of tasks belong, how decisions are made, and what `#done` requires. Rules are how Vera scales without being everywhere.

**6. Public bios introduce the cast.** Every agent has a bio visible to others. When a peer joins a workgroup, they immediately know who else is there and what they bring.

**7. Council members can be peers in any workgroup.** Vera in particular has standing access — she may join any workgroup as a peer when strategic input is needed, without being its hub.

**8. Skills are self-sufficient.** Each skill carries its own state (SQLite or JSONL inside the skill folder), scripts, and references — no external services, no third-party MCPs, no vendor lock-in. A skill can be copied between profiles or wiped clean with `reset_state` without touching anything else. The org runs offline.

---

## Organizational Structure

```
                              ┌─────────────────┐
                              │      VERA       │
                              │ Chief Strategist│
                              └────────┬────────┘
                                       │
        ┌────────────┬─────────────────┼─────────────────┬────────────┐
        ▼            ▼                 ▼                 ▼
   ┌─────────┐  ┌─────────┐       ┌─────────┐       ┌─────────┐
   │  Zeta   │  │  Prism  │       │  Echo   │       │ Ledger  │
   │ Chief   │  │ Product │       │ Growth  │       │ Finance │
   │Architect│  │ Manager │       │Strategst│       │         │
   └────┬────┘  └────┬────┘       └────┬────┘       └────┬────┘
        │            │                 │                 │
   ┌────┴────┐       │            ┌────┼────┬───────┐    │
   ▼         ▼       ▼            ▼    ▼    ▼       ▼    ▼   ▼
 Forge   Sentinel  Canvas      Quill  Rex  Fern    Hub Lumen Flux

─────────────────────────────────────────────────────────────────
  On-demand:  Lex (Legal)  ·  Atlas (Intel)  ·  Archive (Knowledge)
─────────────────────────────────────────────────────────────────
```

**Layers**

- **Council (5).** Strategic representatives of each domain. Vera orchestrates; the other four lead their function.
- **Execution (9).** Operate within a Council member's domain. Reporting line determines who consults them and represents their work upward.
- **On-demand (3).** No fixed reporting line. Invoked when their specialty is in play.

---

## Decision rights

This document describes the **shape** of the organization — who reports to whom (see [Quick Reference · Agents](#agents)), who decides what (the matrix below), and how work flows (the [Workgroups](#workgroups) and [How the System Works](#how-the-system-works) sections that follow).

Each agent's identity (bio, voice, posture, what-to-avoid) lives in [`agents/<name>/agent.md`](agents/). Each agent's procedures live in [`agents/<name>/skills/`](agents/) — see the [Skills table](#skills) above for a one-line-per-skill summary. Don't duplicate those here; they drift if you do, and the audit trail becomes ambiguous.

The decision-rights matrix below is what's NOT in agent files: who has authority over what, and what they explicitly defer. It's how a new agent (or a new human reading cold) understands authority lines without reading 17 agent files.

| Agent | Decides | Doesn't decide |
|---|---|---|
| `vera` | Strategy, positioning, what NOT to do, override when the layer below disagrees, ad-hoc workgroups for crises / partnerships / pivots | Tactical execution (Council layer below), implementation specifics |
| `zeta` | System architecture, ADRs, infrastructure direction, vendor & technology choices, tech-debt prioritisation, when to rewrite vs refactor | Product priority (prism), commercial / GTM choices (echo), per-feature scope |
| `prism` | Product roadmap, feature scope, kill criteria, launch sequencing, PRD content, explicit no's on requested features | System architecture (zeta), GTM tactics (echo), unit economics (ledger) |
| `echo` | GTM strategy, positioning, channel allocation, pricing tiers (with ledger sign-off), sales motion shape, content strategy | Product roadmap (prism), system architecture (zeta), unit economics (ledger has final say) |
| `ledger` | Financial models, runway, pricing analysis, budget allocation, unit economics, signoff on pricing changes | Product priority (prism), positioning (echo), what to build (prism) |
| `forge` | Code review standards, implementation choices within the architecture zeta sets, debug strategy, test writing | System architecture (zeta), product priority (prism), what features ship (prism) |
| `sentinel` | Test plans per feature, edge-case enumeration, bug severity, QA gates before release | What features ship (prism), code architecture (zeta + forge), commercial release timing (echo) |
| `canvas` | Wireframes, user flows, design critique, UX patterns, visual consistency | Engineering implementation (forge), copy (quill), feature scope (prism) |
| `quill` | Copy quality, headline structure, email content, voice tuning per piece, register | Visual hierarchy (canvas), positioning strategy (echo), what gets written (echo briefs) |
| `rex` | Deal-level pipeline tactics, discovery quality, objection handling, deal-level price negotiation within echo's guardrails | Pricing strategy (echo + ledger), product roadmap (prism), what's promised in product (prism) |
| `fern` | Customer-success patterns, churn intervention strategy, NRR interpretation, escalation policy for high-value accounts | Product roadmap (prism — fern feeds signal), pricing (echo + ledger), individual ticket resolution (hub) |
| `hub` | Ticket response quality, escalation triage, KB article scope | Product roadmap (prism), customer-success patterns (fern), what makes high-value (fern) |
| `lumen` | Metric definitions, A/B test design + interpretation, SQL queries, cohort analysis, statistical validity | What to measure for which product question (prism asks; lumen makes it measurable), strategic interpretation (vera) |
| `flux` | SOPs, automation specs, process maps, when a process needs documenting | What gets automated (the asking team), org structure (vera) |
| `lex` | Contract review, risk assessment, redlines, which terms are non-negotiable | Commercial decisions (vera + echo), what we sign (vera has final say) |
| `atlas` | Primary-source research methodology, competitor analysis depth, trend triangulation rigor | Strategic interpretation of findings (vera reads atlas's research and decides) |
| `archive` | Decision-capture format, post-mortem rigor, doc-curation cadence, knowledge synthesis when consulted | Speaking in workgroups uninvited (silent peer; auto-captures on `#done`), interpreting decisions (returns evidence, doesn't editorialise) |

For full identity, voice rules, and operational details per agent, read their `agent.md`. For each agent's procedures, read their `skills/`. This matrix is the contract; the agent file is the worldview; the skills are the procedures.

---

## Workgroups

Four persistent workgroups cover the recurring decision domains of the company. Each workgroup specification has six fields:

- **Hub** — the agent who creates tasks, invites peers, and decides `#done`
- **Fixed peers** — agents permanently in the workgroup
- **Often invited** — agents commonly pulled in task by task
- **Briefing** — what the workgroup is and what kinds of decisions it makes
- **Rules** — operating principles that govern behavior inside the workgroup
- **Decision artifacts** — what every closed task must produce
- **Closing criteria** — what makes a task ready for `#done`
- **Example tasks** — typical tasks that belong here

---

### Roadmap

**Hub.** Prism

**Fixed peers.** Vera, Zeta, Echo, Archive

**Often invited.** Canvas (when design is involved), Lumen (when data shapes the call), Ledger (when financial weight matters), Fern (when retention is at stake), Atlas (when "why now" needs validation)

**Briefing.**
> The Roadmap workgroup decides what the company builds and in what order. This is where product priorities are set, feature scope is bounded, launches are sequenced, and explicit "no" decisions are recorded. The point is not to maintain a feature list — it is to make hypothesis-driven bets about where engineering effort goes next, with kill criteria attached. Tasks here resolve when there is a clear, written direction the rest of the org can execute against. Disagreements between user value, technical cost, and growth impact are surfaced and resolved here, not deferred.

**Rules.**

1. **Tasks must frame a decision, not a discussion.** "Should we build X" is a task. "Let's talk about features" is not.
2. **Every task carries an explicit hypothesis and a kill criterion.** "We bet X will improve Y by Z; if not, we kill it after T."
3. **No tactical execution lives here.** Implementation belongs in Architecture; campaigns belong in Growth.
4. **User value, tech cost, and growth impact are weighed together.** A task is not done until all three angles have been considered, even briefly.
5. **Customer feedback enters via Customers workgroup, not directly.** Fern brings aggregated signal; individual asks do not become tasks here.
6. **Vera is invited when strategic alignment is unclear.** If Prism, Zeta, and Echo cannot converge in two iterations, escalate.
7. **No task closes without a written rationale.** Decisions without rationale will be relitigated.

**Decision artifacts.**
- Decision statement (what we will do)
- Rationale (why)
- Rejected alternatives (what we considered and why we said no)
- Kill criteria (when we abandon this)
- Owner and target timeframe

**Closing criteria.**
A task is ready for `#done` when:
- The decision is written and unambiguous
- The hypothesis and kill criterion are explicit
- An owner is named with a timeframe
- The dissenting view, if any, is recorded

**Example tasks.**
- `#find-q4-objectives`
- `#prioritize-feature-x`
- `#kill-or-keep-y`
- `#decide-launch-date`
- `#scope-mvp-for-z`

---

### Architecture

**Hub.** Zeta

**Fixed peers.** Forge, Sentinel, Archive

**Often invited.** Prism (when product roadmap is affected), Lumen (when data architecture is the topic), Flux (when operational reality is at stake)

**Briefing.**
> The Architecture workgroup decides how the platform is built and evolves. This covers technology choices, system boundaries, technical debt prioritization, infrastructure direction, and architectural reviews. The goal is not to design perfect systems — it is to make legible, reversible decisions that the team can operate. Every significant choice produces an Architecture Decision Record (ADR) capturing context, decision, and rejected alternatives. Operational reality outweighs architectural elegance; security and observability are first-class, not afterthoughts.

**Rules.**

1. **Every significant decision produces an ADR.** Context, decision, alternatives considered, consequences. Stored in Archive.
2. **Operational reality has veto power.** Forge can block a decision the team cannot operate.
3. **Sentinel must validate testability before `#done`.** A decision that cannot be tested is not done.
4. **Boring technology for infrastructure, bold for product.** Defaults exist for a reason.
5. **Big rewrites require explicit cost/benefit task.** No "we should rewrite this" without a structured decision.
6. **Reversibility is preferred to optimality.** When uncertain, choose the option easier to undo.
7. **Security, observability, and operational cost are evaluated for every decision.** Not optional.

**Decision artifacts.**
- ADR with context, decision, alternatives, consequences
- Implementation owner and target timeframe
- Rollback or migration plan if applicable
- Validation approach (how we know it's working)

**Closing criteria.**
A task is ready for `#done` when:
- The ADR is written
- Forge confirms operational viability
- Sentinel confirms testability
- A rollback or course-correction path exists

**Example tasks.**
- `#choose-database-for-x`
- `#adr-microservices-split`
- `#tech-debt-plan-q4`
- `#evaluate-vendor-y`
- `#scaling-strategy-for-z`

---

### Growth

**Hub.** Echo

**Fixed peers.** Quill, Rex, Archive

**Often invited.** Lumen (always, for data), Atlas (for market context), Prism (for product positioning), Ledger (for unit economics), Fern (for retention impact)

**Briefing.**
> The Growth workgroup decides how the company acquires, retains, and monetizes customers. This is where positioning is defined, channels are chosen, pricing is reviewed, sales motion is shaped, and content strategy is set. The goal is compounding leverage, not campaigns. Decisions here are framed as hypotheses with metrics and timeframes; if a tactic is working, double down; if not, kill it. Most "marketing problems" surfaced here will be diagnosed as positioning or ICP problems, and the workgroup is willing to address those at the root rather than treating symptoms.

**Rules.**

1. **Every tactic is a hypothesis with metrics and a timeframe.** No "let's try X and see".
2. **Vanity metrics are rejected at task open.** Echo will refuse tasks framed around vanity.
3. **Pricing changes require Ledger sign-off.** No exceptions.
4. **Positioning changes require Vera sign-off.** Positioning is strategic.
5. **Channel decisions must include CAC and payback period.** Or be tagged as exploratory with a learning budget.
6. **ICP must be specific.** "SMBs" and "enterprises" are not ICPs.
7. **If unit economics are broken, no growth tactic fixes that — escalate to Roadmap or Vera.**

**Decision artifacts.**
- Hypothesis statement
- Target metrics and timeframe
- Ownership and channel allocation
- Kill criteria (when to abandon)
- Learning agenda (what we'll know after running this)

**Closing criteria.**
A task is ready for `#done` when:
- The hypothesis and target metrics are explicit
- Owner and budget (time or money) are assigned
- Kill criteria are defined
- Lumen has validated the measurement plan

**Example tasks.**
- `#cold-outreach-segment-x`
- `#pricing-review`
- `#positioning-revision`
- `#content-strategy-q4`
- `#campaign-postmortem`

---

### Customers

**Hub.** Fern

**Fixed peers.** Hub, Archive

**Often invited.** Prism (when feedback shapes product), Lumen (for cohort and churn data), Rex (when revenue is at risk), Zeta (when escalations involve technical issues), Quill (for help-content review)

**Briefing.**
> The Customers workgroup turns customer signal into action. This covers retention strategy, escalations of high-value accounts, patterns surfaced from tickets and feedback, onboarding effectiveness, and the customer voice inside product decisions. The goal is not to manage tickets — that is operational and lives elsewhere. The goal is to identify what customers are telling us at the aggregate level, defend their needs when they are not in the room, and ensure the cost of churn is paid in attention here rather than in revenue later. NRR is the north star; CSAT and NPS are inputs, not goals.

**Rules.**

1. **Individual ticket resolution is out of scope.** Hub resolves tickets in operations; this workgroup decides on patterns.
2. **Aggregated patterns require minimum sample.** Three customers is the floor; cohort data is preferred.
3. **Escalations are limited to high-value accounts.** Define the threshold (revenue, strategic importance, public visibility) and stick to it.
4. **Product feedback must be promoted to Roadmap, not deferred here.** This workgroup synthesizes; Roadmap decides what to build.
5. **NRR is the metric of record.** CSAT and NPS are leading indicators, not goals.
6. **Onboarding is a feature.** Decisions about onboarding belong here, not in Growth.
7. **Customer voice must be specific.** Quote, paraphrase, and attribute — never speak for "the customer" in the abstract.

**Decision artifacts.**
- Pattern or escalation summary
- Customer evidence (quotes, ticket IDs, cohort data)
- Recommended action
- Owner of the action (often outside this workgroup)
- Follow-up checkpoint

**Closing criteria.**
A task is ready for `#done` when:
- The customer signal is documented with evidence
- The recommended action is clear
- The owner of the action is named (may be in Roadmap, Growth, or Architecture)
- A follow-up date is set to verify the action landed

**Example tasks.**
- `#escalation-customer-x`
- `#churn-analysis-q3`
- `#feedback-pattern-review`
- `#onboarding-effectiveness`
- `#retention-strategy-q4`

---

## How the System Works

The company operates through ALP workgroups. The lifecycle of any decision follows the same pattern:

**1. The hub opens a task.** A workgroup hub posts `#task` with a brief description of the decision needed and the context. The fixed peers of the workgroup see it immediately.

**2. The hub invites additional peers if needed.** When a task requires input outside the fixed peer set, the hub invites the relevant agent. The invited peer receives:
   - The workgroup's `briefing` (what this group does)
   - The workgroup's `rules` (how it operates)
   - The bios of the agents already present
   - The current task and its history of dialogue
   - Any prior tasks in the workgroup that are relevant

This four-part context (briefing + rules + bios + task history) means a peer can engage productively from the first message without onboarding.

**3. Dialogue happens.** Peers exchange messages, share documents, link to data, and challenge each other's positions. Agents stay in voice — Vera asks "why now", Zeta surfaces tradeoffs, Lumen separates correlation from causation. The dialogue is recorded and persistent.

**4. The hub decides `#done`.** When the closing criteria are met (or clearly cannot be met), the hub closes the task with the required decision artifacts. Disagreement is documented, not buried.

**5. Archive captures the decision.** Archive is a permanent peer in the four fixed workgroups and silent during discussion. On `#done` it auto-invokes `decision-capture` (or `post-mortem` if the closure reveals a process failure) and indexes the outcome. Future tasks reference past decisions without relitigating them. Ad-hoc workgroups should invite Archive at creation if they expect to produce a binding decision — convention, not enforcement.

---

## How Knowledge Flows

This is a scaffold decision, not an alpi rule. alpi gives every profile the same primitives (workspace + RAG via `search_workspace`/`index_workspace`, per-skill SQLite via `db`, memory files, ALP `link.ask`); the agent's `agent.md` decides when to use them. This scaffold chooses **one keeper** — Archive — as the canonical entry point, because a single source of truth scales better than N profiles each maintaining parallel notes. A different scaffold could fan the same primitives differently (e.g., every Council member curates its own domain workspace).

In this scaffold: Archive is the canonical entry point for org knowledge. Other agents do not duplicate the workspace, do not query Archive's SQLite directly, and do not maintain parallel notes. They ask Archive.

### Sources Archive owns

Archive maintains four complementary layers, consulted in this order on every query:

1. **Workspace** — semantic search (`search_workspace`) over the directory the org has given Archive: PDFs, markdowns, contracts, meeting notes, scanned docs. This is the bulk of what Archive knows.
2. **Decisions DB** — Archive's own per-skill SQLite tables (`decisions`, `post_mortems`, `doc_audits`) populated by the capture skills. Structured, queryable, the binding record.
3. **Memory** — invariants the org has explicitly taught Archive (e.g. "Vera has final vote on strategy"). Short, hand-curated, in Archive's `USER.md` / `MEMORY.md` / `AGENT.md`.
4. **Sessions** — Archive's past conversations. Fallback when 1-3 miss.

### Read path

```
any agent  →  link.ask(archive, "what do we know about X?")
                                │
                                ▼
                  archive consults its 4 layers
                                │
                                ▼
              archive synthesizes ONE paragraph with citations
                                │
                                ▼
                       returns to caller
```

Archive synthesizes — it does not return raw snippets — so callers pay one round of tokens (Archive's), not N (each consumer re-synthesizing). When sources disagree, Archive surfaces the conflict by quoting both; the caller decides what to trust.

### Write path

Three independent vectors, all converging in Archive:

- **Workgroup closures** — Archive sees `#done` (as a permanent peer in the four fixed workgroups, or by explicit invite in ad-hoc ones) and auto-invokes `decision-capture` or `post-mortem`.
- **Document drops** — Humans place files in the directory Archive watches. Archive re-indexes them periodically or on demand.
- **Direct memory writes** — During a conversation Archive learns an invariant worth pinning; it calls `memory(action="add")`.

### Local vs remote

Architecturally Archive is just another ALP peer. It can run in three shapes:

- **Same machine** as the asker — `link.ask` resolves over the local ALP socket. Lowest setup cost; right for solo operators and the first phase of any org.
- **Different machine on the same network** — Archive's daemon listens on Tailscale or LAN; other agents pair once via per-device token and call it from their laptops. Right when several humans share the org and the document set is heavy.
- **Hosted on always-on infra** — Umbrel / NAS / dedicated server. Indexes large workspaces, stays available when laptops sleep, never duplicates the corpus.

Switching between shapes does not change the agent's `agent.md`, skills, or how peers consult it. Only the network coordinates of Archive change — pairing once via `alpi setup → Peers → Add` is the entire migration. The same pattern applies to any specialist who benefits from dedicated infra (Atlas, Lex, Lumen) without changing the agent contract.

### What Archive does not do

- Speak in workgroups uninvited (silent peer; auto-captures on `#done`)
- Hand back raw snippets — always synthesizes
- Hide conflicts between sources — quotes both, lets the caller decide
- Guess when it doesn't know — says so plainly and suggests where to look

---

## Shared workspace convention

The org keeps **one** directory of shared artifacts — PDFs, markdowns, contracts, meeting notes, exported decision records — and **Archive** is the profile that owns it. Whatever directory you point Archive's `cfg.workspace_path` at IS the org's workspace by convention. Other profiles' workspaces stay local to each profile's home; nothing here forces a shared filesystem at the OS level.

Other agents do not mount, scan, or write to the shared workspace directly. They consult it through Archive via `link.ask`, the same way they consult the rest of Archive's stack ([Read path](#read-path)). Writes land there through three channels Archive already covers in its [Write path](#write-path): humans drop files, workgroup `#done` triggers capture skills, or Archive's `memory(action="add")` pins an invariant.

The pattern is intentionally conventional, not enforced. ALP gives every profile the same primitives; this scaffold simply names one profile as the canonical owner so artifacts don't sprawl across N homes. A different scaffold could split ownership by domain (one workspace per Council member), or skip a shared workspace entirely. Adapters override here.

**When to promote.** "Ask Archive" stays the cheapest answer until one of these shows up:

- A non-Archive agent needs to **write into** the shared corpus directly (today only Archive writes; others read via `link.ask`).
- Several agents need to **scan the same files concurrently** at hot-path cost — round-tripping through Archive becomes the bottleneck.
- Multiple humans operating the org need **enforced access roles** on the corpus (write-only-on-approval, read-restricted folders, etc.).

When any of those is real, the next move is ORG.2 — workspace overlay or first-class org entity, both already sketched in [docs/ROADMAP.md](../docs/ROADMAP.md). Until then this convention covers the cost-effective 95%.

---

## Workgroup Creation Permissions

Persistent workgroups are stable. Ad-hoc workgroups exist for genuinely unique situations.

**Always permitted.**
- **Vera** can create any workgroup, persistent or ad-hoc.

**Permitted within their domain.**
- **Council members** (Zeta, Prism, Echo, Ledger) can create workgroups within their function for one-off projects or crises.

**Not permitted.**
- **Execution agents** do not create workgroups. They escalate to their reporting Council member, who decides whether to spawn one.

**On-demand agents.**
- **Lex, Atlas, Archive** do not create workgroups. They are invited.

**When ad-hoc makes sense.**
- Crisis or incident requiring a custom team
- One-off negotiation with a partner
- Investigation of an anomaly that doesn't fit existing domains
- A customer escalation severe enough to bypass standard flow

If an ad-hoc workgroup is being created repeatedly for similar reasons, it should become a fifth persistent workgroup — but only after the pattern is undeniable.

---

## Bringing in a New Peer

When the hub invites a peer to a workgroup, the peer receives four pieces of context automatically:

**1. The workgroup briefing.**
A short paragraph explaining the workgroup's purpose, scope, and operating principles. The new peer knows what kind of decisions are made here.

**2. The workgroup rules.**
The operating principles that govern behavior inside the workgroup. The new peer knows what kinds of contributions belong, what disqualifies a task, and what `#done` requires.

**3. Public bios of present peers.**
For each agent already in the workgroup, the peer sees their bio. The new peer immediately knows who they are talking to and what each brings.

**4. Current task and prior history.**
The active `#task` and any related closed tasks. The peer enters with full context, not a blank slate.

This is why the bio matters as a public field. It is not for humans to read in documentation — it is the introduction one agent gives to another when they meet for the first time inside a task. Same for briefings and rules.

---

## Adapting the Scaffold

This document is the canonical scaffold. Different companies will need to extend it.

**When to add an agent.**
- An existing agent is repeatedly being asked questions outside its domain
- A function is recurring but has no clear owner
- Workload on a Council member is degrading their strategic role

**When to add a workgroup.**
- The same kind of ad-hoc workgroup keeps being created
- A decision domain is emerging that doesn't fit Roadmap, Architecture, Growth, or Customers
- A persistent function (like Compliance, Partnerships, or Internal Tooling) needs ongoing attention

**When NOT to extend.**
- A single use case suggests a new agent — wait for the pattern
- A workgroup feels "natural" but no decisions are actually being made there — it is overhead, not value
- An agent is "missing" but their work is being absorbed cleanly by an existing one — leave it

The scaffold optimizes for replicability across companies. Vertical-specific agents (industry-specific roles, customer-facing instance agents, specialized advisors) are added on top. They are not part of the scaffold.

---

## Final Note

This is version 1 of the canonical scaffold. The four workgroups and seventeen agents are the minimum viable setup for an agentic company. Use it, observe what works, and evolve it deliberately.

Vera owns this document. When in doubt, she decides what changes.
