#!/usr/bin/env python3
"""Pivot a long-format cohort dataset into a cohort × period table.

Cohort analysis input typically arrives as long-format triples
(cohort, period_offset, value). Pivoting that into a cohort × period
grid by hand is tedious and error-prone. This script does the pivot
canonically — and optionally normalises each row against its M0 baseline
to produce a retention curve table.

Input CSV columns: cohort, period_offset, value
- cohort: cohort label (e.g. '2026-01')
- period_offset: months/weeks since cohort start (0, 1, 2, ...)
- value: count, revenue, or any metric at that period for that cohort

Usage:
    python cohort_table.py --input cohorts.csv --mode pct
    cat cohorts.csv | python cohort_table.py --mode raw
"""
import argparse
import csv
import sys
from collections import defaultdict


def pivot(rows, mode):
    cohorts = sorted({r["cohort"] for r in rows})
    periods = sorted({int(r["period_offset"]) for r in rows})

    grid = defaultdict(dict)
    for r in rows:
        grid[r["cohort"]][int(r["period_offset"])] = float(r["value"])

    header = f"{'cohort':<16} " + " ".join(f"P{p:>4}" for p in periods)
    print(header)
    print("-" * len(header))

    for c in cohorts:
        baseline = grid[c].get(0)
        cells = []
        for p in periods:
            v = grid[c].get(p)
            if v is None:
                cells.append("    -")
            elif mode == "pct":
                if baseline:
                    cells.append(f"{v / baseline * 100:>4.0f}%")
                else:
                    cells.append("    -")
            else:
                cells.append(f"{v:>5.0f}")
        print(f"{c:<16} " + " ".join(cells))


def main():
    ap = argparse.ArgumentParser(description="Pivot long-format cohort data into a table")
    ap.add_argument("--input", help="CSV file (default: stdin)")
    ap.add_argument(
        "--mode",
        choices=["raw", "pct"],
        default="pct",
        help="raw: absolute values; pct: % vs each cohort's M0 baseline",
    )
    args = ap.parse_args()

    src = open(args.input) if args.input else sys.stdin
    try:
        reader = csv.DictReader(src)
        required = {"cohort", "period_offset", "value"}
        fields = set(reader.fieldnames or [])
        if not required.issubset(fields):
            raise SystemExit(
                f"input must have columns {sorted(required)}, got {sorted(fields)}"
            )
        rows = list(reader)
        if not rows:
            print("No rows in input.", file=sys.stderr)
            return 1
        pivot(rows, args.mode)
    finally:
        if args.input:
            src.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
