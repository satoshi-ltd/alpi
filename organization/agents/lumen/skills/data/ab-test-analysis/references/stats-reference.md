# A/B Testing Statistics Quick Reference

---

## Key Terms

**Null hypothesis (H₀):** The assumption that there is no difference between variants — the treatment has no effect.

**Alternative hypothesis (H₁):** The hypothesis that there is a real difference between variants that is unlikely to be due to chance.

**p-value:** The probability of observing results as extreme as yours (or more extreme) if the null hypothesis were true — not the probability that the null is false.

**Statistical power (1 − β):** The probability of detecting a real effect when one exists. Conventional target: 80%.

**Type I error (α, false positive):** Concluding there is an effect when there isn't one. Conventional threshold: 5% (α = 0.05).

**Type II error (β, false negative):** Failing to detect a real effect when one exists. Conventional threshold: 20% (β = 0.20).

**MDE (Minimum Detectable Effect):** The smallest effect size you want to be able to detect. Smaller MDE requires more traffic.

**Confidence interval (CI):** A range of plausible values for the true effect. A 95% CI means: if you ran this experiment 100 times, ~95 of the intervals would contain the true effect.

---

## Sample Size Formula

Normal approximation for a two-tailed test comparing two proportions:

```
n = 2 × (Z_α/2 + Z_β)² × p̄(1 − p̄) / MDE²
```

Where:
- `n` = sample size per variant
- `Z_α/2` = Z-score for significance level (1.96 for α = 0.05)
- `Z_β` = Z-score for power (0.84 for 80% power)
- `p̄` = baseline conversion rate
- `MDE` = minimum detectable effect (absolute, not relative)

**Example:** Baseline rate 10%, MDE = 2 percentage points, α = 0.05, power = 80%
→ `n ≈ 2 × (1.96 + 0.84)² × 0.10 × 0.90 / 0.02²`
→ `n ≈ 2 × 7.84 × 0.09 / 0.0004 ≈ 3,528 per variant`

Use a calculator (e.g., Evan Miller's) to validate; this formula assumes equal variant sizes and binary outcomes.

---

## How to Read a p-Value

**What it means:** p = 0.03 means "if there were truly no effect, there's a 3% chance of seeing data this extreme by chance."

**What it does NOT mean:**
- It is not the probability that H₀ is true
- It is not the probability that you made an error
- A small p-value does not tell you the effect is large or practically meaningful
- A large p-value does not prove there is no effect — only that you lack evidence

**Rule of thumb:** p < α (usually 0.05) → reject H₀. p ≥ α → do not reject H₀.

---

## Common Mistakes

**Peeking early (sequential bias):** Running a test, checking results daily, and stopping when p < 0.05 inflates your false positive rate. If you check at α = 0.05 five times, your true error rate is closer to 20%. Use pre-registered sample sizes or sequential testing methods (e.g., always-valid inference) if you must peek.

**Multiple testing problem:** Testing 5 metrics at once at α = 0.05 means ~23% chance of at least one false positive. Pre-specify your primary metric and treat secondary metrics as exploratory, or apply a Bonferroni correction.

**Ignoring practical significance:** Statistical significance ≠ meaningful. A 0.1% conversion lift might be real but not worth shipping. Always ask: "Is this effect size large enough to matter to the business?"

**Relative vs. absolute MDE:** "10% improvement" on a 5% baseline is 0.5 percentage points absolute. Use absolute values in sample size calculations, not relative.

---

## When NOT to Run an A/B Test

- **Traffic too low:** If you can't reach the required sample size in a reasonable time (< 2–4 weeks), you'll either run underpowered or be tempted to peek.
- **Effect too small to matter:** If even the upper bound of the realistic effect is not worth the engineering cost, don't bother.
- **Metric not measurable:** If you can't reliably instrument the primary metric before starting, you're flying blind.
- **Qualitative problem:** User confusion, trust issues, or brand perception problems are often better diagnosed with user research first.
- **Rapid iteration phase:** If you're changing the feature weekly, a 4-week test is obsolete before it ends.

---

## SRM: Sample Ratio Mismatch

**What it is:** An SRM occurs when the actual split between variants differs significantly from the intended split. If you intended 50/50 but got 48/52, something in your assignment or tracking pipeline is broken.

**Why it matters:** SRM invalidates all results. If assignment is biased, your treatment and control groups are not comparable.

**How to detect it:** Run a chi-squared test on observed vs. expected sample counts.

```
χ² = Σ (observed − expected)² / expected
```

Example: Expected 10,000/10,000. Got 10,400/9,600.
→ χ² = (400²/10,000) + (400²/10,000) = 16 + 16 = 32 → p ≈ 0 → SRM confirmed.

**Common causes:** Bot traffic landing in one variant, redirect bugs, caching of variant assignment, logging failures, filtering applied post-assignment.

**What to do:** Stop the test. Diagnose the pipeline. Do not ship results from an SRM-affected test.
