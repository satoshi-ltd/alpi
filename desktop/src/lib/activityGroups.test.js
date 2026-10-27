import { describe, expect, it } from "vitest";
import { ACTIVITY_FILTERS, UPCOMING_CAP, applyFilter, capDays, failingJobs, groupActivity, groupByDay, nextRun, stripProfilePrefix, visibleFilters } from "../../../common/activityGroups.mjs";

const NOW = Date.parse("2026-10-26T12:00:00Z");
const S = NOW / 1000;
const iso = (offsetS) => new Date(NOW + offsetS * 1000).toISOString();
const failed = (profile, id, agoS, extra = {}) => ({ profile, job_id: id, title: id, next_fire: iso(3600), last_run_status: "error", last_run_at: S - agoS, ...extra });

const ACTIVITY = {
  needs_you: [{ kind: "approval", request_id: "r1", profile: "alpi" }],
  running: [{ kind: "turn", profile: "sentinel", job_id: "rerun", title: "Rerun" }],
  scheduled: [
    failed("sentinel", "old", 7200, { last_ok_at: S - 10000 }),
    failed("pulse", "lobby", 600),
    failed("sentinel", "new", 60),
    failed("sentinel", "rerun", 120),
    failed("agora", "stale", 3 * 86400),
    { profile: "curator", job_id: "nightly", title: "Nightly", next_fire: iso(7200), last_run_status: "ok" },
    { profile: "curator", job_id: "past", title: "Past", next_fire: iso(-60), last_run_status: "ok" },
    { profile: "curator", job_id: "never", title: "Never", next_fire: null },
  ],
};

describe("groupActivity", () => {
  const g = groupActivity(ACTIVITY, { nowMs: NOW });

  it("groups failures per profile, newest group first, newest job first", () => {
    expect(g.failing.map((x) => [x.profile, x.count])).toEqual([["sentinel", 2], ["pulse", 1]]);
    expect(g.failing[0].jobs.map((j) => j.job_id)).toEqual(["new", "old"]);
    expect(g.failing[0].latestAt).toBe(S - 60);
  });

  it("carries last ok as epoch seconds and null when the daemon sends none", () => {
    const [newest, oldest] = g.failing[0].jobs;
    expect(oldest.lastOkAt).toBe(S - 10000);
    expect(newest.lastOkAt).toBeNull();
  });

  it("leaves a failure that is running again to Running, and one older than a day out of Failing", () => {
    expect(failingJobs(g).map((j) => j.job_id)).toEqual(["new", "old", "lobby"]);
  });

  it("lists upcoming as future runs only", () => {
    expect(g.upcoming.map((j) => j.job_id)).toEqual(["stale", "nightly"]);
  });

  it("keeps an old failure with a future run in upcoming", () => {
    expect(groupActivity({ scheduled: [failed("agora", "stale", 3 * 86400)] }, { nowMs: NOW }).upcoming.map((j) => j.job_id)).toEqual(["stale"]);
  });

  it("counts every section and the total", () => {
    expect(g.counts).toEqual({ all: 7, needs: 1, failing: 3, running: 1, upcoming: 2 });
  });

  it("tolerates a missing or malformed payload", () => {
    expect(groupActivity(null).counts.all).toBe(0);
    expect(groupActivity({ needs_you: "x", scheduled: [null, 3] }).counts.all).toBe(0);
  });
});

describe("applyFilter", () => {
  const g = groupActivity(ACTIVITY, { nowMs: NOW });

  it("exposes the five filters in board order", () => {
    expect(ACTIVITY_FILTERS).toEqual(["all", "needs", "failing", "running", "upcoming"]);
  });

  it("keeps everything for all and one section otherwise", () => {
    expect(applyFilter(g, "all")).toBe(g);
    const failing = applyFilter(g, "failing");
    expect(failing.failing).toHaveLength(2);
    expect([failing.needs, failing.running, failing.upcoming].every((x) => x.length === 0)).toBe(true);
    expect(applyFilter(g, "needs").needs).toHaveLength(1);
    expect(applyFilter(g, "bogus")).toBe(g);
  });
});

