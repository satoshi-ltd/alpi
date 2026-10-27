import { describe, expect, it } from "vitest";
import { MAX_NEEDS_ROWS, TRAY_STATES, trayModel, trayState } from "./trayModel.js";

const NOW = Date.UTC(2026, 9, 27, 12, 0, 0);
const sec = (agoSeconds) => (NOW - agoSeconds * 1000) / 1000;

const need = (i, over = {}) => ({
  id: `r${i}`,
  kind: "approval",
  profile: `p${i}`,
  label: `p${i}`,
  title: "wants to run a command",
  ts: sec(120),
  fold: "alpaca",
  accent: "#df4b9d",
  deeplink: { kind: "approval", profile: `p${i}`, id: `r${i}`, connection_id: "c1" },
  ...over,
});

const snap = (over = {}) => ({
  state: "quiet",
  member: false,
  unread: 0,
  update: null,
  needs: { total: 0, approvals: 0, questions: 0, rows: [] },
  failing: { jobs: 0, profileCount: 0, profiles: [] },
  running: { count: 0, rows: [] },
  offline: null,
  ...over,
});

const needsSnap = (n, over = {}) => {
  const rows = Array.from({ length: Math.min(n, 4) }, (_, i) => need(i));
  return snap({ state: "needs", needs: { total: n, approvals: n, questions: 0, rows }, ...over });
};

const turn = (i, over = {}) => ({ id: `t${i}`, profile: "alpi", label: "alpi", title: `Turn ${i}`, ts: NOW / 1000 - 120, fold: "llama", accent: "#14110c", deeplink: { kind: "chat", profile: "alpi", id: `s${i}`, connection_id: "c" }, ...over });

describe("trayState", () => {
  it("lets the link outrank everything and then ranks needs-you, failing, running", () => {
    expect(trayState({ link: "offline", needs: 3, failing: 1, running: 1 })).toBe("offline");
    expect(trayState({ link: "starting", needs: 3 })).toBe("starting");
    expect(trayState({ link: "connecting", needs: 3 })).toBe("connecting");
    expect(trayState({ needs: 1, failing: 2, running: 3 })).toBe("needs");
    expect(trayState({ failing: 2, running: 3 })).toBe("failing");
    expect(trayState({ running: 3 })).toBe("running");
    expect(trayState({})).toBe("quiet");
    expect(trayState()).toBe("quiet");
  });
});

