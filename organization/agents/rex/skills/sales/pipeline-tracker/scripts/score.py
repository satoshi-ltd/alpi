#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import date, datetime


HEALTH_COLORS = {4: "Green", 3: "Yellow", 2: "Yellow", 1: "Red", 0: "Red"}


def score_deal(deal: dict, today: date | None = None) -> dict:
    today = today or date.today()
    score = 4
    penalties = []

    last_activity = datetime.strptime(deal["last_activity"], "%Y-%m-%d").date()
    close_date = datetime.strptime(deal["close_date"], "%Y-%m-%d").date()
    days_idle = (today - last_activity).days
    days_to_close = (close_date - today).days

    if days_idle > 14:
        score -= 1
        penalties.append(f"idle {days_idle}d (>14)")

    if close_date < today:
        score -= 2
        penalties.append("close date in past")

    if deal.get("stage", "").lower() == "discovery" and 0 <= days_to_close < 30:
        score -= 1
        penalties.append("discovery stage with <30d close")

    if not deal.get("next_step", "").strip():
        score -= 1
        penalties.append("no next step defined")

    score = max(score, 0)
    health = HEALTH_COLORS.get(score, "Red")
    return {**deal, "score": score, "health": health, "penalties": penalties}


def format_arr(value) -> str:
    try:
        return f"${float(value):>10,.0f}"
    except (TypeError, ValueError):
        return f"{str(value):>11}"


def print_single(result: dict) -> None:
    print(f"\nDeal Health Score\n{'─' * 44}")
    print(f"  Deal       : {result['deal']}")
    print(f"  Stage      : {result['stage']}")
    print(f"  ARR        : {format_arr(result['arr'])}")
    print(f"  Close date : {result['close_date']}")
    print(f"  Health     : {result['health']}  (score {result['score']}/4)")
    if result["penalties"]:
        print(f"  Penalties  : {'; '.join(result['penalties'])}")
    else:
        print("  Penalties  : none")
    if result.get("next_step"):
        print(f"  Next step  : {result['next_step']}")
    print()


def print_pipeline(results: list[dict]) -> None:
    header = f"{'Deal':<22} {'Stage':<14} {'ARR':>10} {'Health':>8} {'Score':>6}  Penalties"
    sep = "─" * 80
    print(f"\nPipeline Health Report\n{sep}")
    print(header)
    print(sep)
    for r in sorted(results, key=lambda x: x["score"]):
        penalties = "; ".join(r["penalties"]) if r["penalties"] else "—"
        print(f"{r['deal']:<22} {r['stage']:<14} {format_arr(r['arr'])} {r['health']:>8} {r['score']:>6}  {penalties}")
    print(sep)
    red = sum(1 for r in results if r["health"] == "Red")
    yellow = sum(1 for r in results if r["health"] == "Yellow")
    green = sum(1 for r in results if r["health"] == "Green")
    print(f"\nSummary: {green} Green, {yellow} Yellow, {red} Red  ({len(results)} total)\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sales deal health scorer")
    parser.add_argument("--deal", help="Deal name")
    parser.add_argument("--stage", help="Deal stage")
    parser.add_argument("--arr", type=float, help="Annual recurring revenue")
    parser.add_argument("--close-date", dest="close_date", help="Expected close date (YYYY-MM-DD)")
    parser.add_argument("--last-activity", dest="last_activity", help="Last activity date (YYYY-MM-DD)")
    parser.add_argument("--next-step", dest="next_step", default="", help="Next defined step")
    parser.add_argument("--all-deals", dest="all_deals", metavar="FILE",
                        help="JSON file with list of deal objects")
    args = parser.parse_args()

    if args.all_deals:
        try:
            with open(args.all_deals) as f:
                deals = json.load(f)
        except FileNotFoundError:
            print(f"Error: file '{args.all_deals}' not found.", file=sys.stderr)
            sys.exit(1)
        results = [score_deal(d) for d in deals]
        print_pipeline(results)
    elif args.deal:
        required = ["deal", "stage", "arr", "close_date", "last_activity"]
        missing = [r for r in required if not getattr(args, r.replace("-", "_"), None)]
        if missing:
            print(f"Error: missing required fields: {', '.join(missing)}", file=sys.stderr)
            sys.exit(1)
        deal = {
            "deal": args.deal,
            "stage": args.stage,
            "arr": args.arr,
            "close_date": args.close_date,
            "last_activity": args.last_activity,
            "next_step": args.next_step,
        }
        result = score_deal(deal)
        print_single(result)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