describe("stripProfilePrefix", () => {
  it("drops the profile name and its separator from a title", () => {
    expect(stripProfilePrefix("Sentinel PR review", "sentinel")).toBe("PR review");
    expect(stripProfilePrefix("sentinel · watch", "Sentinel")).toBe("watch");
    expect(stripProfilePrefix("Sentinel", "sentinel")).toBe("Sentinel");
    expect(stripProfilePrefix("Sentinelfoo", "sentinel")).toBe("Sentinelfoo");
    expect(stripProfilePrefix("Profiles watch", "alpi", "default")).toBe("Profiles watch");
  });
});

describe("visibleFilters", () => {
  const counts = (over) => ({ all: 0, needs: 0, failing: 0, running: 0, upcoming: 0, ...over });

  it("hides the whole row when at most one kind has entries", () => {
    expect(visibleFilters(counts({ all: 20, upcoming: 20 }))).toEqual([]);
    expect(visibleFilters(counts())).toEqual([]);
  });

  it("shows All and only the kinds above zero once two kinds have entries", () => {
    expect(visibleFilters(counts({ all: 5, needs: 2, upcoming: 3 }))).toEqual(["all", "needs", "upcoming"]);
  });

  it("keeps the current filter and All so a chosen kind that empties can be left", () => {
    expect(visibleFilters(counts({ all: 3, upcoming: 3 }), "failing")).toEqual(["all", "failing", "upcoming"]);
  });
});

describe("day grouping", () => {
  const at = (iso) => ({ nextAt: Date.parse(iso) / 1000 });

  it("groups upcoming runs by the viewer's local day with the day offset", () => {
    const now = new Date(2026, 9, 26, 12, 0).getTime();
    const rows = [at(new Date(2026, 9, 26, 15, 0)), at(new Date(2026, 9, 26, 23, 59)), at(new Date(2026, 9, 27, 0, 1)), at(new Date(2026, 9, 31, 9, 0))];
    const days = groupByDay(rows, { nowMs: now });
    expect(days.map((d) => [d.days, d.rows.length])).toEqual([[0, 2], [1, 1], [5, 1]]);
  });

  it("keeps a day boundary correct across a daylight-saving change", () => {
    const zone = process.env.TZ;
    process.env.TZ = "America/New_York";
    try {
      const now = new Date(2026, 9, 31, 12, 0).getTime();
      const rows = [at(new Date(2026, 10, 1, 0, 30)), at(new Date(2026, 10, 1, 23, 30)), at(new Date(2026, 10, 2, 0, 30))];
      expect(groupByDay(rows, { nowMs: now }).map((d) => [d.days, d.rows.length])).toEqual([[1, 2], [2, 1]]);
    } finally {
      if (zone === undefined) delete process.env.TZ;
      else process.env.TZ = zone;
    }
  });

  it("names the next run as the first upcoming one", () => {
    const g = groupActivity(ACTIVITY, { nowMs: NOW });
    expect(nextRun(g)).toBe(g.upcoming[0]);
    expect(nextRun(g).job_id).toBe("stale");
    expect(nextRun({ upcoming: [] })).toBeNull();
  });
});

describe("capDays", () => {
  const day = (start, n) => ({ start, days: 0, rows: Array.from({ length: n }, (_, i) => ({ i })) });

  it("cuts across days at the limit and counts what is hidden", () => {
    const { days, hidden } = capDays([day(1, 4), day(2, 6), day(3, 5)], UPCOMING_CAP);
    expect(days.map((d) => [d.rows.length, d.total])).toEqual([[4, 4], [6, 6]]);
    expect(hidden).toBe(5);
  });

  it("cuts inside a day and keeps that day's full total", () => {
    const { days, hidden } = capDays([day(1, 7), day(2, 7)], 10);
    expect(days.map((d) => [d.rows.length, d.total])).toEqual([[7, 7], [3, 7]]);
    expect(hidden).toBe(4);
  });

  it("hides nothing under the limit", () => {
    expect(capDays([day(1, 3)]).hidden).toBe(0);
  });
});