describe("trayModel states", () => {
  it("draws All quiet with nothing to do", () => {
    const m = trayModel(snap(), NOW);
    expect(m).toMatchObject({ state: "quiet", title: "All quiet", sub: "Nothing needs you · online", rows: [], more: 0, counts: [], busy: null, start: false, update: null });
  });

  it("draws Needs you with the first request spelled out and the counts below", () => {
    const m = trayModel(
      needsSnap(2, { failing: { jobs: 3, profileCount: 2, profiles: ["sentinel", "clonara"] }, running: { count: 2, rows: [] }, unread: 1 }),
      NOW,
    );
    expect(m.title).toBe("2 things need you");
    expect(m.sub).toBe("p0 and p1");
    expect(m.rows).toHaveLength(2);
    expect(m.rows[0]).toMatchObject({ key: "r0", kind: "approval", title: "wants to run a command", sub: "p0 · approval · 2m ago" });
    expect(m.counts.map((c) => [c.key, c.label, c.value, c.danger])).toEqual([
      ["failing", "Failing jobs", "3 in 2 profiles", true],
      ["running", "Running", "2", false],
    ]);
    expect(m.labels).toBe(true);
    expect(m.unread).toBe(1);
    expect(m.bellLabel).toBe("Notifications · 1 unread");
  });

  it("lists the running turns as rows with their fold and elapsed time", () => {
    const m = trayModel(snap({ state: "running", running: { count: 2, rows: [turn(0), turn(1, { ts: null })] } }), NOW);
    expect(m.title).toBe("Alpi is working");
    expect(m.sub).toBe("Working now");
    expect(m.labels).toBe(false);
    expect(m.runs).toEqual([
      { key: "t0", title: "Turn 0", sub: "alpi · running", elapsed: "2m", fold: "llama", accent: "#14110c", deeplink: { kind: "chat", profile: "alpi", id: "s0", connection_id: "c" } },
      expect.objectContaining({ key: "t1", elapsed: "" }),
    ]);
    expect(m.counts).toEqual([]);
    expect(m.runsMore).toBe(0);
  });

  it("caps running rows at four and counts the rest", () => {
    const m = trayModel(snap({ state: "running", running: { count: 7, rows: [0, 1, 2, 3, 4, 5].map((i) => turn(i)) } }), NOW);
    expect(m.runs).toHaveLength(4);
    expect(m.runsMore).toBe(3);
  });

  it("lists running rows beside one needs-you row and collapses them to a count when needs you is full", () => {
    const running = { count: 2, rows: [turn(0), turn(1)] };
    const beside = trayModel(snap({ ...needsSnap(1), running }), NOW);
    expect(beside.runs).toHaveLength(2);
    expect(beside.counts).toEqual([]);
    const full = trayModel(snap({ ...needsSnap(3), running }), NOW);
    expect(full.runs).toEqual([]);
    expect(full.counts).toEqual([{ key: "running", icon: "activity", label: "Running", value: "2", danger: false }]);
  });

  it("falls back to the Running count line without rows", () => {
    expect(trayModel(snap({ state: "running", running: { count: 2, rows: [] } }), NOW).counts).toHaveLength(1);
  });

  it("draws Failing jobs with the profiles and the Activity window", () => {
    const m = trayModel(snap({ state: "failing", failing: { jobs: 3, profileCount: 2, profiles: ["sentinel", "clonara"] } }), NOW);
    expect(m.title).toBe("3 jobs are failing");
    expect(m.sub).toBe("sentinel and clonara · last 24 h");
    expect(m.counts[0].value).toBe("3 in 2 profiles");
  });

  it("draws a stopped daemon with its one action", () => {
    const m = trayModel(snap({ state: "offline", offline: { local: true, canStart: true, absent: false } }), NOW);
    expect(m).toMatchObject({ title: "alpi is installed but not running", sub: "Start it on this computer.", start: true, rows: [], counts: [] });
  });

  it("draws Starting with the request row and no action", () => {
    const m = trayModel(snap({ state: "starting" }), NOW);
    expect(m).toMatchObject({ title: "Starting alpi…", sub: "Waiting for the daemon", busy: "Start requested", start: false });
  });

  it("draws the update row on a quiet popover", () => {
    const m = trayModel(snap({ update: { version: "0.9.3", busy: false } }), NOW);
    expect(m.title).toBe("All quiet");
    expect(m.update).toEqual({ text: "alpi 0.9.3 is ready", busy: false });
  });

  it("draws Many items as four rows, the rest named, and the kinds counted", () => {
    const m = trayModel(
      needsSnap(7, { needs: { total: 7, approvals: 5, questions: 2, rows: Array.from({ length: 4 }, (_, i) => need(i)) }, unread: 4 }),
      NOW,
    );
    expect(m.title).toBe("7 things need you");
    expect(m.sub).toBe("p0, p1 and 2 more");
    expect(m.rows).toHaveLength(MAX_NEEDS_ROWS);
    expect(m.more).toBe(3);
  });

  it("covers every state it declares", () => {
    for (const state of TRAY_STATES) expect(trayModel(snap({ state }), NOW).state).toBe(state);
  });

  it("reads an unknown or missing state, or no snapshot at all, as quiet", () => {
    expect(trayModel(snap({ state: "mystery" }), NOW).state).toBe("quiet");
    expect(trayModel(null, NOW)).toMatchObject({ state: "quiet", rows: [], counts: [] });
    expect(trayModel(undefined, NOW).title).toBe("All quiet");
  });
});

