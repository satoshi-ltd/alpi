---
name: ab-test-analysis
description: Design or analyze an A/B test — with correct hypothesis, sample size, statistical validity, and honest interpretation
category: data
version: 0.1.0
origin: user
requires_env: []
tools: [terminal, db]
keywords: [ab test, experiment, statistics, hypothesis, significance]
created_at: 2026-05-05
---

## When to use
Before running an experiment (design phase) or after it completes (analysis phase). Also use to audit an existing A/B test for methodological errors before its results are used to make a decision.

## Output format

**Mode** — Experiment design / Post-test analysis.

**For experiment design:**

*Hypothesis* — "We believe [change] will [increase/decrease] [metric] for [segment] because [reason]."

*Primary metric* — the single number that determines if the hypothesis is supported. If there are multiple primary metrics, the test is testing multiple hypotheses.

*Guardrail metrics* — metrics that must not degrade for the test to be considered a win.

*Minimum detectable effect* — the smallest change that would be meaningful to the business. (Do not confuse with statistical significance.)

*Sample size calculation*
- Baseline conversion rate: [%]
- MDE: [%]
- Required statistical power: [80% / 90%]
- Significance level: [0.05 / 0.01]
- Required sample per variant: [N] — calculated, not guessed

*Estimated runtime* — at current traffic, how many days to reach required sample?

*Randomization unit* — user / session / account? If a user can see both variants, the test is invalid.

**For post-test analysis:**

*Results table*

| Variant | N | Conversion rate | Relative lift | p-value | 95% CI |
|---|---|---|---|---|---|
| Control | | | — | — | — |
| Treatment | | | | | |

*Statistical validity checks*
- Was the test run to the planned sample size? (Stopping early inflates false positive rate.)
- Was there SRM (Sample Ratio Mismatch)? Expected split vs. actual split.
- Was there novelty effect? (Did early results diverge from later results?)

*Interpretation* — what does this result mean for the decision, not just for the metric?

*Recommendation* — ship / don't ship / run a follow-up test, with one-sentence rationale.

## Approach
- "Statistically significant" does not mean "practically important." A 0.1% lift significant at p=0.01 may not be worth shipping.
- Sample size must be calculated before the test starts, not after. Post-hoc power analysis is how p-hacking happens.
- A single A/B test is evidence, not proof. Decisions that require multiple independent replications should say so.
- Guardrail metrics prevent local optimization. Winning on conversion while losing on retention is not a win.

## State
A/B test history is leverage — past tests tell you what doesn't work, prevent re-running, and surface effect-size patterns.

```sql
CREATE TABLE IF NOT EXISTS ab_tests (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis        TEXT NOT NULL,
    surface           TEXT NOT NULL,           -- 'pricing-page' / 'onboarding-step-2' / etc.
    primary_metric    TEXT NOT NULL,
    baseline          REAL,
    mde_pct           REAL,
    sample_per_variant INTEGER,
    started_at        TEXT NOT NULL,
    ended_at          TEXT,
    lift_pct          REAL,
    p_value           REAL,
    decision          TEXT,                    -- ship / dont-ship / inconclusive / follow-up
    note              TEXT
)
```

Before designing a new test, query `WHERE surface = ?` to see prior tests on the same surface — never re-run a hypothesis already settled.
