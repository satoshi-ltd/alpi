#!/usr/bin/env python3
"""Build cohort retention curves from the skill's churn-analysis db.

Reads cohorts and churn_events tables and prints retention % at month 0,
1, 2, ... for each cohort. Doing this by hand across multiple cohorts is
error-prone — this gives one canonical calculation everyone agrees on.

Usage:
    python cohort_curve.py --db /path/to/state/db.sqlite [--max-months 12]
"""
import argparse
import sqlite3
import sys
from pathlib import Path


def cohort_retention(conn, max_months):
    cur = conn.cursor()

    cohorts = cur.execute(
        "SELECT cohort_label, starting_count, started_at "
        "FROM cohorts ORDER BY started_at"
    ).fetchall()

    if not cohorts:
        print("No cohorts found in db.", file=sys.stderr)
        return 1

    rows = []
    for label, starting, _started in cohorts:
        churns = cur.execute(
            "SELECT months_active FROM churn_events "
            "WHERE cohort_label = ? AND months_active IS NOT NULL",
            (label,),
        ).fetchall()

        churn_by_month = {}
        for (m,) in churns:
            churn_by_month[m] = churn_by_month.get(m, 0) + 1

        retention = []
        churned_so_far = 0
        for month in range(max_months + 1):
            churned_so_far += churn_by_month.get(month, 0)
            still_active = max(starting - churned_so_far, 0)
            pct = (still_active / starting * 100) if starting else 0.0
            retention.append(pct)

        rows.append((label, starting, retention))

    months = list(range(max_months + 1))
    header = f"{'Cohort':<16} {'Start':>5}  " + " ".join(f"M{m:>2}" for m in months)
    print(header)
    print("-" * len(header))
    for label, starting, retention in rows:
        cells = " ".join(f"{p:>3.0f}" for p in retention)
        print(f"{label:<16} {starting:>5}  {cells}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Cohort retention curves from churn db")
    ap.add_argument("--db", required=True, help="Path to skill state db.sqlite")
    ap.add_argument("--max-months", type=int, default=12)
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"db not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        return cohort_retention(conn, args.max_months)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