describe("trayModel copy and plurals", () => {
  it("uses the singular for one thing", () => {
    expect(trayModel(needsSnap(1), NOW)).toMatchObject({ title: "P0 needs you", sub: "Waiting for an approval" });
    const one = trayModel(snap({ state: "failing", failing: { jobs: 1, profileCount: 1, profiles: ["sentinel"] } }), NOW);
    expect(one).toMatchObject({ title: "1 job is failing", sub: "sentinel · last 24 h" });
    expect(one.counts[0].value).toBe("1 in 1 profile");
    expect(trayModel(snap({ state: "running", running: { count: 1, rows: [] } }), NOW).title).toBe("1 running");
  });

  it("names the agent that is working, two of them, or counts beyond that", () => {
    const state = (rows, count = rows.length) => snap({ state: "running", running: { count, rows } });
    const m = trayModel(state([turn(0, { label: "sentinel", ts: sec(660) })]), NOW);
    expect(m).toMatchObject({ title: "Sentinel is working", sub: "11m" });
    expect(trayModel(state([turn(0, { label: "sentinel" }), turn(1, { label: "alpi" })]), NOW).title).toBe("Sentinel and alpi are working");
    expect(trayModel(state([turn(0, { label: "a" }), turn(1, { label: "b" }), turn(2, { label: "c" })]), NOW).title).toBe("3 running");
    expect(trayModel(state([turn(0), turn(1)]), NOW).title).toBe("Alpi is working");
  });

  it("counts the turns instead of naming an agent when the rows do not cover them all", () => {
    const m = trayModel(snap({ state: "running", running: { count: 6, rows: [0, 1, 2, 3].map((i) => turn(i, { label: "a" })) } }), NOW);
    expect(m.title).toBe("6 running");
  });

  it("tells what else is going on in the subtitle", () => {
    const next = { total: 4, rows: [] };
    const running = trayModel(snap({ state: "running", running: { count: 1, rows: [turn(0, { label: "sentinel" })] }, next }), NOW);
    expect(running.sub).toBe("2m · 4 coming up");
    const needing = trayModel(snap({ ...needsSnap(1), running: { count: 1, rows: [turn(0)] }, next }), NOW);
    expect(needing.sub).toBe("1 running · 4 coming up");
  });

  it("describes a question as a question", () => {
    const rows = [need(0, { kind: "question", title: "", label: "doc", ts: sec(10) })];
    const m = trayModel(snap({ state: "needs", needs: { total: 1, approvals: 0, questions: 1, rows } }), NOW);
    expect(m).toMatchObject({ title: "Doc needs you", sub: "Has a question" });
    expect(m.rows[0]).toMatchObject({ kind: "question", title: "has a question", sub: "doc · question · just now" });
  });

  it("names the profiles that need you, or the kinds when one profile does", () => {
    const rows = [need(0, { label: "abby" }), need(1, { label: "doc" }), need(2, { label: "sentinel" })];
    const three = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 3, questions: 0, rows } }), NOW);
    expect(three).toMatchObject({ title: "3 things need you", sub: "abby, doc and sentinel" });
    const many = trayModel(snap({ state: "needs", needs: { total: 5, approvals: 5, questions: 0, rows: [...rows, need(3, { label: "x" })] } }), NOW);
    expect(many.sub).toBe("abby, doc and 2 more");
    const one = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 2, questions: 1, rows: [need(0)] } }), NOW);
    expect(one.sub).toBe("p0 · 2 approvals, 1 question");
    const only = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 0, questions: 3, rows: [need(0)] } }), NOW);
    expect(only.sub).toBe("p0 · 3 questions");
  });

  it("names two failing profiles, and a third as N more", () => {
    const three = trayModel(snap({ state: "failing", failing: { jobs: 5, profileCount: 3, profiles: ["a", "b"] } }), NOW);
    expect(three.sub).toBe("a, b and 1 more · last 24 h");
    const four = trayModel(snap({ state: "failing", failing: { jobs: 5, profileCount: 4, profiles: ["a", "b"] } }), NOW);
    expect(four.sub).toBe("a, b and 2 more · last 24 h");
  });

  it("falls back when the failing profiles are unknown", () => {
    expect(trayModel(snap({ state: "failing", failing: { jobs: 2, profileCount: 0, profiles: [] } }), NOW).sub).toBe("Last 24 h");
  });

  it("falls back to the profile when a running turn has no title", () => {
    const m = trayModel(snap({ state: "running", running: { count: 1, rows: [turn(0, { title: "" })] } }), NOW);
    expect(m.runs[0].title).toBe("alpi");
  });

  it("explains an outage by its cause", () => {
    expect(trayModel(snap({ state: "offline", offline: { local: true, canStart: false, absent: true } }), NOW)).toMatchObject({ title: "alpi isn’t installed", start: false });
    expect(trayModel(snap({ state: "offline", offline: { local: true, canStart: false, absent: false } }), NOW).title).toBe("alpi isn’t running");
    expect(trayModel(snap({ state: "offline", offline: { local: false, canStart: false, absent: false } }), NOW)).toMatchObject({ title: "Can’t reach alpi", start: false });
    expect(trayModel(snap({ state: "offline" }), NOW).title).toBe("Can’t reach alpi");
    expect(trayModel(snap({ state: "connecting" }), NOW)).toMatchObject({ title: "Connecting…", busy: null });
  });

  it("never offers Start unless the snapshot can start", () => {
    expect(trayModel(snap({ state: "quiet", offline: { canStart: true } }), NOW).start).toBe(false);
  });

  it("words an update without a version", () => {
    expect(trayModel(snap({ update: { version: null, busy: true } }), NOW).update).toEqual({ text: "An update is ready", busy: true });
  });
});

