#!/usr/bin/env python3
import argparse
from datetime import date, timedelta


def months_from_now(months: float) -> str:
    if months <= 0:
        return "already exhausted"
    today = date.today()
    target_month = today.month + int(months) - 1
    target_year = today.year + target_month // 12
    target_month = target_month % 12 + 1
    return date(target_year, target_month, 1).strftime("%b %Y")


def build_scenario(name: str, cash: float, gross_burn: float, revenue: float) -> dict:
    net_burn = gross_burn - revenue
    runway_months = cash / net_burn if net_burn > 0 else float("inf")
    runway_date = months_from_now(runway_months) if net_burn > 0 else "profitable"
    return {
        "name": name,
        "revenue": revenue,
        "gross_burn": gross_burn,
        "net_burn": net_burn,
        "runway_months": runway_months,
        "runway_date": runway_date,
    }


def print_table(scenarios: list[dict]) -> None:
    header = f"{'Scenario':<12} {'Revenue':>12} {'Gross Burn':>12} {'Net Burn':>12} {'Runway Mo':>10} {'Runway Date':>12}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for s in scenarios:
        rm = f"{s['runway_months']:.1f}" if s["runway_months"] != float("inf") else "inf"
        print(
            f"{s['name']:<12} {s['revenue']:>12,.0f} {s['gross_burn']:>12,.0f} "
            f"{s['net_burn']:>12,.0f} {rm:>10} {s['runway_date']:>12}"
        )
    print(sep)


def print_triggers(scenarios: list[dict]) -> None:
    print("\nDecision Triggers")
    print("-" * 40)
    thresholds = [(12, "Fundraise / extend runway"), (6, "Cut burn aggressively"), (3, "Emergency bridge or wind-down")]
    for s in scenarios:
        rm = s["runway_months"]
        if rm == float("inf"):
            continue
        fired = [label for months, label in thresholds if rm <= months]
        if fired:
            print(f"  {s['name']}: {rm:.1f} mo — {', '.join(fired)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Runway model across scenarios")
    parser.add_argument("--cash", type=float, required=True, help="Current cash balance")
    parser.add_argument("--burn", type=float, required=True, help="Gross monthly burn")
    parser.add_argument("--revenue", type=float, required=True, help="Current monthly revenue")
    args = parser.parse_args()

    scenarios = [
        build_scenario("Base", args.cash, args.burn, args.revenue),
        build_scenario("Upside", args.cash, args.burn, args.revenue * 1.3),
        build_scenario("Downside", args.cash, args.burn * 1.1, args.revenue * 0.7),
        build_scenario("Stress", args.cash, args.burn * 1.2, args.revenue * 0.5),
    ]

    print(f"\nRunway Model  |  Cash: ${args.cash:,.0f}  |  Gross Burn: ${args.burn:,.0f}/mo  |  Revenue: ${args.revenue:,.0f}/mo\n")
    print_table(scenarios)
    print_triggers(scenarios)
    print()


if __name__ == "__main__":
    main()
