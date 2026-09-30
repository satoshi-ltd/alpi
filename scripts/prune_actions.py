#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

Gh = Callable[[list[str]], str]


class GhError(RuntimeError):
    def __init__(self, stderr: str) -> None:
        super().__init__(stderr)
        self.stderr = stderr


def real_gh(args: list[str]) -> str:
    done = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise GhError(done.stderr.strip())
    return done.stdout


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def started(run: dict) -> datetime:
    return parse_time(run.get("run_started_at") or run["created_at"])


def select_runs(runs: list[dict], keep: int, min_age_days: float, now: datetime) -> list[int]:
    cutoff = now - timedelta(days=min_age_days)
    by_workflow: dict[int, list[dict]] = defaultdict(list)
    for run in runs:
        by_workflow[run["workflow_id"]].append(run)
    doomed: list[int] = []
    for rows in by_workflow.values():
        rows.sort(key=started, reverse=True)
        for run in rows[keep:]:
            if run["status"] == "completed" and started(run) < cutoff:
                doomed.append(run["id"])
    return doomed


def select_artifacts(artifacts: list[dict], min_age_days: float, now: datetime) -> list[int]:
    cutoff = now - timedelta(days=min_age_days)
    return [item["id"] for item in artifacts if parse_time(item["created_at"]) < cutoff]


def list_items(gh: Gh, path: str, collection: str, fields: str) -> list[dict]:
    out = gh(["--paginate", f"{path}?per_page=100", "--jq", f".{collection}[] | {{{fields}}}"])
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def delete(gh: Gh, path: str) -> bool:
    try:
        gh(["-X", "DELETE", path])
    except GhError as exc:
        if "HTTP 404" in exc.stderr:
            return True
        print(f"cannot delete {path}: {exc.stderr}", file=sys.stderr)
        return False
    return True


def resolve_repo(explicit: str | None) -> str:
    repo = explicit or os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo
    done = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture_output=True, text=True,
    )
    if done.returncode != 0 or not done.stdout.strip():
        raise SystemExit("cannot resolve the repository: pass --repo owner/name")
    return done.stdout.strip()


def main(
    argv: list[str] | None = None, gh: Gh = real_gh, now: datetime | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Delete old GitHub Actions runs and artifacts; dry run unless --apply.",
    )
    parser.add_argument("--repo", help="owner/name (default: $GITHUB_REPOSITORY or the current repo)")
    parser.add_argument("--keep", type=int, default=10, help="runs kept per workflow, newest first")
    parser.add_argument("--min-age-days", type=float, default=7, help="never delete anything younger")
    parser.add_argument("--apply", action="store_true", help="delete instead of listing")
    args = parser.parse_args(argv)
    if args.keep < 0 or args.min_age_days < 0:
        parser.error("--keep and --min-age-days cannot be negative")

    repo = resolve_repo(args.repo)
    when = now or datetime.now(timezone.utc)
    base = f"repos/{repo}/actions"
    runs = list_items(gh, f"{base}/runs", "workflow_runs", "id, workflow_id, status, created_at, run_started_at")
    artifacts = list_items(gh, f"{base}/artifacts", "artifacts", "id, created_at")
    doomed_runs = select_runs(runs, args.keep, args.min_age_days, when)
    doomed_artifacts = select_artifacts(artifacts, args.min_age_days, when)

    deleted_runs = deleted_artifacts = 0
    if args.apply:
        deleted_runs = sum(delete(gh, f"{base}/runs/{run_id}") for run_id in doomed_runs)
        deleted_artifacts = sum(
            delete(gh, f"{base}/artifacts/{artifact_id}") for artifact_id in doomed_artifacts
        )
    mode = "deleted" if args.apply else "would delete"
    print(f"runs: {mode} {deleted_runs if args.apply else len(doomed_runs)} of {len(runs)}")
    print(
        f"artifacts: {mode} "
        f"{deleted_artifacts if args.apply else len(doomed_artifacts)} of {len(artifacts)}"
    )
    failed = (len(doomed_runs) - deleted_runs) + (len(doomed_artifacts) - deleted_artifacts)
    return 1 if args.apply and failed else 0


if __name__ == "__main__":
    sys.exit(main())
