---
title: What Alpi costs — one metric, public bands, no metering
date: 2026-05-28
description: Alpi's pricing in full: a single billing unit (the installed agent), public graduated bands, grandfathered entry prices, founding-customer terms, and implementation services.
tags: [pricing, business]
---

# What Alpi costs — one metric, public bands, no metering

Most agent platforms bill for things that require watching you: seats, traces,
runs, tokens. Alpi bills for one thing it never has to measure — the **installed
agent**. This post is the full, public pricing picture: the metric, the bands,
what counts as installed, and the terms around it. No hidden enterprise rate
card, no negotiated discounts.

## One metric: the installed agent

The billing unit is a productive profile deployed in production doing real
business work. No seats, no traces, no tokens, no execution metering. The
customer declares how many agents are installed; we never measure usage.

This isn't a pricing gimmick — the agent is the atomic unit of the platform by
architecture. Every profile has its own cryptographic identity, memory, budget,
peer list, and capabilities. Charging per installed agent prices the unit the
platform itself recognizes, and it requires no telemetry to operate. The same
"no surveillance" principle that protects your data also shapes the invoice.

## Pricing (2026)

Public, graduated, and the same for everyone. Each band prices the agents within
it — marginal pricing, so adding one agent never triggers a tier cliff.

| Installed agents | Price per agent / year |
|---|---|
| Agents 1–10 | **$10K** |
| Agents 11–30 | **$8K** |
| Agents 31–75 | **$7K** |
| Agents 76–150 | **$5K** |
| 151+ | **Custom** |

The bands fall as you scale on purpose: the more agents you install, the better
the per-agent economics, so "build it ourselves on a framework" never wins on
cost at scale.

Worked examples (annual license):

| Deployment | Agents | Annual license |
|---|---|---|
| Small team | 5 | $50K |
| Single department (e.g. a web factory) | 15 | $140K |
| Multi-department organization | 50 | $400K |
| Large operation | 150 | $950K |

## Early price, not discounts

Alpi doesn't discount. Instead, the published price **rises** as the platform
matures — and every customer keeps the band of the year they entered, for as
long as their subscription stays continuous. 2026 is the lowest price Alpi will
ever have; entering early is rewarded structurally, not negotiated. Indicative
guidance: list prices are reviewed annually and expected to rise 15–25% per year
while the platform accumulates capabilities and references.

## Founding Customer program

The first five enterprise customers enter as Founding Customers:

- **25% off the license — first year only.** From year two they pay their
  grandfathered entry price.
- **Premium SLA included for three years** (normally 20% of the license).
- **Ten days of custom engineering included** in year one.
- **Quarterly roadmap input** and a named contact.

In exchange: a public testimonial / case study and reference-call availability.
Once filled, the program closes permanently.

## What "installed" means

An agent (profile) is installed when it:

- runs under daemon supervision (launchd / systemd) in production, and/or
- is connected via ALP to peers outside its own machine for production work,
  and/or
- is exposed via a gateway (Telegram, email, webhook) to non-developer users.

Profiles used purely for development, testing, evaluation, or sandboxed
experiments are not installed agents. Customers self-declare their count, with
the right to an annual audit if requested — **count, not content**.

## Support and services

**Standard support** is included in every paid band: email support with
business-day response, documentation access, and upgrade guidance. **Premium
SLA** is available at 20% of the annual license — defined response times, a
named engineer, assisted upgrades (free for Founding Customers for three years).

Software licenses don't transform organizations; implementation does.
Professional services are decoupled from the license and scaled to actual need —
a team with its own agent-engineering capability may not need them at all.

| Package | Duration | Price | Scope |
|---|---|---|---|
| **Bootstrap** | 2–3 weeks | **$24K** | Setup, daemon install, one workgroup, team training |
| **Deployment** | 6–8 weeks | **$60K** | Bootstrap + 3–5 production workgroups, custom skills, stack integration |
| **Transformation** | 3–6 months | **$120K–300K** | Deployment + scale to 15–50 agents, deep custom skills, runbook |
| **Custom engineering** | per day | **$2K/day** | Specific extensions, integrations, custom ALP work |

## What else you pay (and to whom)

Beyond license and services, the customer bears LLM API costs (mix providers per
profile — premium, mid-tier, or local Ollama — to optimize per workload) and
cloud infrastructure wherever the daemon runs. Because Alpi is model-agnostic by
architecture, you keep your pricing leverage with model vendors; we have no
incentive to push you toward one.

## Why this is aligned

For the customer, the license is a small fraction of the human cost it
displaces, the bands have no cliffs, success isn't penalized (an agent doing a
million turns a year costs the same as one doing a thousand), there's no usage
metering and no surprise invoice, and the grandfathered entry price means what
you've installed never gets more expensive while you stay.

For us, revenue grows with the customer's adoption — more departments
agentized, more installed agents — not with surveillance of their usage. Rising
list prices reward early customers instead of margin-destroying discounts, and
services revenue declines predictably as the customer internalizes capability.
The model is built around being aligned with the transformation, not extracting
maximum revenue from a single contract.

## Licensing, in one paragraph

The agent core is **Business Source License 1.1**, and **each released version
converts to Apache-2.0 four years after its first public release** (a rolling
window — the four-year-old codebase is always fully open source). Source is
available to read, study, and modify from day one; personal, research, and
evaluation use are free; commercial production use of current versions needs a
license. The conversion is your structural protection: if the publisher
disappeared tomorrow, every version ever shipped becomes open source within at
most four years. The Alpi Link Protocol is Apache-2.0 from day one.

---

*Prices are 2026 list. Figures here are the published rate card; deployment
ROI scenarios elsewhere on this blog are directional, not guaranteed. For
governance, compliance, or integration specifics: info@satoshi-ltd.com.*