describe("trayModel limits and ordering", () => {
  it("never draws more than four needs-you rows even if handed more", () => {
    const rows = Array.from({ length: 9 }, (_, i) => need(i));
    const m = trayModel(snap({ state: "needs", needs: { total: 9, approvals: 9, questions: 0, rows } }), NOW);
    expect(m.rows.map((r) => r.key)).toEqual(["r0", "r1", "r2", "r3"]);
    expect(m.more).toBe(5);
  });

  it("has no more row at exactly four, or fewer", () => {
    expect(trayModel(needsSnap(4), NOW)).toMatchObject({ more: 0 });
    expect(trayModel(needsSnap(3), NOW)).toMatchObject({ more: 0 });
  });

  it("keeps the daemon order of the rows", () => {
    const rows = [need(2), need(0), need(1)];
    const m = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 3, questions: 0, rows } }), NOW);
    expect(m.rows.map((r) => r.key)).toEqual(["r2", "r0", "r1"]);
  });

  it("lists failing before running", () => {
    const m = trayModel(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] }, running: { count: 2, rows: [] }, failing: { jobs: 1, profileCount: 1, profiles: ["x"] } }), NOW);
    expect(m.counts.map((c) => c.key)).toEqual(["failing", "running"]);
  });

  it("hides rows and counts while the daemon is not reachable", () => {
    const m = trayModel(snap({ state: "offline", needs: { total: 2, approvals: 2, questions: 0, rows: [need(0)] }, running: { count: 1, rows: [] }, failing: { jobs: 1, profileCount: 1, profiles: ["x"] } }), NOW);
    expect(m).toMatchObject({ rows: [], more: 0, counts: [] });
  });

  it("tolerates garbage counts", () => {
    const m = trayModel(snap({ state: "failing", failing: { jobs: "x", profileCount: -4, profiles: [] }, running: { count: NaN, first: null } }), NOW);
    expect(m.counts).toEqual([]);
    expect(m.title).toBe("0 jobs are failing");
  });
});

