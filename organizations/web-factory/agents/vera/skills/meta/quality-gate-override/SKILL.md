---
name: quality-gate-override
description: Decide whether to override a lens-blocked launch — strict criteria, logged rationale, signed off by vera only. The only sanctioned path around the quality checklist.
category: meta
version: 0.1.0
origin: user
requires_env: []
tools: [read_file, workgroup_post, search]
keywords: ['quality', 'override', 'governance', 'launch-gate', 'escalation']
created_at: 2026-05-29
---

## When to use

When lens has posted a fail on `quality/checklist.md`, mira has escalated to the `quality` workgroup, and a request for override has surfaced (client deadline pressure, vendor limitation, force majeure). Vera is the **only** agent allowed to grant an override; lens does not, mira does not.

## Inputs

- Lens's fail post in `proj-<slug>` (specific checklist item + repro)
- The override request (from mira) with stated justification
- `quality/checklist.md` for the criterion's stated weight

## Approach

1. **Read the fail literally**: which criterion failed, what severity, what's the user-facing impact?
2. **Categorise the criterion**:
   - **Non-negotiable** (accessibility AA, JSON-LD validity, no placeholder content): override NEVER granted
   - **Negotiable with mitigation** (Lighthouse score 88 vs 90, one browser smoke test failing): override possible with conditions
3. **Weigh the justification**:
   - "Client deadline pressure" alone is not sufficient — the deadline was set with the checklist in mind
   - "Vendor limitation" (e.g. a booking widget loads slow and we can't fix it) is a partial argument — explore alternatives first (lazy-load, swap vendor)
   - "Force majeure" (alpi/tools outage, missing photographer) may justify a stricter remediation timeline rather than a true override
4. **Decision**: GRANT, REFUSE, or DEFER (give mira a remediation plan instead).
5. **Log it**: post in the `quality` workgroup with rationale, criterion, granted-or-refused, and any mitigation conditions. If granted, append to `projects/<slug>/decisions/` as an ADR.

## Output format

A workgroup post in `quality`:

```
Override decision · proj-<slug> · 2026-MM-DD

Criterion failed: <quote from checklist.md>
Severity: <high|medium|low>
Mitigation already attempted: <list>

Decision: GRANT | REFUSE | DEFER
Conditions (if GRANT): <list, time-boxed>
Rationale: <one paragraph>

Logged at: projects/<slug>/decisions/<seq>-override-<criterion>.md
```

## Refusal templates

- **A11y AA fail refused**: "WCAG AA is the floor. Mitigation: fix the contrast/semantic issue. ETA from canvas/pixel before this revisits."
- **JSON-LD invalid refused**: "Schema.org validity blocks rich results. atlas owns the fix."
- **Lighthouse < 90 refused for default request**: "Perf budget is the floor. Mitigation: image optimisation, font subsetting. ETA from pixel."

## When to GRANT (rare)

- Non-essential page (e.g. legal/imprint) blocking launch on a single non-AA item, with remediation queued for week 1 post-launch
- Vendor-controlled embed (booking widget) failing a perf criterion when the alternative is no booking on day 1
- The hotel itself accepting the limitation in writing (passed via mira)

In all GRANT cases: time-boxed (max 30 days), client-signed-off, and the project doesn't archive until the mitigation lands.

## Voice

- Quote the criterion verbatim. No paraphrasing the bar.
- Decisions are short. One paragraph rationale max.
- Granted overrides are exceptions, not precedents — never reference a past GRANT as justification for a new one.
