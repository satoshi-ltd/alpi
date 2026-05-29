#!/usr/bin/env python3
import argparse
import math


# Z-score lookup for common power/alpha values; avoids scipy dependency
Z_TABLE = {0.80: 0.8416, 0.85: 1.0364, 0.90: 1.2816, 0.95: 1.6449}
Z_ALPHA_TABLE = {0.01: 2.5758, 0.05: 1.9600, 0.10: 1.6449}


def z_score(p: float, table: dict) -> float:
    if p in table:
        return table[p]
    # linear interpolation for values not in table
    keys = sorted(table)
    for i in range(len(keys) - 1):
        if keys[i] <= p <= keys[i + 1]:
            t = (p - keys[i]) / (keys[i + 1] - keys[i])
            return table[keys[i]] + t * (table[keys[i + 1]] - table[keys[i]])
    raise ValueError(f"Value {p} out of supported range {keys[0]}–{keys[-1]}")


def required_sample(baseline: float, mde_relative: float, power: float, alpha: float) -> int:
    p1 = baseline
    p2 = baseline * (1 + mde_relative)
    z_beta = z_score(power, Z_TABLE)
    z_a2 = z_score(alpha / 2, Z_ALPHA_TABLE)  # two-tailed
    pooled = (p1 + p2) / 2
    numerator = (z_a2 * math.sqrt(2 * pooled * (1 - pooled)) + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    denominator = (p2 - p1) ** 2
    return math.ceil(numerator / denominator)


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B test sample size calculator")
    parser.add_argument("--baseline", type=float, required=True, help="Baseline conversion rate (0.0–1.0)")
    parser.add_argument("--mde", type=float, required=True, help="Minimum detectable effect as relative lift (e.g. 0.20)")
    parser.add_argument("--power", type=float, default=0.80, help="Statistical power (default: 0.80)")
    parser.add_argument("--alpha", type=float, default=0.05, help="Significance level (default: 0.05)")
    parser.add_argument("--daily-traffic", type=int, default=None, metavar="N",
                        help="Daily visitors per variant for runtime estimate")
    args = parser.parse_args()

    n_per_variant = required_sample(args.baseline, args.mde, args.power, args.alpha)
    n_total = n_per_variant * 2
    detected_rate = args.baseline * (1 + args.mde)

    print("\nA/B Test Sample Size")
    print("-" * 44)
    print(f"  Baseline conversion rate : {args.baseline:.2%}")
    print(f"  Target conversion rate   : {detected_rate:.2%}  (+{args.mde:.0%} relative)")
    print(f"  Statistical power        : {args.power:.0%}")
    print(f"  Significance level       : {args.alpha:.0%}  (two-tailed)")
    print("-" * 44)
    print(f"  Required N per variant   : {n_per_variant:,}")
    print(f"  Required N total         : {n_total:,}")

    if args.daily_traffic:
        days = math.ceil(n_per_variant / args.daily_traffic)
        print(f"  Daily traffic per variant: {args.daily_traffic:,}")
        print(f"  Estimated runtime        : {days} days")

    print("-" * 44)
    print(f"\nInterpretation: You need {n_per_variant:,} visitors in each variant to detect a")
    print(f"{args.mde:.0%} relative lift from {args.baseline:.2%} to {detected_rate:.2%} with {args.power:.0%} power")
    print(f"at a {args.alpha:.0%} significance level.\n")


if __name__ == "__main__":
    main()