describe("trayModel members and the bell", () => {
  it("hides the bell for a member connection", () => {
    expect(trayModel(snap({ member: true }), NOW).bell).toBe(false);
    expect(trayModel(snap({ member: false }), NOW).bell).toBe(true);
  });

  it("labels the bell plainly with nothing unread", () => {
    expect(trayModel(snap(), NOW).bellLabel).toBe("Notifications");
  });

  it("carries the row's deeplink untouched and null when absent", () => {
    const m = trayModel(snap({ state: "needs", needs: { total: 2, approvals: 2, questions: 0, rows: [need(0), need(1, { deeplink: undefined })] } }), NOW);
    expect(m.rows[0].deeplink).toEqual({ kind: "approval", profile: "p0", id: "r0", connection_id: "c1" });
    expect(m.rows[1].deeplink).toBeNull();
  });

  it("dates a row against the clock it is given", () => {
    const rows = [need(0, { ts: sec(7200) }), need(1, { ts: sec(5) })];
    const m = trayModel(snap({ state: "needs", needs: { total: 2, approvals: 2, questions: 0, rows } }), NOW);
    expect(m.rows[0].sub).toContain("2h ago");
    expect(m.rows[1].sub).toContain("just now");
  });
});

describe("trayModel without a verdict on activity", () => {
  it("draws a neutral heading for a daemon that cannot list activity", () => {
    const m = trayModel(snap({ state: "online" }), NOW);
    expect(m).toMatchObject({ state: "online", title: "alpi", sub: "online", rows: [], counts: [], more: 0 });
    expect(`${m.title} ${m.sub}`).not.toMatch(/quiet|Nothing needs/i);
  });

  it("draws Connecting while the first activity reply is pending", () => {
    expect(trayModel(snap({ state: "connecting" }), NOW)).toMatchObject({ title: "Connecting…", sub: "Waiting for the daemon" });
  });

  it("still tells a real quiet", () => {
    expect(trayModel(snap(), NOW)).toMatchObject({ title: "All quiet", sub: "Nothing needs you · online" });
  });

  it("heads a reduced snapshot by its counts alone", () => {
    expect(trayModel({ v: 1, state: "needs", counts: { needs: 3, failing: 0, running: 0 } }, NOW)).toMatchObject({ title: "3 things need you", rows: [], more: 3 });
    expect(trayModel({ v: 1, state: "failing", counts: { failing: 2 } }, NOW)).toMatchObject({ title: "2 jobs are failing" });
    expect(trayModel({ v: 1, state: "running", counts: { running: 1 } }, NOW).title).toBe("1 running");
  });
});

describe("trayModel quiet Next line", () => {
  const AT = new Date(NOW + 5 * 3600e3).toISOString();
  const job = (i, over = {}) => ({ id: `c/p/j${i}`, title: `Job ${i}`, label: "scribe", at: AT, source: null, fold: "llama", accent: "#14110c", deeplink: { kind: "settings", profile: "scribe", id: "schedules", connection_id: "c" }, ...over });
  const quiet = (over = {}) => snap({ next: { rows: [job(0)] }, ...over });

  it("lists the next jobs under a Coming up heading", () => {
    const m = trayModel(quiet({ next: { rows: [job(0), job(1, { source: "mirai" })] } }), NOW);
    expect(m.title).toBe("All quiet");
    expect(m.sub).toBe("Coming up");
    expect(m.nextRows).toEqual([
      { key: "c/p/j0", title: "Job 0", sub: "scribe", when: expect.any(String), fold: "llama", accent: "#14110c", deeplink: expect.any(Object) },
      expect.objectContaining({ key: "c/p/j1", sub: "scribe · mirai" }),
    ]);
  });

  it("caps the list at three rows", () => {
    expect(trayModel(quiet({ next: { rows: [0, 1, 2, 3, 4].map((i) => job(i)) } }), NOW).nextRows).toHaveLength(3);
  });

  it("falls back to the title-less profile label", () => {
    expect(trayModel(quiet({ next: { rows: [job(0, { title: "" })] } }), NOW).nextRows[0].title).toBe("scribe");
  });

  it("says Nothing scheduled for an admin with no job", () => {
    const m = trayModel(quiet({ next: null }), NOW);
    expect(m.sub).toBe("Nothing scheduled");
    expect(m.nextRows).toEqual([]);
  });

  it("keeps the neutral line for a member without jobs and lists the jobs another connection brought", () => {
    expect(trayModel(snap({ member: true, next: null }), NOW).sub).toBe("Nothing needs you · online");
    const m = trayModel(quiet({ member: true }), NOW);
    expect(m.sub).toBe("Coming up");
    expect(m.nextRows).toHaveLength(1);
  });

  it("names the connection on a needs-you and a running row", () => {
    const needs = trayModel(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [{ id: "m/1", kind: "approval", label: "sentinel", source: "mirai", title: "t", ts: null }] } }), NOW);
    expect(needs).toMatchObject({ title: "Sentinel needs you", sub: "Waiting for an approval · mirai" });
    expect(needs.rows[0].sub).toBe("sentinel · mirai · approval");
    const running = trayModel(snap({ state: "running", running: { count: 1, rows: [{ id: "m/s", label: "sentinel", source: "mirai", title: "Review", ts: null }] } }), NOW);
    expect(running.runs[0].sub).toBe("sentinel · mirai · running");
  });

  it("renders today's popover for a snapshot without next", () => {
    expect(trayModel(snap(), NOW)).toMatchObject({ sub: "Nothing needs you · online", nextRows: [] });
  });

  it("makes no claim when the daemon cannot list activity or is still loading", () => {
    expect(trayModel(quiet({ state: "online", next: null }), NOW)).toMatchObject({ title: "alpi", sub: "online", nextRows: [] });
    expect(trayModel(quiet({ state: "connecting" }), NOW)).toMatchObject({ title: "Connecting…", nextRows: [] });
  });

  it("keeps the Coming up rows beside running, needs you and failing within the five-row budget", () => {
    const next = { total: 3, rows: [0, 1, 2].map((i) => job(i)) };
    const running = { count: 1, rows: [turn(0)] };
    const beside = trayModel(snap({ state: "running", running, next }), NOW);
    expect(beside.runs).toHaveLength(1);
    expect(beside.nextRows).toHaveLength(2);
    expect(beside.labels).toBe(true);
    const failing = trayModel(snap({ state: "failing", failing: { jobs: 3, profileCount: 2, profiles: ["a", "b"] }, next }), NOW);
    expect(failing.nextRows).toHaveLength(3);
    expect(failing.labels).toBe(true);
    const needing = trayModel(snap({ ...needsSnap(2), running, next }), NOW);
    expect(needing.rows.length + needing.runs.length + needing.nextRows.length).toBeLessThanOrEqual(5);
    expect(needing.nextRows).toHaveLength(2);
  });

  it("hides Coming up when needs you fills the popover", () => {
    const next = { total: 3, rows: [job(0)] };
    const m = trayModel(snap({ ...needsSnap(3), running: { count: 2, rows: [turn(0), turn(1)] }, next }), NOW);
    expect(m.nextRows).toEqual([]);
    expect(m.counts.map((c) => c.key)).toEqual(["running"]);
  });

  it("labels the sections only when more than one shows", () => {
    expect(trayModel(quiet(), NOW).labels).toBe(false);
    expect(trayModel(snap({ state: "failing", failing: { jobs: 1, profileCount: 1, profiles: ["x"] } }), NOW).labels).toBe(false);
  });

  it("hides the line while the daemon is not reachable", () => {
    for (const state of ["offline", "starting", "connecting"]) {
      expect(trayModel(quiet({ state }), NOW).nextRows, state).toEqual([]);
    }
  });
});
